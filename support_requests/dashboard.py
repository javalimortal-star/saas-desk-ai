from django import forms
from django.db.models import CharField, Count, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce, NullIf

from support_requests.models import AnalysisAttempt, SupportRequest


class DashboardFilterForm(forms.Form):
    stage = forms.ChoiceField(
        choices=(("", "Todas"), *SupportRequest.Stage.choices), required=False, label="Etapa"
    )
    category = forms.ChoiceField(
        choices=(("", "Todas"), *SupportRequest.Category.choices),
        required=False,
        label="Categoria",
    )
    priority = forms.ChoiceField(
        choices=(("", "Todas"), *SupportRequest.Priority.choices),
        required=False,
        label="Prioridade",
    )


def effective_support_requests():
    latest_success = AnalysisAttempt.objects.filter(
        support_request_id=OuterRef("pk"),
        outcome=AnalysisAttempt.Outcome.SUCCEEDED,
    ).order_by("-created_at", "-pk")
    return SupportRequest.objects.annotate(
        effective_category=Coalesce(
            NullIf("final_category", Value("")),
            Subquery(latest_success.values("recommended_category")[:1]),
            output_field=CharField(),
        ),
        effective_priority=Coalesce(
            NullIf("final_priority", Value("")),
            Subquery(latest_success.values("recommended_priority")[:1]),
            output_field=CharField(),
        ),
    )


def filter_support_requests(queryset, cleaned_filters):
    filters = {field: value for field, value in cleaned_filters.items() if value}
    category = filters.pop("category", None)
    priority = filters.pop("priority", None)
    if category:
        filters["effective_category"] = category
    if priority:
        filters["effective_priority"] = priority
    return queryset.filter(**filters)


def dashboard_totals(queryset):
    stage_counts = dict(queryset.values_list("stage").annotate(total=Count("pk")).order_by())
    category_counts = dict(
        queryset.exclude(effective_category__isnull=True)
        .values_list("effective_category")
        .annotate(total=Count("pk"))
        .order_by()
    )
    priority_counts = dict(
        queryset.exclude(effective_priority__isnull=True)
        .values_list("effective_priority")
        .annotate(total=Count("pk"))
        .order_by()
    )
    return (
        {value: stage_counts.get(value, 0) for value in SupportRequest.Stage.values},
        category_counts,
        priority_counts,
    )
