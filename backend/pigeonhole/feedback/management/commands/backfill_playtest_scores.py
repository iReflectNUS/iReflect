"""
@changelog
| Version | Description                          | Reference                                   |
| v1.0.0  | Initial implementation: backfill score_json for playtest records | BUG: playtest-missing-score-json |
|         | by re-parsing the stored LightRAG score block          |                                             |
/@changelog

@author chuckyang123
"""
import re

from django.core.management.base import BaseCommand

from ...models import AIFeedbackRecord

# Mirrors parsePlaytestScores() in frontend/src/utils/playtest-score-utils.ts
# so historical records get the same shape as newly reported ones.
TOTAL_PATTERN = re.compile(r"\*\*Score:\s*\[(\d+)\s*/\s*\d+\]\*\*")
GRAPH_PATTERN = re.compile(r"\*\*\[(\d+)\s*/\s*\d+\]\*\*")
INGREDIENT_PATTERN = re.compile(
    r"^[-*]\s+\*\*([^:*]+):\*\*\s*\[(\d+)\s*/\s*\d+\]", re.MULTILINE
)


def score_key(label):
    return re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")


def parse_scores(markdown):
    """Return {total, breakdown, knowledge_graph} or None when unparsable."""
    if not markdown:
        return None
    total_match = TOTAL_PATTERN.search(markdown)
    graph_match = GRAPH_PATTERN.search(markdown)
    breakdown = {
        score_key(label): int(value)
        for label, value in INGREDIENT_PATTERN.findall(markdown)
    }
    if total_match is None and graph_match is None and not breakdown:
        return None
    return {
        "total": int(total_match.group(1)) if total_match else None,
        "breakdown": breakdown,
        "knowledge_graph": int(graph_match.group(1)) if graph_match else None,
    }


class Command(BaseCommand):
    """Backfill score_json for playtest records created before the frontend
    started reporting parsed scores.

    Dry-run by default (prints what would change); pass --apply to write.
    Only records whose score_json is still null are touched, so the command is
    idempotent and safe to re-run.
    """

    help = "Backfill score_json for playtest AI feedback records by re-parsing feedback_content."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run).")
        parser.add_argument("--course-id", type=int, help="Restrict to a single course id.")

    def handle(self, *args, **options):
        records = AIFeedbackRecord.objects.filter(
            feedback_type=AIFeedbackRecord.FEEDBACK_TYPE_PLAYTEST,
            score_json__isnull=True,
        ).select_related("version")
        if options.get("course_id"):
            records = records.filter(version__course_id=options["course_id"])

        filled = 0
        unparsable = 0
        for record in records.order_by("id"):
            scores = parse_scores(record.feedback_content)
            if scores is None:
                unparsable += 1
                continue
            if options["apply"]:
                AIFeedbackRecord.objects.filter(pk=record.pk).update(score_json=scores)
            filled += 1

        mode = "applied" if options["apply"] else "dry run"
        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill {mode}: {filled} record(s) with scores, "
                f"{unparsable} without parsable scores."
            )
        )
