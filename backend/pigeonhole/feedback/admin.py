from django.contrib import admin

from pigeonhole.common.admin import BaseAdmin
from .models import (
    FeedbackInitialResponse,
)

# Register your models here.
admin.site.register(FeedbackInitialResponse, BaseAdmin)