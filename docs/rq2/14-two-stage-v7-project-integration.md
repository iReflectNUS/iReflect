# Two-stage v7 feedback integration — 19 October 2026

Status: implemented locally; not deployed or pushed; no live-model calls.

## What was running before

- Individual reflection A: even-numbered accounts use BASIC / askChatGPTOriginal.
  This was the 14 October single-call suggestion adaptation, not the final
  T1_v3 + T2_v7_guided. Its grader and advice shared one response.
- Individual reflection B: odd-numbered accounts use ADVANCED / askChatGPT.
- Playtest: a shared LightRAG grading/advice prompt. It has no reflection-style
  A/B allocation. The prompt required suggestions for every ingredient below
  ten and a reflective question. Production nginx previously bypassed Django.

## What changed

Both reflection A and playtest now run the exact frozen T1_v3 and T2_v7_guided
prompt/schema files copied from the final 15 October research package. These
are not the earlier single-pass v7/v7.2 files under docs/rq2/prompts and are
not v8. Source hashes are recorded in feedback/prompts/v7/source_manifest.json.

The new feedback checks the supplied task and current answer before advice:

1. T1 creates a fallible, source-linked requirement coverage table.
2. T2 checks the original question/current answer again, credits one concrete
   strength, and groups real residual gaps into zero to two actions.
3. If no assessable gap remains, there are no actions. Missing external
   comparisons remain assessment-limited rather than a claim of perfection.
4. Feedback is checked against the frozen schemas, source IDs, table/ledger
   coverage, actual action quotations, completion consistency and 180 words.
   It is rejected rather than silently truncated, repaired by another call or
   replaced with the legacy prompt if invalid.

These are structural safeguards and prompt instructions, not proof that the
live model will always interpret adequacy correctly. Unlike some development
experiments, runtime T1 is not manually corrected before T2. No history is
automatically introduced; the frozen prompt is used with null P/F.

## Scoring preservation

- Reflection A's original complete grading call was renamed to
  _askChatGPTOriginalScored without changing its AST body, prompt, model,
  temperature, answer input or original grading instructions. Its original
  numeric grades and total are extracted for display, not recomputed from v7.
  The original grading response is retained in score_json for audit; old advice
  is replaced in the student-facing feedback.
- B's functions, score sampling/averaging, feedback prompt and grouping remain
  unchanged. Its existing stage clean-up is unchanged.
- Playtest sends the original grading query and hybrid mode to LightRAG.
  Its numeric score block and rationale prefix remain unchanged. Only Professor
  Feedback and the old Final Summary are replaced. The frontend score parser
  and score-hiding rules remain unchanged.
- The old public playtest prompt remains as grading input, not the final
  student-advice prompt. Copying v7 over that file would change the scoring
  instructions and omit the second-stage contract, so it was not done.

New A/playtest records identify the feedback pipeline in model_version; A also
logs the prompt version with token usage. No database migration or teacher
editing/approval workflow was added.

## Routing and runtime

The frontend playtest request now supplies question and answer separately
alongside the unchanged grading query. Both production and local playtest
requests go through Django; nginx no longer sends production requests directly
to LightRAG. Docker backend configuration supplies the internal LIGHTRAG_URL.
Gunicorn and proxy read timeouts allow for the additional sequential calls.

The backend needs its existing OPENAI_API_KEY. Playtest also needs the existing
LightRAG service/key. Each successful A/playtest request adds two feedback-model
calls to its original grading path. The feedback model is the tested snapshot
gpt-4o-2024-08-06 at temperature 0.1, max_tokens 5000. Grading models are unchanged.
Unconfigured DEBUG mocks are explicitly local mocks, not evidence of v7 quality.

## Validation and boundary

The no-network verification covers correct stopping, real-gap actions, source
IDs, row/action mapping, refusal, overlength rejection, unchanged grading query,
retained numeric scores, and request routing contracts. The broader feedback,
score visibility, history and research export regressions run against an
in-memory database. Frontend TypeScript is checked without emitting files.

Actual results and a repeatable runner:
E:/FYP/output/v7_project_integration_20261019/Verification_Results.json
E:/FYP/output/v7_project_integration_20261019/run_offline_checks.py

No production server was inspected or changed, so this establishes the local
code version only. Deployment requires rebuilding the backend, frontend and
reverse proxy together; there is no claim that the current website is already
using these changes. v7 remains a final development candidate, not established
superiority or evidence of student cognitive progression.

Structured output transport was checked against official OpenAI documentation:
https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat
