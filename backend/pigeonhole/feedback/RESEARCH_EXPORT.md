# Research data export

Teachers can open **Course details → Export research data**, choose the current
course or all courses they manage, and download a ZIP for external analysis.
The optional identity map contains names and emails separately. Raw answers and
other free text can still contain identifying information.

`POST /api/feedback/research-export/` uses the existing JWT authentication:

```json
{"scope": "course", "courseId": 123, "includeIdentity": false}
```

For all authorized courses, use `{"scope":"all","includeIdentity":false}`
without a course ID. Course owners, INSTRUCTOR/CO_OWNER members (including
STANDARD accounts), and ADMIN accounts can export. A global EDUCATOR account
alone does not grant access to another course.

The ZIP includes manifest checksums, a field/relationship guide, course settings,
forms, memberships/groups, current submissions, initial answers, all saved answer
versions, all REFLECTION and PLAYTEST feedback with scores and usage metadata,
submission comments (deleted bodies withheld), comparison candidates, and data
quality issues. Scores hidden from students remain available in teacher exports.

This endpoint does not call AI. An external tool can read
`derived/reflection_pairs.jsonl`, select `eligibility=ready`, and analyse those
inputs independently. No agent integration or result-import endpoint is added.

## Consistency and resource limits

PostgreSQL reads run in one read-only REPEATABLE READ transaction. After creating
the archive, current course permissions are checked again before handing the
file to the response. Temporary spool files close with the download response;
no public download link or persistent archive is created. Responses use no-store.

Concurrent exports from the same account are rejected with 409 while the first
generation is in progress (process guard plus PostgreSQL session advisory lock).
The UI blocks duplicate clicks. A second tab must wait for the original download;
it does not receive a second copy of an in-progress archive. SQLite development
uses an in-process guard only; it does not provide cross-process deduplication.

This first implementation is synchronous and bounded. Django settings can
override the following defaults:

| Setting | Default |
| --- | --- |
| `RESEARCH_EXPORT_MAX_ROWS` | 100,000 raw + derived + issue records |
| `RESEARCH_EXPORT_MAX_BYTES` | 64 MiB of accumulated JSON data before compression |
| `RESEARCH_EXPORT_MAX_SECONDS` | 20 seconds of generation work |
| `RESEARCH_EXPORT_ID_KEY` | Django SECRET_KEY |

PostgreSQL statements additionally have a 15-second timeout within the snapshot.
Limits produce an error, never a truncated archive. Large scopes should be split
by course; background generation is not implemented. Ensure application and
proxy timeouts exceed the configured generation budget before using larger
limits. No server or deployment configuration is changed by this feature.

Participant IDs are HMAC-SHA256 pseudonyms over the domain user ID. Keep the
research key stable across exports to preserve participant linkage. Rotating
the fallback Django secret changes IDs; the key itself is never exported.

Current submissions are exported verbatim, including saved finalization answers,
but are not invented as historical versions. Comparison with the last recorded
answer is attempted only for a unique exact question/label match. Ambiguous or
missing data is reported. Feedback records do not prove that students read them,
or establish historical score visibility/provider provenance. Binary attachments
and never-recorded history are not included.

## Verification

Run with the project's Django test environment:

```text
python pigeonhole/manage.py test feedback.test_research_export feedback.test_ai_feedback_verification --noinput
```

The inter-connection advisory-lock test requires PostgreSQL and skips on SQLite.
Other tests cover permissions, identity options, unchanged raw text and hashes,
version/feedback selection, camelCase client requests, 125-record completeness,
current submissions, comments, duplicate requests, limits and permission revocation.

Implementation verification on 2026-09-15: 37 tests passed on isolated SQLite,
one PostgreSQL-only lock test skipped. Changed frontend files passed ESLint and
the frontend passed TypeScript checking. No live OpenAI call or deployment was
performed. PostgreSQL execution and browser download still require environment
verification; static checking is not an end-to-end browser test.
