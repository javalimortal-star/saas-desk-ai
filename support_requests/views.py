from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, TemplateView

from support_requests.forms import SupportRequestForm
from support_requests.models import SupportRequest


class SupportRequestCreateView(CreateView):
    form_class = SupportRequestForm
    template_name = "support_requests/submit.html"

    def get_success_url(self):
        return reverse("support_requests:submitted", kwargs={"protocol": self.object.protocol})


class SupportRequestSubmittedView(TemplateView):
    template_name = "support_requests/submitted.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        support_request = get_object_or_404(
            SupportRequest.objects.only("protocol"),
            protocol=kwargs["protocol"],
        )
        context["protocol"] = support_request.protocol
        return context
