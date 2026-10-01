"""
@changelog
| Version | Description                                      | Reference                                   |
| v1.0.0  | Initial implementation: feedback generation and initial response collection serializers |                                             |
| v1.1.0  | Added PostFeedbackRecordSerializer (reporting) and | REQ: 20260818-feedback-modification-tracking |
|         | FeedbackRecordQuerySerializer (query filters)     | TECH: 04_design_tech-design.md §3.3          |
| v1.2.0  | FeedbackRecordQuerySerializer adds submission_id | REQ: 20260818-feedback-modification-tracking |
|         | filter parameter                                | TECH: 04_design_tech-design.md §3.3          |
| v1.3.0  | PostFeedbackRecordSerializer accepts score_json | BUG: playtest-missing-score-json             |
|         | so playtest records keep structured scores      | PRD: 20260824-playtest-score-visibility      |
/@changelog

@author chuckyang123
"""
from rest_framework import serializers

from .models import FeedbackInitialResponse
from pigeonhole.common.serializers import IdField


class PostFeedbackSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, allow_blank=True)
    submission_id = IdField(required=False)
    question = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PostFeedbackInitialResponseSerializer(serializers.Serializer):
    submission_id = IdField(required=True)
    question = serializers.CharField(required=True, allow_blank=False)
    initial_response = serializers.CharField(required=True, allow_blank=False)
    genre = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    mechanic = serializers.CharField(required=False, allow_null=True)


class PostFeedbackRecordSerializer(serializers.Serializer):
    """Playtest frontend payload for reporting an AI feedback record (includes idempotency key, RISK-DA006)."""
    submission_id = IdField(required=True)
    question = serializers.CharField(required=True, allow_blank=False)
    initial_response = serializers.CharField(required=True, allow_blank=False)
    feedback_content = serializers.CharField(required=True, allow_blank=False)
    genre = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    mechanic = serializers.CharField(required=False, allow_null=True)
    idempotency_key = serializers.UUIDField(required=False, allow_null=True)
    # Parsed by the frontend from the LightRAG score block; absent when the
    # response carried no parsable scores (still stored as null, not rejected).
    score_json = serializers.JSONField(required=False, allow_null=True)


class FeedbackRecordQuerySerializer(serializers.Serializer):
    """Query filter parameters for educators/researchers (read-only API)."""
    course_id = IdField(required=False)
    user_id = IdField(required=False)
    milestone_id = IdField(required=False)
    submission_id = IdField(required=False)
    question = serializers.CharField(required=False, allow_blank=True, allow_null=True)
