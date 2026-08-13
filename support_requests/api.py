from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, serializers
from rest_framework.response import Response

from support_requests.access import is_support_request_analyst
from support_requests.analysis_retry import (
    AnalysisRetryRateLimited,
    IdempotencyKeyConflict,
    InvalidAnalysisRetryTransition,
    request_analysis_retry,
)
from support_requests.dashboard import (
    DashboardFilterForm,
    effective_support_requests,
    filter_support_requests,
)
from support_requests.models import (
    SUGGESTED_RESPONSE_MAX_LENGTH,
    AnalysisAttempt,
    SupportRequest,
)
from support_requests.public_protection import PublicSubmissionRateLimited, get_client_ip
from support_requests.review import InvalidResolutionTransition, resolve_support_request
from support_requests.submission import submit_support_request


class PublicSupportRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportRequest
        fields = ("requester_name", "requester_email", "subject", "message", "protocol")
        extra_kwargs = {
            "requester_name": {"write_only": True},
            "requester_email": {"write_only": True},
            "subject": {"write_only": True},
            "message": {"write_only": True},
            "protocol": {"read_only": True},
        }

    def create(self, validated_data):
        request = self.context["request"]
        return submit_support_request(
            client_ip=get_client_ip(request),
            **validated_data,
        )


class ErrorDetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


VALIDATION_ERROR_SCHEMA = {
    "type": "object",
    "additionalProperties": {
        "type": "array",
        "items": {"type": "string"},
    },
}


class PublicSupportRequestCreateView(generics.CreateAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = PublicSupportRequestSerializer

    @extend_schema(
        responses={
            201: PublicSupportRequestSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            429: ErrorDetailSerializer,
        },
        parameters=[
            OpenApiParameter(
                "Retry-After",
                int,
                OpenApiParameter.HEADER,
                response=[429],
                description="Segundos até um novo envio ser permitido.",
            )
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except PublicSubmissionRateLimited as exc:
            return Response(
                {"detail": str(exc)},
                status=429,
                headers={"Retry-After": str(exc.retry_after_seconds)},
            )


class IsSupportRequestAnalyst(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_support_request_analyst(request.user)


class AnalystSupportRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportRequest
        fields = (
            "id",
            "protocol",
            "requester_name",
            "requester_email",
            "subject",
            "message",
            "stage",
            "created_at",
        )


class AnalystSupportRequestListSerializer(AnalystSupportRequestSerializer):
    effective_category = serializers.CharField(read_only=True, allow_null=True)
    effective_category_label = serializers.SerializerMethodField()
    effective_priority = serializers.CharField(read_only=True, allow_null=True)
    effective_priority_label = serializers.SerializerMethodField()

    class Meta(AnalystSupportRequestSerializer.Meta):
        fields = AnalystSupportRequestSerializer.Meta.fields + (
            "effective_category",
            "effective_category_label",
            "effective_priority",
            "effective_priority_label",
        )

    def get_effective_category_label(self, obj) -> str:
        return obj.effective_category_display

    def get_effective_priority_label(self, obj) -> str:
        return obj.effective_priority_display


class AnalysisAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisAttempt
        fields = (
            "id",
            "outcome",
            "summary",
            "recommended_category",
            "recommended_priority",
            "suggested_response",
            "provider_model",
            "duration_ms",
            "input_tokens",
            "output_tokens",
            "sanitized_error",
            "created_at",
        )


class AnalystSupportRequestDetailSerializer(AnalystSupportRequestSerializer):
    analysis_attempts = AnalysisAttemptSerializer(many=True, read_only=True)

    class Meta(AnalystSupportRequestSerializer.Meta):
        fields = AnalystSupportRequestSerializer.Meta.fields + ("analysis_attempts",)


class AnalystSupportRequestListView(generics.ListAPIView):
    permission_classes = [IsSupportRequestAnalyst]
    serializer_class = AnalystSupportRequestListSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("stage", enum=SupportRequest.Stage.values),
            OpenApiParameter("category", enum=SupportRequest.Category.values),
            OpenApiParameter("priority", enum=SupportRequest.Priority.values),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        form = DashboardFilterForm(self.request.query_params)
        if not form.is_valid():
            raise serializers.ValidationError(form.errors.get_json_data())
        return filter_support_requests(
            effective_support_requests().order_by("-created_at"), form.cleaned_data
        )


class AnalystSupportRequestDetailView(generics.RetrieveAPIView):
    permission_classes = [IsSupportRequestAnalyst]
    queryset = SupportRequest.objects.all()
    serializer_class = AnalystSupportRequestDetailSerializer


class HumanReviewSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=SupportRequest.Category)
    priority = serializers.ChoiceField(choices=SupportRequest.Priority)
    approved_response = serializers.CharField(
        max_length=SUGGESTED_RESPONSE_MAX_LENGTH, trim_whitespace=True
    )


class HumanReviewResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    stage = serializers.ChoiceField(choices=SupportRequest.Stage)
    category = serializers.ChoiceField(choices=SupportRequest.Category)
    priority = serializers.ChoiceField(choices=SupportRequest.Priority)
    approved_response = serializers.CharField()
    resolved_at = serializers.DateTimeField()


class AnalystSupportRequestApproveView(generics.GenericAPIView):
    permission_classes = [IsSupportRequestAnalyst]
    queryset = SupportRequest.objects.all()
    serializer_class = HumanReviewSerializer

    @extend_schema(
        responses={
            200: HumanReviewResultSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            409: ErrorDetailSerializer,
        }
    )
    def post(self, request, pk):
        self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            support_request = resolve_support_request(
                support_request_id=pk, **serializer.validated_data
            )
        except InvalidResolutionTransition as exc:
            return Response({"detail": str(exc)}, status=409)

        return Response(
            {
                "id": support_request.pk,
                "stage": support_request.stage,
                "category": support_request.final_category,
                "priority": support_request.final_priority,
                "approved_response": support_request.approved_response,
                "resolved_at": support_request.resolved_at,
            }
        )


class AnalysisRetrySerializer(serializers.Serializer):
    idempotency_key = serializers.UUIDField()


class AnalysisRetryResultSerializer(serializers.Serializer):
    idempotency_key = serializers.UUIDField()
    status = serializers.CharField()
    created = serializers.BooleanField()


class AnalystSupportRequestRetryAnalysisView(generics.GenericAPIView):
    permission_classes = [IsSupportRequestAnalyst]
    queryset = SupportRequest.objects.all()
    serializer_class = AnalysisRetrySerializer

    @extend_schema(
        responses={
            202: AnalysisRetryResultSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            409: ErrorDetailSerializer,
            429: ErrorDetailSerializer,
        },
        parameters=[
            OpenApiParameter(
                "Retry-After",
                int,
                OpenApiParameter.HEADER,
                response=[429],
                description="Segundos até uma nova Tentativa ser permitida.",
            )
        ],
    )
    def post(self, request, pk):
        get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            run, created = request_analysis_retry(
                support_request_id=pk, **serializer.validated_data
            )
        except InvalidAnalysisRetryTransition as exc:
            return Response({"detail": str(exc)}, status=409)
        except IdempotencyKeyConflict as exc:
            return Response({"detail": str(exc)}, status=409)
        except AnalysisRetryRateLimited as exc:
            return Response(
                {"detail": str(exc)},
                status=429,
                headers={"Retry-After": str(exc.retry_after_seconds)},
            )
        return Response(
            {
                "idempotency_key": str(run.idempotency_key),
                "status": run.status,
                "created": created,
            },
            status=202,
        )
