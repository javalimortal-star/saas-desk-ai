from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from support_requests.health import health_check

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
    path("", include("support_requests.urls")),
]
