from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView

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


class AnalystLoginView(LoginView):
    template_name = "support_requests/analyst_login.html"
    redirect_authenticated_user = True


class AnalystLogoutView(LogoutView):
    pass


class AnalystPermissionRequiredMixin(LoginRequiredMixin, PermissionRequiredMixin):
    permission_required = "support_requests.view_supportrequest"

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()


class AnalystSupportRequestListView(AnalystPermissionRequiredMixin, ListView):
    model = SupportRequest
    template_name = "support_requests/analyst_list.html"
    context_object_name = "support_requests"
    ordering = "-created_at"


class AnalystSupportRequestDetailView(AnalystPermissionRequiredMixin, DetailView):
    model = SupportRequest
    template_name = "support_requests/analyst_detail.html"
    context_object_name = "support_request"
