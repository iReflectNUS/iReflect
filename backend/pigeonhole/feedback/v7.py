"""Frozen T1_v3 + T2_v7_guided, feedback only. Grading is a separate caller."""
import copy
import json
import logging
import os
import re
import time
from pathlib import Path

from openai import OpenAI

logger = logging.getLogger(__name__)
ASSETS = Path(__file__).resolve().parent / "prompts" / "v7"
VERSION = "T1_v3+T2_v7_guided"
MODEL = "gpt-4o-2024-08-06"


class V7FeedbackError(RuntimeError):
    """A refused, incomplete or invalid response must not become legacy advice."""


def _schema_check(value, schema):
    """Validate the small JSON-schema subset used by the frozen assets."""
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            raise V7FeedbackError("Expected a feedback object.")
        if not set(schema.get("required", [])) <= set(value):
            raise V7FeedbackError("Incomplete feedback object.")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(props):
            raise V7FeedbackError("Unexpected feedback fields.")
        for key, child in value.items():
            if key in props:
                _schema_check(child, props[key])
    elif kind == "array":
        if not isinstance(value, list):
            raise V7FeedbackError("Expected a feedback list.")
        for child in value:
            _schema_check(child, schema["items"])
    elif kind == "string" and not isinstance(value, str):
        raise V7FeedbackError("Expected feedback text.")
    if "enum" in schema and value not in schema["enum"]:
        raise V7FeedbackError("Invalid feedback status.")


def evidence(text, prefix):
    return [{"id": f"{prefix}{i}", "text": line}
            for i, line in enumerate((s.strip() for s in text.splitlines() if s.strip()), 1)]


def _call(client, prompt_name, schema_name, user):
    schema = json.loads((ASSETS / schema_name).read_text(encoding="utf-8"))
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        max_tokens=5000,
        messages=[
            {"role": "system", "content": (ASSETS / prompt_name).read_text(encoding="utf-8")},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        response_format={"type": "json_schema", "json_schema": {
            "name": "current_assessment" if schema_name.startswith("assessment") else "feedback_v7",
            "strict": True, "schema": schema,
        }},
    )
    choice = response.choices[0]
    if choice.finish_reason != "stop" or getattr(choice.message, "refusal", None):
        raise V7FeedbackError("Feedback was refused or incomplete.")
    try:
        payload = json.loads(choice.message.content)
    except (TypeError, ValueError) as exc:
        raise V7FeedbackError("Feedback was not valid JSON.") from exc
    _schema_check(payload, schema)
    usage = response.usage
    return payload, ({
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    } if usage else None)


def _table_source_errors(table, user):
    """Pass fallible T1 source problems into T2; do not 'repair' its semantics."""
    errors = []
    qs = {x["id"]: x["text"] for x in user["task"]["evidence"]}
    cs = {x["id"]: x["text"] for x in user["current"]["evidence"]}
    seen = set()
    for row in table["requirements"]:
        rid = row["requirementId"]
        if rid in seen:
            errors.append(f"{rid}:duplicate_requirement")
        seen.add(rid)
        if not row["questionEvidenceIds"] or not set(row["questionEvidenceIds"]) <= qs.keys():
            errors.append(f"{rid}:invalid_Q_id")
        if not row["taskQuote"] or not any(row["taskQuote"] in qs.get(i, "") for i in row["questionEvidenceIds"]):
            errors.append(f"{rid}:invalid_task_quote")
        for e in row["currentEvidence"]:
            if not e["quote"] or e["quote"] not in cs.get(e["id"], ""):
                errors.append(f"{rid}:invalid_current_quote")
        if row["status"] in ("satisfied", "partially_satisfied") and not row["currentEvidence"]:
            errors.append(f"{rid}:missing_current_support")
    return errors


def _validate_result(envelope, user):
    feedback = envelope["feedback"]
    ledger = envelope["coverageLedger"]
    qids = {x["id"] for x in user["task"]["evidence"]}
    cids = {x["id"] for x in user["current"]["evidence"]}
    table_ids = {r["requirementId"] for r in user["currentAssessment"]["table"]["requirements"]}
    ledger_ids = [r["requirementId"] for r in ledger]
    if not ledger or len(ledger_ids) != len(set(ledger_ids)) or not table_ids <= set(ledger_ids):
        raise V7FeedbackError("Feedback omitted or duplicated an assessment row.")
    actions = {}
    suggestions = feedback["suggestions"]
    if len(suggestions) > 2 or len(feedback["strengths"]) > 1:
        raise V7FeedbackError("Feedback exceeded the v7 action or strength limit.")
    for row in ledger:
        rid = row["requirementId"]
        if rid not in table_ids and not re.fullmatch(r"N[1-9][0-9]*", rid):
            raise V7FeedbackError("Feedback introduced an invalid requirement.")
        if (not row["questionEvidenceIds"] or not set(row["questionEvidenceIds"]) <= qids
                or not set(row["currentEvidenceIds"]) <= cids or not row["finding"].strip()):
            raise V7FeedbackError("Feedback evidence does not match the current answer.")
        if row["disposition"] == "already_satisfied" and not row["currentEvidenceIds"]:
            raise V7FeedbackError("A satisfied requirement needs current evidence.")
        slot = row["suggestionSlot"]
        if row["disposition"] == "action":
            if (slot == "none" or int(slot) > len(suggestions)
                    or not row["actionQuote"] or row["actionQuote"] not in suggestions[int(slot)-1]["nextStep"]):
                raise V7FeedbackError("A genuine gap is not linked to an action.")
            actions[rid] = slot
        elif slot != "none" or row["actionQuote"]:
            raise V7FeedbackError("A nonaction requirement cannot request a revision.")
    groups = envelope["actionGroups"]
    slots = [g["suggestionSlot"] for g in groups]
    if len(slots) != len(set(slots)) or set(slots) != {str(i+1) for i in range(len(suggestions))}:
        raise V7FeedbackError("Feedback actions and groups do not match.")
    grouped = []
    for group in groups:
        if not group["sharedPurpose"].strip() or not group["requirementIds"]:
            raise V7FeedbackError("Empty feedback action group.")
        for rid in group["requirementIds"]:
            grouped.append(rid)
            if actions.get(rid) != group["suggestionSlot"]:
                raise V7FeedbackError("An action was assigned to the wrong gap.")
    if len(grouped) != len(set(grouped)) or set(grouped) != set(actions):
        raise V7FeedbackError("Feedback skipped a residual gap.")
    for strength in feedback["strengths"]:
        if not strength["currentEvidenceIds"] or not set(strength["currentEvidenceIds"]) <= cids:
            raise V7FeedbackError("A strength needs current-answer evidence.")
    for suggestion in suggestions:
        if (not suggestion["nextStep"].strip() or not suggestion["questionEvidenceIds"]
                or not set(suggestion["questionEvidenceIds"]) <= qids
                or not set(suggestion["currentEvidenceIds"]) <= cids):
            raise V7FeedbackError("An action needs valid evidence and a next step.")
    # Current-only deployment does not implicitly activate the unresolved history experiment.
    if feedback["historyAudit"] or any(x["classification"] != "currently_present_origin_unknown"
                                       or x["previousAnswerEvidenceIds"] for x in feedback["newOrMissedGaps"]):
        raise V7FeedbackError("Current-only feedback cannot infer a history.")
    for gap in feedback["newOrMissedGaps"]:
        if not set(gap["questionEvidenceIds"]) <= qids or not set(gap["currentEvidenceIds"]) <= cids:
            raise V7FeedbackError("Invalid gap evidence.")
    expected = ("revision_suggested" if actions else "assessment_limited"
                if any(x["disposition"] == "unverifiable" for x in ledger) else "no_material_gap")
    if feedback["completion"] != expected or bool(suggestions) != bool(actions):
        raise V7FeedbackError("Feedback stopped early or requested unnecessary actions.")
    words = " ".join([feedback["summary"]] + [s["comment"] for s in feedback["strengths"]] +
                     [s[k] for s in suggestions for k in ("acknowledges", "gap", "nextStep")])
    if len(words.split()) > 180 or len(render_feedback(feedback).split()) > 180:
        raise V7FeedbackError("Feedback exceeded 180 words.")


def render_feedback(feedback):
    lines = [feedback["summary"], "", "**What works**"]
    lines += ["- " + s["comment"] for s in feedback["strengths"]]
    lines += ["", "**Next steps**"]
    if feedback["suggestions"]:
        lines += ["- " + " ".join(s[k] for k in ("acknowledges", "gap", "nextStep") if s[k])
                  for s in feedback["suggestions"]]
    elif feedback["completion"] == "assessment_limited":
        lines += ["No further revision is suggested within the assessable scope; the stated comparison remains unverified."]
    else:
        lines += ["No further material revision is suggested within the assessable scope."]
    if feedback["contextLimits"]:
        lines += ["", "**Assessment limits**"] + ["- " + s for s in feedback["contextLimits"]]
    return "\n".join(lines).strip()


def generate_feedback(question, answer):
    if not isinstance(question, str) or not question.strip():
        raise V7FeedbackError("The task question is required for v7 feedback.")
    if not isinstance(answer, str) or not answer.strip():
        raise V7FeedbackError("The current answer is required for v7 feedback.")
    started = time.monotonic()
    user = {"task": {"instructions": "", "evidence": evidence(question, "Q")},
            "current": {"evidence": evidence(answer, "C")},
            "previousAnswer": None, "previousFeedback": None, "relatedAnswers": []}
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), max_retries=0, timeout=60.0)
        # T1 sees current sources only; no scores, prior feedback, genre or KG demands.
        table, u1 = _call(client, "T1_current_assessment_v3.txt", "assessment_schema_v3.json",
                          {"task": copy.deepcopy(user["task"]), "current": copy.deepcopy(user["current"])})
        user["currentAssessment"] = {"table": table, "sourceValidationErrors": _table_source_errors(table, user)}
        envelope, u2 = _call(client, "T2_feedback_v7_guided.txt", "stage2_envelope_v3.json", user)
        _validate_result(envelope, user)
    except V7FeedbackError:
        raise
    except Exception as exc:
        # Never log student text or fall back to the old suggestion prompt.
        logger.warning("v7 feedback failed (%s).", type(exc).__name__)
        raise V7FeedbackError("v7 feedback generation is temporarily unavailable.") from exc
    logger.info("Feedback prompt=%s model=%s completion=%s", VERSION, MODEL, envelope["feedback"]["completion"])
    return render_feedback(envelope["feedback"]), [u1, u2], (time.monotonic()-started)*1000


def reflection_score_block(graded_text):
    """Extract existing numeric grades, without a new score or old advice.

    The original A grading call is unchanged. Its suggestions are superseded;
    no new score is inferred from task sufficiency or the v7 table.
    """
    headers = list(re.finditer(r"(?im)^[^\n]*\b(Stage\s*[1-5]|Additional\s+Stage)\b[^\n]*", graded_text))
    labels = {str(i): label for i, label in enumerate([
        "Returning to Experience", "Attending to Feelings", "Integration",
        "Appropriation", "Outcomes of Reflection"], 1)}
    scores = {}
    for i, match in enumerate(headers):
        key = "additional" if match.group(1).lower().startswith("additional") else re.search(r"[1-5]", match.group(1)).group()
        block = graded_text[match.start():headers[i+1].start() if i+1 < len(headers) else len(graded_text)]
        value = re.search(r"(?<!\d)([0-2](?:\.\d+)?)\s*/\s*2\b", block)
        if not value:
            value = re.search(r"(?i)(?:score|grade)\s*[:=]?\s*\**\s*([0-2](?:\.\d+)?)\b", block)
        if value:
            scores[key] = value.group(1)
    total = re.search(r"(?im)^[^\n]*(?:total|overall)[^\n]*?(\d+(?:\.\d+)?)\s*/\s*12\b", graded_text)
    if set(scores) != set(labels) | {"additional"} or not total:
        raise V7FeedbackError("The original reflection scores could not be read safely.")
    lines = [f"**Stage {i}. {label}: {scores[i]} / 2**" for i, label in labels.items()]
    lines += [f"**Additional Stage. Readability and Accuracy: {scores['additional']} / 2**",
              f"**Total Score: {total.group(1)} / 12**"]
    return "\n\n".join(lines)


def replace_playtest_advice(graded_text, feedback):
    """Preserve the original numeric score block and its evidence explanations."""
    marker = re.search(r"(?im)^\s*\*{0,2}Professor(?:-Style)?\s+Feedback\s*:?\*{0,2}\s*$", graded_text)
    if not marker:
        raise V7FeedbackError("The original playtest score block could not be separated safely.")
    return graded_text[:marker.start()].rstrip() + "\n\n**Professor Feedback:**\n\n" + feedback
