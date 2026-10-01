"""
@changelog
| Version | Description                          | Reference                                   |
| v1.0.0  | Initial implementation: feedback routes |                                             |
| v1.1.0  | Added records/ route (report + query) | REQ: 20260818-feedback-modification-tracking |
| v1.2.0  | Added milestone-export/ route (Excel) | REQ: 20260929-Excel导出功能升级 TECH: 04_design_tech-design.md §3.5 |
/@changelog

@author chuckyang123
"""
from django.urls import path
from django.db import transaction
from .research_export import ResearchExportView
from .milestone_excel_export import MilestoneExcelExportView

from .views import (
    FeedbackInitialResponseView,
    FeedbackRecordView,
    FeedbackView,
)

urlpatterns = [
    path("research-export/", transaction.non_atomic_requests(ResearchExportView.as_view()), name="research_export"),
    path("milestone-export/", transaction.non_atomic_requests(MilestoneExcelExportView.as_view()), name="milestone_excel_export"),
    path("", FeedbackView.as_view(), name="feedback"),
    path("initial-response/", FeedbackInitialResponseView.as_view(), name="initial_response"),
    path("records/", FeedbackRecordView.as_view(), name="feedback_records"),
]
