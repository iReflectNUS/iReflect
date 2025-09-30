# from django.contrib import admin

# from pigeonhole.common.admin import BaseAdmin
# from .models import (
#     FeedbackInitialResponse,
# )

# # Register your models here.
# admin.site.register(FeedbackInitialResponse, BaseAdmin)

from django.contrib import admin
from pigeonhole.common.admin import BaseAdmin
from .models import FeedbackInitialResponse


@admin.register(FeedbackInitialResponse)
class FeedbackInitialResponseAdmin(BaseAdmin):
    raw_id_fields = ("course", "milestone", "template", "creator")

   
