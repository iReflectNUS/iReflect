"""
@changelog
| Version | Description                                      | Reference                                   |
| v1.0.0  | Skeleton: milestone Excel export endpoint view   | REQ: 20260929-Excel导出功能升级 TECH: 04_design_tech-design.md §3.1-§3.5 |
| v1.1.0  | Full pipeline: snapshot + 2-sheet xlsx + limits  | REQ: 20260929-Excel导出功能升级 TECH: 04_design_tech-design.md §3.4 |
|         | (Submissions sheet + AI Feedback History sheet)  |                                             |
| v1.2.0  | Add Auto-Generated Questions sheet: surfaces the | REQ: 20261007-auto-question-excel            |
|         | auto-generated reflective question + student ans |                                             |
|         | wer (FeedbackInitialResponse) + AI feedback.     |                                             |
/@changelog

@author chuckyang123
"""
import json
import logging
import tempfile
import time
from datetime import datetime, timezone

from django.conf import settings
from django.db import connection, transaction, OperationalError
from django.http import FileResponse
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.views import APIView

from courses.models import CourseMilestone, CourseMilestoneTemplate, CourseSubmission
from users.models import User
from .models import AIFeedbackRecord, FeedbackInitialResponse
from .research_export import ExportLimit, allowed_courses, export_guard

logger = logging.getLogger("main")
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CELL_TEXT_LIMIT = 32767
TRUNCATION_SUFFIX = "\n[Truncated; full text in AI Feedback History]"
SUBMISSIONS_SHEET = "Submissions"
FEEDBACK_SHEET = "AI Feedback History"
AUTO_GEN_QUESTION_SHEET = "Auto-Generated Questions"
# The reflective question auto-generated for students. Its answer is captured via
# the playtest/feedback flow (FeedbackInitialResponse) rather than a plain form
# column, so it is surfaced on its own sheet. Match is case-insensitive + trimmed.
TARGET_QUESTION_TEXT = (
    "In the previous interaction with AI feedback, why did you stop "
    "generating further feedback and finalize it?"
)
AUTO_GEN_QUESTION_HEADER = [
    "Student ID", "Student Name", "Student Email", "Group", "Submission ID",
    "Submission Name", "Question", "Student Answer", "AI Feedback",
]
SUBMISSION_HEADER = [
    "Student ID", "Student Name", "Student Email", "Group", "Submission ID",
    "Submission Name", "Submission Type", "Status", "Created At (UTC)",
    "Updated At (UTC)", "Last Editor",
]
FEEDBACK_HEADER = [
    "Record ID", "Student ID", "Student Name", "Student Email", "Group",
    "Submission ID", "Question", "Version Number", "Answer At Version",
    "Initial Response", "Feedback Type", "Strategy", "Model", "Prompt Tokens",
    "Completion Tokens", "Total Tokens", "Latency (ms)", "Feedback Created At (UTC)",
    "Feedback Content", "Score JSON",
]


class MilestoneExportRequest(serializers.Serializer):
    """POST /milestone-export/ body: course_id + milestone_id (both required)."""

    course_id = serializers.IntegerField(min_value=1)
    milestone_id = serializers.IntegerField(min_value=1)


class ExcelLimit:
    """Row/time guard so a runaway export fails with 413 instead of a half file."""

    def __init__(self):
        self.started = time.monotonic()
        self.rows = 0

    def check(self, rows=1):
        self.rows += rows
        if (self.rows > getattr(settings, "EXCEL_EXPORT_MAX_ROWS", 100000)
                or time.monotonic() - self.started > getattr(settings, "EXCEL_EXPORT_MAX_SECONDS", 30)):
            raise ExportLimit(
                "This milestone export exceeds the synchronous export limit. "
                "No partial workbook was produced."
            )


def cell_text(value):
    """Coerce a form response/answer into a single safe spreadsheet cell."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = "; ".join(str(item) for item in value if item is not None)
    elif not isinstance(value, str):
        value = str(value)
    # openpyxl rejects control characters that Excel cannot store.
    value = ILLEGAL_CHARACTERS_RE.sub("", value)
    if len(value) > CELL_TEXT_LIMIT:
        value = value[: CELL_TEXT_LIMIT - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX
    return value


def iso_utc(value):
    return value.astimezone(timezone.utc).isoformat() if value is not None else None


def snapshot_milestone(course_id, milestone_id):
    """Materialize every queryset inside one repeatable-read snapshot, then exit
    the transaction before any workbook writing happens (ADR-3)."""
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '15000ms'")
        milestone = CourseMilestone.objects.filter(pk=milestone_id, course_id=course_id).first()
        if milestone is None:
            raise PermissionDenied("The milestone does not belong to this course.")
        submissions = list(
            CourseSubmission.objects
            .filter(course_id=course_id, milestone=milestone)
            .select_related("creator__user", "editor__user", "group", "template")
            .order_by("creator__user_id", "created_at", "id")
        )
        template_ids = {s.template_id for s in submissions if s.template_id}
        templates = list(
            CourseMilestoneTemplate.objects
            .filter(course_id=course_id, id__in=template_ids)
            .select_related("form")
            .order_by("id")
        )
        feedbacks = list(
            AIFeedbackRecord.objects
            .filter(version__course_id=course_id, version__milestone=milestone)
            .select_related(
                "version", "version__creator__user",
                "version__submission", "version__submission__group",
            )
        )
        initials = list(
            FeedbackInitialResponse.objects.filter(course_id=course_id, milestone=milestone)
        )
    return milestone, submissions, templates, feedbacks, initials


def template_labels(templates):
    """Dynamic column headers: every labelled form field, in template order,
    matching what the frontend renders (ADR-4). Fields stored without a label
    fall back to their question so no answer column is silently dropped."""
    labels = []
    for template in templates:
        fields = template.form.form_field_data
        for field in fields if isinstance(fields, list) else []:
            if isinstance(field, dict):
                # Label is what the frontend renders; fall back to question for
                # field types stored without a label (e.g. TEXT_DISPLAY).
                label = field.get("label") or field.get("question")
                if label and label not in labels:
                    labels.append(label)
    return labels


def response_value(form_response_data, label):
    if not isinstance(form_response_data, list):
        return None
    for entry in form_response_data:
        if isinstance(entry, dict) and (entry.get("label") or entry.get("question")) == label:
            return entry.get("response")
    return None


def student_columns(membership, group):
    """GROUP submissions present the group name in the name/email identity
    columns (design §3.4) while keeping the submitter id as the join key;
    individual submissions show the creator user."""
    user = membership.user if membership is not None else None
    student_id = user.id if user is not None else None
    if group is not None:
        return student_id, group.name, group.name
    return (
        student_id,
        user.name if user is not None else None,
        user.email if user is not None else None,
    )


def token_usage(usage):
    """Tolerate snake_case and camelCase token keys; never raise on odd JSON
    (lesson DBG-003: use .get() fallbacks for batch row processing)."""
    if not isinstance(usage, dict):
        usage = {}
    prompt = usage.get("prompt_tokens", usage.get("promptTokens"))
    completion = usage.get("completion_tokens", usage.get("completionTokens"))
    total = usage.get("total_tokens", usage.get("totalTokens"))
    return prompt, completion, total


def build_workbook(user, course_id, milestone_id):
    """Build the two-sheet workbook and return (spooled file, limiter stats)."""
    limiter = ExcelLimit()
    milestone, submissions, templates, feedbacks, initials = snapshot_milestone(
        course_id, milestone_id
    )
    # Check the row budget before openpyxl allocates its temp files, so an
    # oversized milestone fails with 413 instead of leaving a half workbook.
    limiter.check(rows=len(submissions) + len(feedbacks))
    labels = template_labels(templates)
    initial_by_key = {
        (row.creator_id, row.question): row.initial_response
        for row in initials
        if row.creator_id is not None
    }

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(SUBMISSIONS_SHEET)
    sheet.append(SUBMISSION_HEADER + labels)
    for submission in submissions:
        limiter.check(rows=0)
        group_name = submission.group.name if submission.group is not None else None
        student_id, student_name, student_email = student_columns(submission.creator, submission.group)
        editor_name = (
            submission.editor.user.name
            if submission.editor is not None and submission.editor.user is not None
            else None
        )
        row = [
            student_id, cell_text(student_name), cell_text(student_email), cell_text(group_name),
            submission.id, cell_text(submission.name), submission.submission_type,
            "Draft" if submission.is_draft else "Submitted",
            iso_utc(submission.created_at), iso_utc(submission.updated_at), cell_text(editor_name),
        ]
        row += [cell_text(response_value(submission.form_response_data, label)) for label in labels]
        sheet.append(row)

    sheet = workbook.create_sheet(FEEDBACK_SHEET)
    sheet.append(FEEDBACK_HEADER)
    # Student -> Question -> Version -> Record (design §3.4 ordering).
    feedbacks.sort(
        key=lambda record: (
            record.version.creator.user_id if record.version.creator is not None else 0,
            record.version.question,
            record.version.version_number,
            record.id,
        )
    )
    for record in feedbacks:
        limiter.check(rows=0)
        version = record.version
        membership = version.creator
        group = version.submission.group if version.submission is not None else None
        student_id, student_name, student_email = student_columns(membership, group)
        prompt, completion, total = token_usage(record.token_usage_json)
        row = [
            record.id, student_id, cell_text(student_name), cell_text(student_email),
            cell_text(group.name if group is not None else None),
            version.submission_id, cell_text(version.question), version.version_number,
            cell_text(version.answer_content),
            cell_text(initial_by_key.get((membership.id if membership is not None else None, version.question))),
            record.feedback_type, record.strategy, cell_text(record.model_version),
            prompt, completion, total, record.latency_ms, iso_utc(record.created_at),
            cell_text(record.feedback_content),
            cell_text(json.dumps(record.score_json, ensure_ascii=False)) if record.score_json is not None else None,
        ]
        sheet.append(row)

    # --- Auto-Generated Questions sheet ---------------------------------------
    # The auto-generated reflective question (e.g. "Why did you stop ...?") is
    # answered through the playtest/feedback flow, so its answer lands in
    # FeedbackInitialResponse (and the AI reply in AIFeedbackRecord) rather than a
    # plain form column. Surface it on its own sheet for quick review. Only build
    # the sheet when at least one template in this milestone actually contains the
    # target question, so unrelated exports are not given an empty sheet.
    target = TARGET_QUESTION_TEXT.strip().lower()
    template_target = {}
    for template in templates:
        fields = template.form.form_field_data
        for field in fields if isinstance(fields, list) else []:
            if not isinstance(field, dict):
                continue
            field_question = (field.get("label") or field.get("question") or "").strip().lower()
            if field_question == target:
                template_target[template.id] = field.get("label") or field.get("question")
                break

    if template_target:
        initial_norm = {
            (row.creator_id, (row.question or "").strip().lower()): row.initial_response
            for row in initials
            if row.creator_id is not None
        }
        feedback_by_submission = {}
        for record in feedbacks:
            feedback_by_submission.setdefault(record.version.submission_id, []).append(record)

        sheet = workbook.create_sheet(AUTO_GEN_QUESTION_SHEET)
        sheet.append(AUTO_GEN_QUESTION_HEADER)
        for submission in submissions:
            limiter.check(rows=0)
            question_text = template_target.get(submission.template_id)
            if question_text is None:
                continue
            group_name = submission.group.name if submission.group is not None else None
            student_id, student_name, student_email = student_columns(submission.creator, submission.group)
            membership = submission.creator
            member_id = membership.id if membership is not None else None
            student_answer = response_value(submission.form_response_data, question_text)
            if student_answer is None:
                student_answer = initial_norm.get((member_id, target))
            ai_feedback = None
            for record in feedback_by_submission.get(submission.id, []):
                if (record.version.question or "").strip().lower() == target:
                    ai_feedback = record.feedback_content
                    break
            sheet.append([
                student_id, cell_text(student_name), cell_text(student_email),
                cell_text(group_name), submission.id, cell_text(submission.name),
                cell_text(question_text), cell_text(student_answer), cell_text(ai_feedback),
            ])

    # Recheck permissions outside the repeatable-read snapshot, mirroring
    # research_export: a revoked instructor must not receive the file.
    fresh_user = User.objects.get(pk=user.pk)
    if not fresh_user.is_activated or not allowed_courses(fresh_user).filter(pk=course_id).exists():
        raise PermissionDenied("Export permission changed. Please try again.")

    output = tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024, mode="w+b")
    try:
        workbook.save(output)
    except Exception:
        output.close()
        raise
    limiter.check(rows=0)
    return output, limiter


class MilestoneExcelExportView(APIView):
    """Per-milestone Excel export for teachers: Sheet 1 is the current
    submissions snapshot with dynamic form columns; Sheet 2 is the full AI
    feedback history, one row per feedback record with its answer version;
    Sheet 3 (Auto-Generated Questions) surfaces the auto-generated reflective
    question plus each student's answer and the AI reply, when present."""

    def post(self, request):
        # JWTTokenUserAuthentication returns a token user, not our domain User.
        user = User.objects.filter(pk=request.user.id, is_activated=True).first()
        if user is None:
            raise PermissionDenied()
        serializer = MilestoneExportRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data
        # Fail before acquiring the export lock for unauthorized requests.
        if not allowed_courses(user).filter(pk=params["course_id"]).exists():
            raise PermissionDenied("No permission to export this course.")
        try:
            with export_guard(user.pk):
                output, limiter = build_workbook(user, params["course_id"], params["milestone_id"])
        except OperationalError:
            logger.warning(
                "Milestone Excel export database unavailable user=%s course=%s milestone=%s",
                user.pk, params["course_id"], params["milestone_id"],
            )
            error = APIException("The export could not finish reading the database. Please try again.")
            error.status_code = 503
            raise error
        except Exception as exc:
            logger.warning(
                "Milestone Excel export failed user=%s course=%s milestone=%s error_type=%s",
                user.pk, params["course_id"], params["milestone_id"], type(exc).__name__,
            )
            raise
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output.seek(0)
        response = FileResponse(
            output,
            as_attachment=True,
            filename=f"ireflect-{params['course_id']}-{params['milestone_id']}-{timestamp}.xlsx",
            content_type=XLSX_MIME,
        )
        response["Cache-Control"] = "no-store, private"
        response["X-Content-Type-Options"] = "nosniff"
        logger.info(
            "Milestone Excel export completed user=%s course=%s milestone=%s rows=%s seconds=%.2f",
            user.pk, params["course_id"], params["milestone_id"],
            limiter.rows, time.monotonic() - limiter.started,
        )
        return response
