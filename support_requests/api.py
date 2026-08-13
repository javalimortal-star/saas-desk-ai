from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, serializers
from rest_framework.response import Response

from support_requests.access import is_support_request_analyst
from support_requests.analysis_retry import (
    AnalysisRetryRateLimited,
    IdempotencyKeyConflict,
    InvalidAnalysisRetryTransition,
    request_analysis_retry,
)
from support_requests.models import (
    SUGGESTED_RESPONSE_MAX_LENGTH,
    AnalysisAttempt,
    SupportRequest,
)
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
        return submit_support_request(**validated_data)


class PublicSupportRequestCreateView(generics.CreateAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = PublicSupportRequestSerializer


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
    queryset = SupportRequest.objects.order_by("-created_at")
    serializer_class = AnalystSupportRequestSerializer


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


class AnalystSupportRequestApproveView(generics.GenericAPIView):
    permission_classes = [IsSupportRequestAnalyst]
    queryset = SupportRequest.objects.all()
    serializer_class = HumanReviewSerializer

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


class AnalystSupportRequestRetryAnalysisView(generics.GenericAPIView):
    permission_classes = [IsSupportRequestAnalyst]
    queryset = SupportRequest.objects.all()
    serializer_class = AnalysisRetrySerializer

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
