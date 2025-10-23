from rest_framework import serializers

from .models import FeedbackInitialResponse
from pigeonhole.common.serializers import IdField


class PostFeedbackSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, allow_blank=True)
    

class PostFeedbackInitialResponseSerializer(serializers.Serializer):
    submission_id = IdField(required=True)
    question = serializers.CharField(required=True, allow_blank=False)
    initial_response = serializers.CharField(required=True, allow_blank=False)
    genre = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    mechanic = serializers.CharField(required=False, allow_null=True)


