"""Teacher-only, point-in-time research archives. No AI/provider dependencies."""
import hashlib
import hmac
import json
import logging
import tempfile
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.db import connection, transaction, OperationalError
from django.db.models import Q
from django.http import FileResponse
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.views import APIView

from courses.models import (
    Course, CourseSettings, CourseMembership, CourseGroup, CourseGroupMember,
    CourseMilestone, CourseMilestoneTemplate, CourseSubmission,
    CourseSubmissionComment, Role,
)
from users.models import AccountType, User
from .models import FeedbackInitialResponse, FeedbackAnswerVersion, AIFeedbackRecord

logger = logging.getLogger("main")
SCHEMA_VERSION = "1.0"
SELECTION_VERSION = "1.0"
_local_lock = Lock()
_active = set()


class ExportBusy(APIException):
    status_code = 409
    default_detail = "An export for this account is already running. Please wait before trying again."


class ExportLimit(APIException):
    status_code = 413
    default_detail = "This export exceeds the synchronous export limit. Export one course at a time. No partial archive was produced."


class ExportRequest(serializers.Serializer):
    scope = serializers.ChoiceField(choices=["course", "all"], default="course")
    course_id = serializers.IntegerField(min_value=1, required=False)
    include_identity = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if attrs["scope"] == "course" and "course_id" not in attrs:
            raise serializers.ValidationError("course_id is required for a course export.")
        if attrs["scope"] == "all" and "course_id" in attrs:
            raise serializers.ValidationError("Do not supply course_id with scope=all.")
        return attrs


def allowed_courses(user):
    if user.account_type == AccountType.ADMIN:
        return Course.objects.all()
    return Course.objects.filter(
        Q(owner=user) | Q(coursemembership__user=user,
                          coursemembership__role__in=[Role.INSTRUCTOR, Role.CO_OWNER])
    ).distinct()


def selected_courses(user, params):
    courses = allowed_courses(user)
    if params["scope"] == "course":
        courses = courses.filter(pk=params["course_id"])
    ids = list(courses.order_by("id").values_list("id", flat=True))
    if not ids:
        raise PermissionDenied("No permission to export the requested courses.")
    return ids


def participant_id(user_id):
    if user_id is None:
        return None
    # Stable while the server signing key is stable; never export that key.
    key = str(getattr(settings, "RESEARCH_EXPORT_ID_KEY", settings.SECRET_KEY)).encode()
    return "p_" + hmac.new(key, f"ireflect-research-v1:{user_id}".encode(), hashlib.sha256).hexdigest()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def value_json(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def serialize(obj, fields):
    result = {}
    for name in ["id", "created_at", "updated_at", *fields.split()]:
        value = getattr(obj, name)
        result[name] = str(value) if value is not None and (name == "id" or name.endswith("_id")) else value_json(value)
    return result


@contextmanager
def export_guard(user_id):
    """Bound duplicate work in each process and across PostgreSQL workers."""
    with _local_lock:
        if user_id in _active:
            raise ExportBusy()
        _active.add(user_id)
    try:
        if connection.vendor == "postgresql":
            # Session lock survives snapshot commit and is always released below.
            key = int.from_bytes(hashlib.sha256(f"research-export:{user_id}".encode()).digest()[:8], "big", signed=True)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", [key])
                acquired = cursor.fetchone()[0]
            if not acquired:
                raise ExportBusy()
            try:
                yield
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [key])
        else:
            yield
    finally:
        with _local_lock:
            _active.discard(user_id)


class ArchiveBuilder:
    def __init__(self):
        self.started = time.monotonic()
        self.rows = 0
        self.bytes = 0

    def check(self, rows=0, size=0):
        self.rows += rows
        self.bytes += size
        if (self.rows > getattr(settings, "RESEARCH_EXPORT_MAX_ROWS", 100000)
                or self.bytes > getattr(settings, "RESEARCH_EXPORT_MAX_BYTES", 64 * 1024 * 1024)
                or time.monotonic() - self.started > getattr(settings, "RESEARCH_EXPORT_MAX_SECONDS", 20)):
            raise ExportLimit()

    def collect(self, queryset, fields):
        rows = []
        for obj in queryset.order_by("id").iterator(chunk_size=500):
            row = serialize(obj, fields)
            self.check(rows=1, size=len(json_bytes(row)))
            rows.append(row)
        return rows


def collect_data(builder, course_ids, include_identity):
    data = {}
    specs = [
        ("courses", Course.objects.filter(id__in=course_ids), "owner_id name description is_published"),
        ("course_settings", CourseSettings.objects.filter(course_id__in=course_ids),
         "course_id show_group_members_names allow_students_to_create_groups allow_students_to_delete_groups allow_students_to_join_groups allow_students_to_leave_groups allow_students_to_modify_group_name allow_students_to_add_or_remove_group_members milestone_alias show_ai_score"),
        ("memberships", CourseMembership.objects.filter(course_id__in=course_ids), "user_id course_id role"),
        ("groups", CourseGroup.objects.filter(course_id__in=course_ids), "course_id name"),
        ("group_members", CourseGroupMember.objects.filter(group__course_id__in=course_ids), "member_id group_id"),
        ("milestones", CourseMilestone.objects.filter(course_id__in=course_ids), "course_id name description start_date_time end_date_time is_published"),
        ("templates", CourseMilestoneTemplate.objects.filter(course_id__in=course_ids), "course_id form_id description submission_type is_published"),
        ("submissions", CourseSubmission.objects.filter(course_id__in=course_ids), "course_id milestone_id group_id template_id creator_id editor_id name description is_draft submission_type form_response_data"),
        ("initial_responses", FeedbackInitialResponse.objects.filter(course_id__in=course_ids), "course_id milestone_id template_id creator_id name question initial_response genre mechanic"),
        ("answer_versions", FeedbackAnswerVersion.objects.filter(course_id__in=course_ids), "course_id milestone_id template_id submission_id creator_id name question answer_content version_number genre mechanic"),
        ("ai_feedback_records", AIFeedbackRecord.objects.filter(version__course_id__in=course_ids), "version_id feedback_type strategy score_json feedback_content model_version token_usage_json latency_ms idempotency_key"),
    ]
    for name, queryset, fields in specs:
        data[name] = builder.collect(queryset, fields)
    from forms.models import Form
    data["forms"] = builder.collect(Form.objects.filter(coursemilestonetemplate__course_id__in=course_ids), "name form_field_data")
    # Include existing educator comments as research context, without deleted bodies.
    links = CourseSubmissionComment.objects.filter(submission__course_id__in=course_ids)
    data["submission_comments"] = builder.collect(links, "submission_id comment_id field_index member_id")
    from courses.models import Comment
    data["comments"] = builder.collect(Comment.objects.filter(coursesubmissioncomment__in=links).distinct(), "content is_deleted commenter_id")
    users = set()
    for row in data["courses"]:
        users.add(int(row["owner_id"]))
        row["owner_participant_id"] = participant_id(row.pop("owner_id"))
    for row in data["memberships"]:
        users.add(int(row["user_id"]))
        row["participant_id"] = participant_id(row.pop("user_id"))
    for row in data["comments"]:
        user_id = row.pop("commenter_id")
        if user_id:
            users.add(int(user_id))
        row["commenter_participant_id"] = participant_id(user_id)
        if row["is_deleted"]:
            row["content"] = None
    if include_identity:
        identity = []
        for user in User.objects.filter(id__in=users).order_by("id").iterator():
            row = {"participant_id": participant_id(user.id), "name": user.name, "email": user.email}
            builder.check(rows=1, size=len(json_bytes(row)))
            identity.append(row)
        data["identity_map"] = identity
    return data


RELATIONS = {
    "course_id": "courses", "milestone_id": "milestones", "template_id": "templates",
    "submission_id": "submissions", "creator_id": "memberships", "editor_id": "memberships",
    "member_id": "memberships", "group_id": "groups", "form_id": "forms",
    "version_id": "answer_versions", "comment_id": "comments",
}


def derive(data, builder):
    indexes = {name: {row["id"]: row for row in rows if "id" in row} for name, rows in data.items()}
    issues = []
    invalid = set()

    def issue(code, table, row_id, **extra):
        entry = {"code": code, "table": table, "record_id": row_id, **extra}
        builder.check(rows=1, size=len(json_bytes(entry)))
        issues.append(entry)

    for table, rows in data.items():
        for row in rows:
            for field, target in RELATIONS.items():
                if field not in row:
                    continue
                ref = row[field]
                linked = indexes.get(target, {}).get(ref)
                if ref is None:
                    issue("null_relation", table, row.get("id"), field=field)
                elif linked is None:
                    issue("missing_relation", table, row.get("id"), field=field, target_id=ref)
                    invalid.add((table, row.get("id")))
                elif row.get("course_id") and linked.get("course_id") and row["course_id"] != linked["course_id"]:
                    issue("cross_course_relation", table, row.get("id"), field=field)
                    invalid.add((table, row.get("id")))

    for version in data["answer_versions"]:
        submission = indexes["submissions"].get(version["submission_id"])
        if submission and any(version[key] != submission[key] for key in ("course_id", "milestone_id", "template_id")):
            issue("submission_context_mismatch", "answer_versions", version["id"])
            invalid.add(("answer_versions", version["id"]))

    feedback = defaultdict(list)
    for record in data["ai_feedback_records"]:
        feedback[record["version_id"]].append(record)
    grouped = defaultdict(list)
    keys = ("course_id", "creator_id", "submission_id", "milestone_id", "template_id", "question")
    for version in data["answer_versions"]:
        grouped[tuple(version[k] for k in keys)].append(version)
    pairs = []
    for versions in grouped.values():
        versions.sort(key=lambda row: (row["version_number"], int(row["id"])))
        previous = None
        for current in versions:
            own = feedback[current["id"]]
            if not any(row["feedback_type"] == "REFLECTION" for row in own):
                if not own:
                    issue("unknown_feedback_type", "answer_versions", current["id"])
                previous = current
                continue
            reason = None
            chosen = None
            if any(current[k] is None for k in keys[:-1]) or ("answer_versions", current["id"]) in invalid:
                reason = "missing_context"
            elif previous is None:
                reason = "no_previous_version"
            elif ("answer_versions", previous["id"]) in invalid:
                reason = "missing_context"
            elif previous["version_number"] >= current["version_number"] or previous["created_at"] >= current["created_at"]:
                reason = "ambiguous_history"
            else:
                candidates = [row for row in feedback[previous["id"]]
                              if row["feedback_type"] == "REFLECTION" and row["feedback_content"].strip()
                              and row["created_at"] < current["created_at"]]
                if not candidates:
                    reason = "missing_previous_feedback"
                else:
                    chosen = max(candidates, key=lambda row: (row["created_at"], int(row["id"])))
            member = indexes["memberships"].get(current["creator_id"], {})
            row = {
                "pair_id": "pair_" + current["id"], "course_id": current["course_id"],
                "participant_id": member.get("participant_id"), "submission_id": current["submission_id"],
                "question": current["question"], "previous_version_id": previous["id"] if previous else None,
                "current_version_id": current["id"], "previous_feedback_id": chosen["id"] if chosen else None,
                "previous_answer": previous["answer_content"] if previous else None,
                "current_answer": current["answer_content"], "previous_feedback": chosen["feedback_content"] if chosen else None,
                "eligibility": "unavailable" if reason else ("no_change" if previous["answer_content"] == current["answer_content"] else "ready"),
                "reason_code": reason, "selection_rule_version": SELECTION_VERSION,
            }
            hash_input = {key: row[key] for key in ("question", "previous_answer", "current_answer", "previous_feedback", "selection_rule_version")}
            row["input_hash"] = hashlib.sha256(json_bytes(hash_input)).hexdigest()
            builder.check(rows=1, size=len(json_bytes(row)))
            pairs.append(row)
            if reason:
                issue(reason, "answer_versions", current["id"])
            previous = current
        # Do not invent a final answer version. Match only unique exact question labels.
        latest = versions[-1]
        submission = indexes["submissions"].get(latest["submission_id"])
        if submission:
            payload = submission["form_response_data"]
            matches = [field for field in payload if isinstance(field, dict) and field.get("label", field.get("question")) == latest["question"]] if isinstance(payload, list) else []
            if len(matches) == 1 and isinstance(matches[0].get("response"), str):
                if matches[0]["response"] != latest["answer_content"]:
                    issue("current_submission_differs", "submissions", submission["id"], latest_version_id=latest["id"])
            else:
                issue("current_submission_comparison_unavailable", "submissions", submission["id"], latest_version_id=latest["id"])
    return pairs, issues


def build_archive(user, params):
    builder = ArchiveBuilder()
    # The request is explicitly non-atomic: establish isolation before snapshot reads.
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '15000ms'")
        snapshot_at = datetime.now(timezone.utc).isoformat()
        course_ids = selected_courses(user, params)
        data = collect_data(builder, course_ids, params["include_identity"])
    pairs, issues = derive(data, builder)
    export_id = str(uuid.uuid4())
    output = tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024, mode="w+b")
    manifest = {
        "export_id": export_id, "schema_version": SCHEMA_VERSION,
        "snapshot_at": snapshot_at, "exported_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_consistency": "PostgreSQL repeatable read" if connection.vendor == "postgresql" else "database read transaction",
        "scope": params["scope"], "course_ids": [str(i) for i in course_ids],
        "include_identity": params["include_identity"], "files": {},
        "limitations": ["Raw text may contain identifying information.", "Attachments are references only.",
                        "Deleted or never recorded history cannot be reconstructed.",
                        "Settings reflect export time, not historical score visibility.",
                        "Feedback records do not prove delivery, reading, or authentic provider provenance.",
                        "Current submissions are not synthesized into historical versions.",
                        "Participant IDs are stable only while the server research/signing key is unchanged."],
    }
    try:
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            files = {f"data/{name}.jsonl": rows for name, rows in data.items() if name != "identity_map"}
            files.update({"derived/reflection_pairs.jsonl": pairs, "quality/data_issues.jsonl": issues})
            if "identity_map" in data:
                files["identity/identity_map.jsonl"] = data["identity_map"]
            for path, rows in files.items():
                digest = hashlib.sha256()
                size = 0
                with archive.open(path, "w") as entry:
                    for row in rows:
                        builder.check()
                        line = json_bytes(row) + b"\n"
                        digest.update(line)
                        size += len(line)
                        entry.write(line)
                manifest["files"][path] = {"records": len(rows), "bytes": size, "sha256": digest.hexdigest()}
            readme = make_readme(files).encode("utf-8")
            archive.writestr("README.md", readme)
            manifest["files"]["README.md"] = {"bytes": len(readme), "sha256": hashlib.sha256(readme).hexdigest()}
            archive.writestr("manifest.json", json_bytes(manifest))
        # Recheck current permissions outside the repeatable-read snapshot.
        fresh_user = User.objects.get(pk=user.pk)
        if not fresh_user.is_activated or set(course_ids) - set(allowed_courses(fresh_user).values_list("id", flat=True)):
            raise PermissionDenied("Export permission changed. Please try again.")
        builder.check()
        output.seek(0)
        logger.info("Research export completed user=%s export=%s courses=%s rows=%s identity=%s", user.pk, export_id, course_ids, builder.rows, params["include_identity"])
        return output, export_id
    except Exception:
        output.close()
        raise


def make_readme(files):
    text = """# iReflect research archive (schema 1.0)

No AI was called to create this archive. Read manifest.json, then data/*.jsonl,
quality/data_issues.jsonl, and derived/reflection_pairs.jsonl. Each JSONL line is
one object; UTF-8 and escaped newlines preserve the original text. UTC timestamps
include timezone offsets. IDs and foreign-key IDs are strings; missing values
are null. Field names use snake_case and nested form/score JSON is preserved as stored.

Every *_id relationship uses the id field in its target file. participant_id,
owner_participant_id and commenter_participant_id use the same keyed research
identity namespace. Only the optional identity map contains dedicated name/email
identity columns. Names and identity information can still occur inside raw text.

The hash input for a pair is the object with question, previous_answer,
current_answer, previous_feedback, selection_rule_version; encode as UTF-8 JSON
with sorted keys, ensure_ascii=False and separators=(',', ':'); apply SHA-256.
No whitespace normalization is applied. Pair IDs identify current versions;
combine export_id and input_hash when recording external analysis results.

eligibility: ready (valid input), no_change (skip AI), unavailable (see reason_code).
Feedback types: REFLECTION / PLAYTEST. Strategies: BASIC / ADVANCED / PLAYTEST.
Only REFLECTION enters candidate pairs; all feedback types remain in raw data.
Settings are CURRENT, not proof of what students saw. Latest saved submissions
are separate from version history. No reading/learning/causal claims are made.
Deleted comment bodies are withheld. Missing links are reported, not invented.
Do not feed identity/identity_map.jsonl into an analysis agent.

## Foreign-key dictionary
"""
    text += "\n".join(f"- {key}: data/{target}.jsonl" for key, target in RELATIONS.items())
    text += "\n\n## File fields (raw JSON values retain their stored types)\n"
    for path, rows in files.items():
        fields = sorted({field for row in rows for field in row})
        text += f"\n- {path}: {', '.join(fields) if fields else '(empty file; no records in this scope)'}"
    return text + "\n"


class ResearchExportView(APIView):
    def post(self, request):
        # JWTTokenUserAuthentication returns a token user, not our domain User.
        user = User.objects.filter(pk=request.user.id, is_activated=True).first()
        if user is None:
            raise PermissionDenied()
        serializer = ExportRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data
        # Fail before acquiring the export lock for unauthorized requests.
        selected_courses(user, params)
        try:
            with export_guard(user.pk):
                output, export_id = build_archive(user, params)
        except OperationalError:
            logger.warning("Research export database unavailable user=%s scope=%s", user.pk, params["scope"])
            error = APIException("The export could not finish reading the database. Please try again or export one course at a time.")
            error.status_code = 503
            raise error
        except Exception as exc:
            logger.warning("Research export failed user=%s scope=%s error_type=%s", user.pk, params["scope"], type(exc).__name__)
            raise
        response = FileResponse(output, as_attachment=True, filename=f"ireflect-research-{export_id}.zip", content_type="application/zip")
        response["Cache-Control"] = "no-store, private"
        response["X-Content-Type-Options"] = "nosniff"
        return response
