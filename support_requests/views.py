from uuid import uuid4

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView

from support_requests.access import ANALYST_PERMISSION, is_support_request_analyst
from support_requests.analysis_retry import (
    AnalysisRetryRateLimited,
    IdempotencyKeyConflict,
    InvalidAnalysisRetryTransition,
    request_analysis_retry,
)
from support_requests.forms import AnalysisRetryForm, HumanReviewForm, SupportRequestForm
from support_requests.models import AnalysisAttempt, SupportRequest
from support_requests.review import InvalidResolutionTransition, resolve_support_request
from support_requests.submission import submit_support_request


class SupportRequestCreateView(CreateView):
    form_class = SupportRequestForm
    template_name = "support_requests/submit.html"

    def get_success_url(self):
        return reverse("support_requests:submitted", kwargs={"protocol": self.object.protocol})

    def form_valid(self, form):
        self.object = submit_support_request(**form.cleaned_data)
        return HttpResponseRedirect(self.get_success_url())


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
    permission_required = ANALYST_PERMISSION

    def handle_no_permission(self):
        if self.request.user.is_authenticated and not is_support_request_analyst(self.request.user):
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        latest_success = (
            self.object.analysis_attempts.filter(outcome=AnalysisAttempt.Outcome.SUCCEEDED)
            .order_by("-created_at")
            .first()
        )
        initial = {}
        if latest_success:
            initial = {
                "category": latest_success.recommended_category,
                "priority": latest_success.recommended_priority,
                "approved_response": latest_success.suggested_response,
            }
        context["review_form"] = HumanReviewForm(initial=initial)
        context["analysis_retry_form"] = AnalysisRetryForm(
            initial={"idempotency_key": uuid4()}
        )
        return context


class AnalystSupportRequestApproveView(AnalystPermissionRequiredMixin, View):
    def post(self, request, pk):
        support_request = get_object_or_404(SupportRequest, pk=pk)
        form = HumanReviewForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "support_requests/analyst_detail.html",
                {"support_request": support_request, "review_form": form},
                status=400,
            )

        try:
            resolve_support_request(support_request_id=pk, **form.cleaned_data)
        except InvalidResolutionTransition as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                "support_requests/analyst_detail.html",
                {"support_request": support_request, "review_form": form},
                status=409,
            )
        return redirect("support_requests:analyst-detail", pk=pk)


class AnalystSupportRequestRetryAnalysisView(AnalystPermissionRequiredMixin, View):
    def post(self, request, pk):
        support_request = get_object_or_404(SupportRequest, pk=pk)
        form = AnalysisRetryForm(request.POST)
        if not form.is_valid():
            return self._render_detail(request, support_request, form, 400)
        try:
            request_analysis_retry(support_request_id=pk, **form.cleaned_data)
        except (InvalidAnalysisRetryTransition, IdempotencyKeyConflict) as exc:
            form.add_error(None, str(exc))
            return self._render_detail(request, support_request, form, 409)
        except AnalysisRetryRateLimited as exc:
            form.add_error(None, str(exc))
            response = self._render_detail(request, support_request, form, 429)
            response.headers["Retry-After"] = str(exc.retry_after_seconds)
            return response
        return redirect("support_requests:analyst-detail", pk=pk)

    @staticmethod
    def _render_detail(request, support_request, retry_form, status):
        return render(
            request,
            "support_requests/analyst_detail.html",
            {
                "support_request": support_request,
                "review_form": HumanReviewForm(),
                "analysis_retry_form": retry_form,
            },
            status=status,
        )
