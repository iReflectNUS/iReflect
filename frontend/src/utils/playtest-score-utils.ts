/**
 * @changelog
 * | Version | Description                                            | Reference                                     |
 * | v1.0.0 | Extracted playtest score helpers: parse / sanitize placeholders / strip numbers but keep comments | BUG: playtest-missing-score-json |
 * | v1.1.0 | Tolerate format drift: bare "31/50" lines and "4/10" without brackets (model stopped emitting **[x/y]**) | BUG: playtest-score-format-drift |
 * /@changelog
 *
 * @author chuckyang123
 */
import type { PlaytestScoreJson } from "../types/feedback";

/**
 * Score helpers for LightRAG playtest feedback markdown.
 *
 * The LightRAG output follows `prompt_for_playtest_feedback.txt`, but the model
 * drifts between notations, so every score is matched in all observed shapes:
 *   **Score: [79/100]** | Score: 79/100
 *   - **Specificity:** [4/10] – text | - **Specificity:** 4/10 – text
 *   - **[18/50]** – text | 31/50 on its own line | - 31/50 – text
 *
 * Three separate jobs:
 *   1. parsePlaytestScores() → structured scores sent as score_json
 *   2. sanitizeScorePlaceholders() → drops unfilled placeholders such as
 *      **[XX/100]** so neither students nor teachers ever see them
 *   3. stripScoresFromMarkdown() → hides the numbers but KEEPS the
 *      qualitative comments (PRD 20260824-playtest-score-visibility)
 */
const DENOMINATORS = "(?:100|50|12|10|2)";
/** A real numeric score, e.g. 79 / 100 (spacing tolerated). */
const NUMERIC_SCORE = String.raw`\d{1,3}\s*\/\s*${DENOMINATORS}`;
/** A score-shaped token with or without brackets, numeric or placeholder. */
const ANY_SCORE = String.raw`\[?[A-Za-z0-9]{0,4}\s*\/\s*${DENOMINATORS}\]?`;
/** Same token inside a list item, optionally bolded: "**[18/50]**". */
const ANY_SCORE_ITEM = String.raw`\*{0,2}${ANY_SCORE}\*{0,2}`;
const NUMERIC_PAIR = new RegExp(`^\\d{1,3}\\s*\\/\\s*${DENOMINATORS}$`);

/** "**Score: [79/100]**" / "Score: 79/100" (a whole line). */
const TOTAL_LINE = new RegExp(
  String.raw`^\*{0,2}\s*Score:\s*(${ANY_SCORE})\s*\*{0,2}$`,
);
/** A line that is nothing but a score: "31/50", "- 31/50", "**31/50**". */
const SCORE_ONLY_LINE = new RegExp(
  String.raw`^[-*]?\s*\*{0,2}\s*(${ANY_SCORE})\s*\*{0,2}\s*$`,
);
/** "- **Specificity:** [4/10] – text" / "- 31/50 – text" (label optional). */
const SCORED_ITEM = new RegExp(
  String.raw`^(\s*[-*]\s+(?:\*\*[^*:]+:\*\*)?)\s*(${ANY_SCORE_ITEM})\s*[–-]?\s*`,
);

function isRealScore(token: string): boolean {
  return NUMERIC_PAIR.test(token.replace(/[[\]*]/g, "").trim());
}

function toScoreKey(label: string): string {
  return label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
}

function joinLines(lines: (string | null)[]): string {
  return lines
    .filter((line): line is string => line !== null)
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Extract the numeric scores so the backend can persist them (score_json). */
export function parsePlaytestScores(
  markdown: string,
): PlaytestScoreJson | null {
  // eslint-disable-next-line prefer-regex-literals -- embeds NUMERIC_SCORE
  const totalMatch = markdown.match(
    new RegExp(String.raw`Score:\s*\[?(${NUMERIC_SCORE})\]?`, "i"),
  );
  // /50 is only used by the knowledge graph score, /10 only by ingredients.
  const graphMatch = markdown.match(/\[?(\d{1,3})\s*\/\s*50\]?/);
  const breakdown: Record<string, number> = {};
  // eslint-disable-next-line prefer-regex-literals -- multiline flag
  const ingredient = new RegExp(
    String.raw`^[-*]\s+\*\*([^:*]+):\*\*\s*\[?(\d{1,3})\s*\/\s*\d+\]?`,
    "gm",
  );
  let match = ingredient.exec(markdown);
  while (match !== null) {
    breakdown[toScoreKey(match[1])] = Number(match[2]);
    match = ingredient.exec(markdown);
  }

  const total = totalMatch ? Number(totalMatch[1].split("/")[0]) : null;
  const knowledgeGraph = graphMatch ? Number(graphMatch[1]) : null;
  if (
    total === null &&
    knowledgeGraph === null &&
    Object.keys(breakdown).length === 0
  ) {
    return null;
  }
  return { total, breakdown, knowledge_graph: knowledgeGraph };
}

/** Remove score markers that the model left unfilled (e.g. **[XX/100]**). */
export function sanitizeScorePlaceholders(markdown: string): string {
  return joinLines(
    markdown.split("\n").map((line) => {
      const total = line.match(TOTAL_LINE);
      if (total && !isRealScore(total[1])) {
        return null;
      }
      const item = line.match(SCORED_ITEM);
      if (item && !isRealScore(item[2])) {
        // Keep the label and the comment, drop only the placeholder token.
        return line.replace(SCORED_ITEM, "$1 ").replace(/[ \t]+$/, "");
      }
      return line.replace(/[ \t]+$/, "");
    }),
  );
}

/** Hide numeric scores while keeping every qualitative comment. */
export function stripScoresFromMarkdown(markdown: string): string {
  return joinLines(
    markdown.split("\n").map((line) => {
      // Total-score and bare-score lines carry no qualitative text.
      if (TOTAL_LINE.test(line) || SCORE_ONLY_LINE.test(line)) {
        return null;
      }
      const item = line.match(SCORED_ITEM);
      if (item && isRealScore(item[2])) {
        // Keep the label and the comment, drop only the numeric score.
        return line.replace(SCORED_ITEM, "$1 ").replace(/[ \t]+$/, "");
      }
      return line.replace(/[ \t]+$/, "");
    }),
  );
}
