"""
@changelog
| Version | Description                                      | Reference                                   |
| v1.0.0  | Initial implementation: feedback generation and initial response collection views |                                             |
| v1.1.0  | Reworked FeedbackView: persist submission_id/question | REQ: 20260818-feedback-modification-tracking |
|         | Added FeedbackRecordView: Playtest reporting + querying | TECH: 04_design_tech-design.md §3.3          |
/@changelog

@author chuckyang123
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from pigeonhole.common.exceptions import BadRequest
from courses.models import Course
from users.middlewares import check_account_access
from users.models import AccountType, User

from .logic import (
    askChatGPT,
    askChatGPTOriginal,
    ai_feedback_record_to_json,
    createFeedbackInitialResponseIfNotExists,
    create_feedback_version_and_record,
    feedback_answer_version_to_json,
    feedback_initial_response_to_json,
)
from .models import AIFeedbackRecord, FeedbackAnswerVersion
from .serializers import (
    FeedbackRecordQuerySerializer,
    PostFeedbackInitialResponseSerializer,
    PostFeedbackRecordSerializer,
    PostFeedbackSerializer,
)


# Create your views here.
class FeedbackView(APIView):
    @check_account_access(AccountType.STANDARD, AccountType.EDUCATOR, AccountType.ADMIN)
    def post(self, request, requester: User):
        serializer = PostFeedbackSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # No annotated content from ChatGPT, only feedback
        annotated_content = ''

        if requester.id % 2 == 0:
            strategy = AIFeedbackRecord.STRATEGY_BASIC
            feedback, score_json, token_usage_json, latency_ms = askChatGPTOriginal(
                validated_data["content"]
            )
        else:
            strategy = AIFeedbackRecord.STRATEGY_ADVANCED
            feedback, score_json, token_usage_json, latency_ms = askChatGPT(
                validated_data["content"]
            )

        # Persist transactionally: answer version snapshot + AI feedback record (only when submission_id is provided)
        if validated_data.get("submission_id") and validated_data.get("question"):
            try:
                record = create_feedback_version_and_record(
                    submission_id=validated_data["submission_id"],
                    requester=requester,
                    question=validated_data["question"],
                    answer_content=validated_data["content"],
                    feedback_type=AIFeedbackRecord.FEEDBACK_TYPE_REFLECTION,
                    strategy=strategy,
                    feedback_content=feedback,
                    score_json=score_json,
                    token_usage_json=token_usage_json,
                    latency_ms=latency_ms,
                )
            except ValueError as e:
                raise BadRequest(detail=e)
            record_id = record.id
        else:
            record_id = None

        data = {
            "annotated_content": annotated_content,
            "feedback": feedback,
            "record_id": record_id,
        }

        return Response(data=data, status=status.HTTP_200_OK)


class FeedbackInitialResponseView(APIView):
    @check_account_access(AccountType.STANDARD, AccountType.EDUCATOR, AccountType.ADMIN)
    def post(
        self,
        request,
        requester: User,
    ):
        serializer = PostFeedbackInitialResponseSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        try:
            new_initial_response, created = createFeedbackInitialResponseIfNotExists(
                submission_id=validated_data["submission_id"],
                requester=requester,
                question=validated_data["question"],
                initial_response=validated_data["initial_response"],
                genre=validated_data["genre"],
                mechanic=validated_data["mechanic"],
            )
        except ValueError as e:
            raise BadRequest(detail=e)

        data = {"created": created}

        if (created):
            json_data = feedback_initial_response_to_json(new_initial_response)
            data["new_initial_response"] = json_data

        return Response(data=data, status=status.HTTP_200_OK)


class FeedbackRecordView(APIView):
    """AI feedback records: POST for frontend reporting (Playtest path), GET for educator/researcher queries."""

    @check_account_access(AccountType.STANDARD, AccountType.EDUCATOR, AccountType.ADMIN)
    def post(self, request, requester: User):
        serializer = PostFeedbackRecordSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        try:
            record = create_feedback_version_and_record(
                submission_id=validated_data["submission_id"],
                requester=requester,
                question=validated_data["question"],
                answer_content=validated_data["initial_response"],
                feedback_type=AIFeedbackRecord.FEEDBACK_TYPE_PLAYTEST,
                strategy=AIFeedbackRecord.STRATEGY_PLAYTEST,
                feedback_content=validated_data["feedback_content"],
                idempotency_key=validated_data.get("idempotency_key"),
                genre=validated_data.get("genre"),
                mechanic=validated_data.get("mechanic"),
            )
        except ValueError as e:
            raise BadRequest(detail=e)

        data = {
            "record": ai_feedback_record_to_json(record),
            "version": feedback_answer_version_to_json(record.version),
        }

        return Response(data=data, status=status.HTTP_200_OK)

    @check_account_access(AccountType.EDUCATOR, AccountType.ADMIN)
    def get(self, request, requester: User):
        serializer = FeedbackRecordQuerySerializer(data=request.query_params)

        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data

        versions = FeedbackAnswerVersion.objects.select_related(
            "course", "milestone", "template", "creator__user"
        ).prefetch_related("feedback_records").order_by(
            "creator", "question", "version_number"
        )

        if params.get("course_id"):
            versions = versions.filter(course_id=params["course_id"])
        if params.get("user_id"):
            versions = versions.filter(creator__user_id=params["user_id"])
        if params.get("milestone_id"):
            versions = versions.filter(milestone_id=params["milestone_id"])
        if params.get("question"):
            versions = versions.filter(question=params["question"])

        data = [
            {
                **feedback_answer_version_to_json(version),
                "feedback_records": [
                    ai_feedback_record_to_json(record)
                    for record in version.feedback_records.all()
                ],
            }
            for version in versions
        ]

        return Response(data=data, status=status.HTTP_200_OK)
