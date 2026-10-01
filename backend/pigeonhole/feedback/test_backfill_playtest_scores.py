"""
@changelog
| Version | Description                                      | Reference                                   |
| v1.0.0  | Tests: backfill_playtest_scores command           | BUG: playtest-missing-score-json             |
/@changelog

@author chuckyang123
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from courses.models import SubmissionType
from .management.commands.backfill_playtest_scores import parse_scores
from .models import AIFeedbackRecord, FeedbackAnswerVersion
from .test_ai_feedback_verification import AIFeedbackBase

FEEDBACK = (
    "**Score: [79/100]**\n\n"
    "**Breakdown of Key Ingredients:**\n\n"
    "- **Specificity:** [4/10] – quotes the student.\n"
    "- **Constructive Criticism:** [2/10] – no suggestions.\n\n"
    "**Genre & Mechanic Evaluation (Knowledge Graph Score):**\n\n"
    "- **[18/50]** – mentions movement.\n\n"
    "**Professor Feedback:**\n\n- Good start.\n"
)


class ParseScoresTests(TestCase):
    def test_parses_total_breakdown_and_graph(self):
        self.assertEqual(
            parse_scores(FEEDBACK),
            {
                "total": 79,
                "breakdown": {"specificity": 4, "constructive_criticism": 2},
                "knowledge_graph": 18,
            },
        )

    def test_unfilled_placeholder_total_is_null(self):
        scores = parse_scores(FEEDBACK.replace("[79/100]", "[XX/100]"))
        self.assertIsNone(scores["total"])
        self.assertEqual(scores["knowledge_graph"], 18)

    def test_no_scores_returns_none(self):
        self.assertIsNone(parse_scores("plain text without scores"))
        self.assertIsNone(parse_scores(""))


class BackfillCommandTests(AIFeedbackBase):
    setUp = AIFeedbackBase.setUp

    def playtest_record(self, feedback_content=FEEDBACK, score_json=None):
        # Version numbers are unique per student/question, so each helper call
        # needs a fresh one.
        version_number = (
            FeedbackAnswerVersion.objects.filter(
                course=self.course, milestone=self.milestone,
                template=self.template, creator=self.student_membership,
                question="gameplay_feedback",
            ).count()
            + 1
        )
        version = FeedbackAnswerVersion.objects.create(
            course=self.course, milestone=self.milestone, template=self.template,
            submission=self.submission, creator=self.student_membership,
            name="Playtest", question="gameplay_feedback",
            answer_content="my answer", version_number=version_number,
        )
        return AIFeedbackRecord.objects.create(
            version=version,
            feedback_type=AIFeedbackRecord.FEEDBACK_TYPE_PLAYTEST,
            strategy=AIFeedbackRecord.STRATEGY_PLAYTEST,
            feedback_content=feedback_content,
            score_json=score_json,
        )

    def test_dry_run_does_not_write(self):
        record = self.playtest_record()
        out = StringIO()
        call_command("backfill_playtest_scores", stdout=out)

        record.refresh_from_db()
        self.assertIsNone(record.score_json)
        self.assertIn("dry run", out.getvalue())

    def test_apply_fills_and_skips_unparsable(self):
        record = self.playtest_record()
        blank = self.playtest_record(feedback_content="no scores here")
        out = StringIO()
        call_command("backfill_playtest_scores", "--apply", stdout=out)

        record.refresh_from_db()
        blank.refresh_from_db()
        self.assertEqual(record.score_json["total"], 79)
        self.assertEqual(record.score_json["knowledge_graph"], 18)
        self.assertIsNone(blank.score_json)
        self.assertIn("applied", out.getvalue())

    def test_already_filled_records_are_untouched(self):
        record = self.playtest_record(score_json={"total": 1, "breakdown": {}, "knowledge_graph": None})
        call_command("backfill_playtest_scores", "--apply", stdout=StringIO())

        record.refresh_from_db()
        self.assertEqual(record.score_json["total"], 1)

    def test_course_filter(self):
        record = self.playtest_record()
        call_command(
            "backfill_playtest_scores", "--apply", "--course-id", self.course.id + 1,
            stdout=StringIO(),
        )
        record.refresh_from_db()
        self.assertIsNone(record.score_json)
