from django.urls import path

from support_requests.views import SupportRequestCreateView, SupportRequestSubmittedView


app_name = "requests"
urlpatterns = [
    path("", SupportRequestCreateView.as_view(), name="submit"),
    path("submitted/<uuid:protocol>/", SupportRequestSubmittedView.as_view(), name="submitted"),
]

