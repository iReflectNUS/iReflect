from django.db import models

from pigeonhole.common.models import TimestampedModel
from courses.models import Course, CourseMilestone, CourseMilestoneTemplate, CourseGroup, CourseMembership
from users.models import User

# Model for initial responses to the feedback feature
class FeedbackInitialResponse(TimestampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    milestone = models.ForeignKey(CourseMilestone, on_delete=models.SET_NULL, null=True)
    template = models.ForeignKey(
        CourseMilestoneTemplate, on_delete=models.SET_NULL, null=True
    )
    creator = models.ForeignKey(CourseMembership, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=255)
    question = models.CharField(max_length=1000)
    initial_response = models.TextField(blank=False)
    genre = models.TextField(null=True, blank=True)
    mechanic = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('course', 'milestone', 'template', 'creator', 'question')

    def __str__(self) -> str:
        return f"{self.name} | {self.creator} | {self.question}"
