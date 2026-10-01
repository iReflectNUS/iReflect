/**
 * @changelog
 * | Version | Description                                            | Reference                                     |
 * | v1.0.0 | Extracted playtest score helpers: parse / sanitize placeholders / strip numbers but keep comments | BUG: playtest-missing-score-json |
 * /@changelog
 *
 * @author chuckyang123
 */
import type { PlaytestScoreJson } from "../types/feedback";

/**
 * Score helpers for LightRAG playtest feedback markdown.
 *
 * The LightRAG output follows `prompt_for_playtest_feedback.txt`:
 *   **Score: [xx/100]** → **Breakdown of Key Ingredients:** (10 x [x/10])
 *   → **Genre & Mechanic Evaluation (Knowledge Graph Score):** ([x/50])
 *   → **Professor Feedback:** (text) → **Final Summary:** (text)
 *
 * Three separate jobs:
 *   1. parsePlaytestScores() → structured scores sent as score_json
 *   2. sanitizeScorePlaceholders() → drops unfilled placeholders such as
 *      **[XX/100]** so neither students nor teachers ever see them
 *   3. stripScoresFromMarkdown() → hides the numbers but KEEPS the
 *      qualitative comments (cutting to "**Professor Feedback:**" threw away
 *      the whole breakdown, PRD 20260824-playtest-score-visibility)
 */
const NUMERIC_SCORE = String.raw`\d+\s*\/\s*\d+`;
const TOTAL_LINE_ANY = /^\*\*Score:\s*\[[^\]]*\]\*\*$/;
// Literal form keeps ESLint happy; mirrors NUMERIC_SCORE inside the brackets.
const TOTAL_LINE_NUMERIC = /^\*\*Score:\s*\[\d+\s*\/\s*\d+\]\*\*$/;
/** - **Specificity:** [4/10] – explanation */
const INGREDIENT_NUMERIC = new RegExp(
  String.raw`^(\s*[-*]\s+\*\*[^*:]+:\*\*)\s*\[${NUMERIC_SCORE}\]\s*[–-]?\s*`,
);
/** Same shape but the bracket is not a real score (e.g. [x/10], [XX/10]). */
const INGREDIENT_PLACEHOLDER = new RegExp(
  String.raw`^(\s*[-*]\s+\*\*[^*:]+:\*\*)\s*\[(?!${NUMERIC_SCORE}\])[^\]]*\]\s*[–-]?\s*`,
);
/** - **[18/50]** – explanation */
const GRAPH_NUMERIC = new RegExp(
  String.raw`^(\s*[-*]\s+)\*\*\[${NUMERIC_SCORE}\]\*\*\s*[–-]?\s*`,
);
const GRAPH_PLACEHOLDER = new RegExp(
  String.raw`^(\s*[-*]\s+)\*\*\[(?!${NUMERIC_SCORE}\])[^\]]*\]\*\*\s*[–-]?\s*`,
);

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
  const totalMatch = markdown.match(
    new RegExp(String.raw`\*\*Score:\s*\[(${NUMERIC_SCORE})\]\*\*`),
  );
  const graphMatch = markdown.match(
    new RegExp(String.raw`\*\*\[(${NUMERIC_SCORE})\]\*\*`),
  );
  const breakdown: Record<string, number> = {};
  // Created per call so lastIndex restarts for every parse.
  const ingredient = /^[-*]\s+\*\*([^:*]+):\*\*\s*\[(\d+)\s*\/\s*\d+\]/gm;
  let match = ingredient.exec(markdown);
  while (match !== null) {
    breakdown[toScoreKey(match[1])] = Number(match[2]);
    match = ingredient.exec(markdown);
  }

  const total = totalMatch ? Number(totalMatch[1].split("/")[0]) : null;
  const knowledgeGraph = graphMatch
    ? Number(graphMatch[1].split("/")[0])
    : null;
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
      const trimmed = line.trim();
      if (TOTAL_LINE_ANY.test(trimmed) && !TOTAL_LINE_NUMERIC.test(trimmed)) {
        return null;
      }
      return line
        .replace(INGREDIENT_PLACEHOLDER, "$1 ")
        .replace(GRAPH_PLACEHOLDER, "$1")
        .replace(/[ \t]+$/, "");
    }),
  );
}

/** Hide numeric scores while keeping every qualitative comment. */
export function stripScoresFromMarkdown(markdown: string): string {
  return joinLines(
    markdown.split("\n").map((line) => {
      const trimmed = line.trim();
      // The total-score line carries no qualitative text.
      if (TOTAL_LINE_ANY.test(trimmed)) {
        return null;
      }
      return line
        .replace(INGREDIENT_NUMERIC, "$1 ")
        .replace(GRAPH_NUMERIC, "$1")
        .replace(/[ \t]+$/, "");
    }),
  );
}
