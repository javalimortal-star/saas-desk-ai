from django.urls import path

from support_requests.api import PublicSupportRequestCreateView
from support_requests.views import SupportRequestCreateView, SupportRequestSubmittedView


app_name = "support_requests"
urlpatterns = [
    path("", SupportRequestCreateView.as_view(), name="submit"),
    path("submitted/<uuid:protocol>/", SupportRequestSubmittedView.as_view(), name="submitted"),
    path(
        "api/v1/requests/",
        PublicSupportRequestCreateView.as_view(),
        name="api-create",
    ),
]
