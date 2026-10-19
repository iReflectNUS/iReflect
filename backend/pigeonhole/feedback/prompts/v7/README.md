# Runtime feedback version: T1_v3 + T2_v7_guided

These six prompt/schema/configuration files are byte-for-byte copies of the
final research package at output/rq2_final_v7_20261015/prompt_package.
source_manifest.json records their SHA-256 values.
This is the two-stage candidate retained on 15 October, not the older
single-pass v7/v7.2 or the rejected v8.

- Reflection A (even user IDs, BASIC): the original scoring call remains in
  _askChatGPTOriginalScored; its numeric results are carried into the response.
  Its full original grading response is retained in score_json for source audits;
  superseded advice is not shown in the new student feedback.
  New A/playtest records label the feedback pipeline in model_version so they
  can be distinguished from earlier records; this label is not a claim that
  the separate grading model changed.
  Its old suggestions are replaced by this two-stage feedback. Reflection B
  (odd IDs, ADVANCED), its scoring calls and its feedback prompt are unchanged.
- Playtest has one shared route, not the reflection A/B split. LightRAG still
  receives the original grading query, rubric, genre/mechanic and hybrid mode.
  The score/rationale prefix is retained; its Professor Feedback and Final
  Summary are replaced by v7. Production nginx must route through Django.
- Both calls use the supplied question and current answer, not numeric grades.
  T1 supplies the requirement table and T2 checks it against the source again.
  Runtime T1 is raw/model-generated; no claim of the researcher's manually
  corrected-table quality is made.
- No history is automatically added. The unchanged v7 prompt supports optional
  history, but its deployed input here uses null P/F because history benefit is
  unresolved and this change does not authorise a history intervention.
- Feedback has at most two actions and one specific strength. No supported
  residual means no action, regardless of whether the independent grade is
  maximum. Missing external context remains limited, not "all requirements met".
- Schema, source IDs, row coverage, action mappings and a 180-word final
  feedback limit are checked. Invalid/refused/overlength output is an error,
  not a legacy fallback, truncation or a third repair call. Formal checks
  cannot guarantee the model's semantic interpretation.

Each successful A/playtest request adds two model calls to its original
grading path. The original single-call A scoring method, Advanced/B
three-draw scoring and LightRAG grading criteria are not replaced by v7.
The 180-word limit applies to the new feedback, not the separate score block.

The backend needs OPENAI_API_KEY and playtest also needs LIGHTRAG_URL and its
existing LIGHTRAG_API_KEY. Docker compose supplies the internal LightRAG URL;
credentials are not included here. DEBUG-only unconfigured mocks are not v7.
No deployment or live API experiment is performed by copying these files.

Structured-output transport follows the official OpenAI documentation:
https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat
