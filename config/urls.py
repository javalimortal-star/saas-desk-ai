from django.urls import include, path

from support_requests.api import PublicSupportRequestCreateView


urlpatterns = [
    path("api/v1/requests/", PublicSupportRequestCreateView.as_view(), name="request-api-list"),
    path("", include("support_requests.urls")),
]
