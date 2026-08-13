from django.urls import reverse
from django.views.generic import CreateView, TemplateView

from support_requests.forms import SupportRequestForm


class SupportRequestCreateView(CreateView):
    form_class = SupportRequestForm
    template_name = "support_requests/submit.html"

    def get_success_url(self):
        return reverse("requests:submitted", kwargs={"protocol": self.object.protocol})


class SupportRequestSubmittedView(TemplateView):
    template_name = "support_requests/submitted.html"

