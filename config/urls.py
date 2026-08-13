from django.urls import include, path


urlpatterns = [
    path("", include("support_requests.urls")),
]
