from django.urls import path

from support_requests.api import (
    AnalystSupportRequestApproveView as AnalystSupportRequestApiApproveView,
    AnalystSupportRequestRetryAnalysisView as AnalystSupportRequestApiRetryAnalysisView,
    AnalystSupportRequestDetailView as AnalystSupportRequestApiDetailView,
    AnalystSupportRequestListView as AnalystSupportRequestApiListView,
    PublicSupportRequestCreateView,
)
from support_requests.views import (
    AnalystLoginView,
    AnalystLogoutView,
    AnalystSupportRequestDetailView,
    AnalystSupportRequestListView,
    AnalystSupportRequestApproveView,
    AnalystSupportRequestRetryAnalysisView,
    SupportRequestCreateView,
    SupportRequestSubmittedView,
)


app_name = "support_requests"
urlpatterns = [
    path("", SupportRequestCreateView.as_view(), name="submit"),
    path("submitted/", SupportRequestSubmittedView.as_view(), name="submitted"),
    path(
        "api/v1/requests/",
        PublicSupportRequestCreateView.as_view(),
        name="api-create",
    ),
    path(
        "api/v1/analyst/requests/",
        AnalystSupportRequestApiListView.as_view(),
        name="analyst-api-list",
    ),
    path(
        "api/v1/analyst/requests/<int:pk>/",
        AnalystSupportRequestApiDetailView.as_view(),
        name="analyst-api-detail",
    ),
    path(
        "api/v1/analyst/requests/<int:pk>/approve/",
        AnalystSupportRequestApiApproveView.as_view(),
        name="analyst-api-approve",
    ),
    path(
        "api/v1/analyst/requests/<int:pk>/retry-analysis/",
        AnalystSupportRequestApiRetryAnalysisView.as_view(),
        name="analyst-api-retry-analysis",
    ),
    path("analyst/login/", AnalystLoginView.as_view(), name="analyst-login"),
    path("analyst/logout/", AnalystLogoutView.as_view(), name="analyst-logout"),
    path("analyst/requests/", AnalystSupportRequestListView.as_view(), name="analyst-list"),
    path(
        "analyst/requests/<int:pk>/",
        AnalystSupportRequestDetailView.as_view(),
        name="analyst-detail",
    ),
    path(
        "analyst/requests/<int:pk>/approve/",
        AnalystSupportRequestApproveView.as_view(),
        name="analyst-approve",
    ),
    path(
        "analyst/requests/<int:pk>/retry-analysis/",
        AnalystSupportRequestRetryAnalysisView.as_view(),
        name="analyst-retry-analysis",
    ),
]
