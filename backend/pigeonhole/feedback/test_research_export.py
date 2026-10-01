"""Research ZIP permissions, completeness, evidence pairing and isolation tests."""
import hashlib
import io
import json
from datetime import timedelta
from unittest import mock, skipUnless
from zipfile import ZipFile

from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from courses.models import Course, CourseMembership, CourseSubmission, Role, Comment, CourseSubmissionComment, CourseMilestone
from users.models import User, AccountType
from .models import AIFeedbackRecord, FeedbackAnswerVersion, FeedbackInitialResponse
from .research_export import export_guard, ExportBusy, json_bytes, participant_id
from .test_ai_feedback_verification import AIFeedbackBase, jwt_client

URL = "/api/feedback/research-export/"


@override_settings(RESEARCH_EXPORT_MAX_SECONDS=60)
class ResearchExportTests(TransactionTestCase):
    setUp = AIFeedbackBase.setUp

    def version(self, answer, number, feedback="Explain the cause.", kind="REFLECTION", submission=None):
        version = FeedbackAnswerVersion.objects.create(
            course=self.course, milestone=self.milestone, template=self.template,
            submission=submission or self.submission, creator=self.student_membership,
            name="Reflection", question="Why?", answer_content=answer, version_number=number,
        )
        # Stable temporal ordering independent of database timestamp resolution.
        instant = timezone.now() - timedelta(days=1) + timedelta(minutes=number)
        FeedbackAnswerVersion.objects.filter(pk=version.pk).update(created_at=instant)
        if feedback is not None:
            record = AIFeedbackRecord.objects.create(
                version=version, feedback_type=kind, strategy="BASIC", feedback_content=feedback,
                score_json={"stage_1": 1}, model_version="test-model",
                token_usage_json={"prompt_tokens": 7}, latency_ms=10,
            )
            AIFeedbackRecord.objects.filter(pk=record.pk).update(created_at=instant + timedelta(seconds=1))
        version.refresh_from_db()
        return version

    def download(self, user=None, **params):
        return jwt_client(user or self.educator).post(URL, params or {"course_id": self.course.id}, format="json")

    def unpack(self, response):
        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        try:
            archive = ZipFile(io.BytesIO(b"".join(response.streaming_content)))
            files = {}
            for name in archive.namelist():
                body = archive.read(name)
                files[name] = [json.loads(line) for line in body.splitlines()] if name.endswith(".jsonl") else body
            manifest = json.loads(files["manifest.json"])
            for name, item in manifest["files"].items():
                body = archive.read(name)
                self.assertEqual(item["bytes"], len(body))
                self.assertEqual(item["sha256"], hashlib.sha256(body).hexdigest())
                if "records" in item:
                    self.assertEqual(item["records"], len(files[name]))
            return files
        finally:
            response.close()

    def test_complete_archive_preserves_text_metadata_pairs_and_latest_submission(self):
        original = '第一版\n"保持原文" 😀'
        first = self.version(original, 1, "说明具体原因。")
        second = self.version("我没有确认分工。", 3, "CURRENT feedback must not be used")
        self.version("playtest", 4, kind="PLAYTEST")
        self.submission.form_response_data = [{"label": "Why?", "response": "最终保存", "finalizationReason": "我已理解"}]
        self.submission.save()
        FeedbackInitialResponse.objects.create(course=self.course, creator=self.student_membership, name="R", question="Why?", initial_response=original)
        with mock.patch("openai.OpenAI", side_effect=AssertionError("Export must not call AI")):
            response = self.download()
        self.assertEqual(response["Cache-Control"], "no-store, private")
        files = self.unpack(response)
        self.assertNotIn("identity/identity_map.jsonl", files)
        self.assertEqual(len(files["data/answer_versions.jsonl"]), 3)
        self.assertEqual(len(files["data/ai_feedback_records.jsonl"]), 3)
        self.assertEqual(files["data/answer_versions.jsonl"][0]["answer_content"], original)
        self.assertEqual(files["data/initial_responses.jsonl"][0]["initial_response"], original)
        self.assertEqual(files["data/ai_feedback_records.jsonl"][0]["score_json"], {"stage_1": 1})
        self.assertEqual(files["data/submissions.jsonl"][0]["form_response_data"], self.submission.form_response_data)
        pairs = files["derived/reflection_pairs.jsonl"]
        self.assertEqual(pairs[0]["reason_code"], "no_previous_version")
        pair = pairs[1]
        self.assertEqual(pair["eligibility"], "ready")
        self.assertEqual(pair["previous_version_id"], str(first.id))
        self.assertEqual(pair["current_version_id"], str(second.id))
        self.assertEqual(pair["previous_feedback"], "说明具体原因。")
        content = {key: pair[key] for key in ("question", "previous_answer", "current_answer", "previous_feedback", "selection_rule_version")}
        self.assertEqual(pair["input_hash"], hashlib.sha256(json_bytes(content)).hexdigest())
        self.assertTrue(any(row["code"] == "current_submission_differs" for row in files["quality/data_issues.jsonl"]))
        members = files["data/memberships.jsonl"]
        self.assertTrue(all("user_id" not in row and "email" not in row for row in members))

    def test_identity_is_opt_in_and_ids_stable(self):
        first = self.unpack(self.download())
        second = self.unpack(self.download(course_id=self.course.id, include_identity=True))
        self.assertEqual(first["data/memberships.jsonl"], second["data/memberships.jsonl"])
        identity = second["identity/identity_map.jsonl"]
        self.assertTrue(any(row["participant_id"] == participant_id(self.student.id) and row["email"] == self.student.email for row in identity))

    def test_students_and_unrelated_educators_denied(self):
        self.assertEqual(self.download(self.student).status_code, 403)
        outsider = User.objects.create(email="outside@example.com", account_type=AccountType.EDUCATOR, is_activated=True)
        self.assertEqual(self.download(outsider).status_code, 403)

    def test_standard_instructor_can_export(self):
        instructor = User.objects.create(email="invited@example.com", account_type=AccountType.STANDARD, is_activated=True)
        CourseMembership.objects.create(course=self.course, user=instructor, role=Role.INSTRUCTOR)
        self.unpack(self.download(instructor))

    def test_all_scope_filters_unauthorized_courses_and_admin_can_export_all(self):
        outside = User.objects.create(email="other@example.com", is_activated=True)
        other_course = Course.objects.create(owner=outside, name="Private", is_published=True)
        files = self.unpack(self.download(scope="all"))
        self.assertEqual([row["id"] for row in files["data/courses.jsonl"]], [str(self.course.id)])
        self.educator.account_type = AccountType.ADMIN
        self.educator.save()
        files = self.unpack(self.download(scope="all"))
        self.assertEqual({row["id"] for row in files["data/courses.jsonl"]}, {str(self.course.id), str(other_course.id)})

    def test_missing_feedback_not_skipped_and_same_text_is_no_change(self):
        self.version("same", 1)
        self.version("same", 2)
        self.version("missing", 3, feedback=None)
        self.version("last", 4)
        files = self.unpack(self.download())
        pairs = files["derived/reflection_pairs.jsonl"]
        self.assertEqual(pairs[1]["eligibility"], "no_change")
        self.assertEqual(pairs[2]["reason_code"], "missing_previous_feedback")

    def test_late_feedback_not_selected(self):
        first = self.version("one", 1)
        second = self.version("two", 2)
        first.feedback_records.update(created_at=second.created_at + timedelta(hours=1))
        files = self.unpack(self.download())
        self.assertEqual(files["derived/reflection_pairs.jsonl"][1]["reason_code"], "missing_previous_feedback")

    def test_different_submissions_do_not_pair(self):
        self.version("one", 1)
        other = CourseSubmission.objects.get(pk=self.submission.pk)
        other.pk = None
        other.save()
        self.version("two", 2, submission=other)
        files = self.unpack(self.download())
        self.assertTrue(all(row["reason_code"] == "no_previous_version" for row in files["derived/reflection_pairs.jsonl"]))

    def test_missing_context_retained_with_issue(self):
        version = self.version("orphan", 1)
        FeedbackAnswerVersion.objects.filter(pk=version.pk).update(submission=None)
        files = self.unpack(self.download())
        self.assertEqual(len(files["data/answer_versions.jsonl"]), 1)
        self.assertEqual(files["derived/reflection_pairs.jsonl"][0]["reason_code"], "missing_context")

    @override_settings(RESEARCH_EXPORT_MAX_ROWS=1)
    def test_limit_returns_error_not_partial_archive(self):
        response = self.download()
        self.assertEqual(response.status_code, 413)
        self.assertFalse(response.streaming)

    def test_duplicate_export_does_not_build_again(self):
        with export_guard(self.educator.id), mock.patch("feedback.research_export.build_archive") as build:
            self.assertEqual(self.download().status_code, 409)
            build.assert_not_called()

    def test_permission_rechecked_before_download(self):
        from .research_export import derive
        def revoke(*args):
            result = derive(*args)
            CourseMembership.objects.filter(user=self.educator).delete()
            Course.objects.filter(pk=self.course.id).update(owner=self.student)
            return result
        with mock.patch("feedback.research_export.derive", side_effect=revoke):
            self.assertEqual(self.download().status_code, 403)

    def test_strict_scope_validation(self):
        self.assertEqual(self.download(scope="all", course_id=self.course.id).status_code, 400)

    def test_more_than_one_page_exported(self):
        FeedbackAnswerVersion.objects.bulk_create([
            FeedbackAnswerVersion(course=self.course, milestone=self.milestone,
                                  template=self.template, submission=self.submission,
                                  creator=self.student_membership, name="R", question="Why?",
                                  answer_content="完整原文 " + str(i), version_number=i)
            for i in range(1, 126)
        ])
        files = self.unpack(self.download())
        self.assertEqual(len(files["data/answer_versions.jsonl"]), 125)
        self.assertEqual(len([row for row in files["quality/data_issues.jsonl"] if row["code"] == "unknown_feedback_type"]), 125)

    def test_comment_context_and_deleted_content(self):
        comment = Comment.objects.create(content="Specific evidence", commenter=self.educator, is_deleted=False)
        CourseSubmissionComment.objects.create(submission=self.submission, comment=comment, field_index=0, member=self.teacher_membership)
        files = self.unpack(self.download())
        self.assertEqual(files["data/comments.jsonl"][0]["content"], "Specific evidence")
        self.assertNotIn("commenter_id", files["data/comments.jsonl"][0])
        comment.is_deleted = True
        comment.save()
        files = self.unpack(self.download())
        self.assertIsNone(files["data/comments.jsonl"][0]["content"])

    def test_inconsistent_submission_context_not_ready(self):
        self.version("first", 1)
        second = self.version("second", 2)
        milestone = CourseMilestone.objects.create(course=self.course, name="Other", is_published=True, start_date_time=timezone.now())
        FeedbackAnswerVersion.objects.filter(pk=second.pk).update(milestone=milestone)
        files = self.unpack(self.download())
        pair = next(row for row in files["derived/reflection_pairs.jsonl"] if row["current_version_id"] == str(second.id))
        self.assertEqual(pair["reason_code"], "missing_context")

    def test_camel_case_request_from_frontend(self):
        response = jwt_client(self.educator).post(URL, {"scope": "course", "courseId": self.course.id, "includeIdentity": True}, format="json")
        self.assertIn("identity/identity_map.jsonl", self.unpack(response))

    def test_get_cannot_start_export(self):
        response = jwt_client(self.educator).get(URL)
        self.assertEqual(response.status_code, 405)

    @skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL for inter-worker locking")
    def test_postgres_lock_blocks_another_connection(self):
        import psycopg2
        params = connection.get_connection_params()
        lock_key = int.from_bytes(hashlib.sha256(f"research-export:{self.educator.id}".encode()).digest()[:8], "big", signed=True)
        with export_guard(self.educator.id):
            other = psycopg2.connect(**params)
            try:
                with other.cursor() as cursor:
                    cursor.execute("SELECT pg_try_advisory_lock(%s)", [lock_key])
                    self.assertFalse(cursor.fetchone()[0])
            finally:
                other.close()
