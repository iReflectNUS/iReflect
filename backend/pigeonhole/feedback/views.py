from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from pigeonhole.common.exceptions import BadRequest
from courses.middlewares import check_course, check_requester_membership
from courses.models import Course, CourseMembership, Role
from users.middlewares import check_account_access
from users.models import AccountType, User

from .logic import askChatGPT, askChatGPTOriginal, createFeedbackInitialResponseIfNotExists, feedback_initial_response_to_json
from .serializers import PostFeedbackInitialResponseSerializer, PostFeedbackSerializer


# Create your views here.
class FeedbackView(APIView):
    @check_account_access(AccountType.STANDARD, AccountType.EDUCATOR, AccountType.ADMIN)
    def post(self, request, requester: User):
        serializer = PostFeedbackSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        # No annotated content from ChatGPT, only feedback
        annotated_content = ''

        if requester.id % 2 == 0:
            feedback = askChatGPTOriginal(serializer.validated_data["content"])
        else:
            feedback = askChatGPT(serializer.validated_data["content"])

        data = {"annotated_content": annotated_content, "feedback": feedback}

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
                mechanic=validated_data["machanic"],
            )
        except ValueError as e:
            raise BadRequest(detail=e)
        
        data = {"created": created}

        if (created):
            json_data = feedback_initial_response_to_json(new_initial_response)
            data["new_initial_response"] = json_data

        return Response(data=data, status=status.HTTP_200_OK)
