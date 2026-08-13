from rest_framework import generics, permissions, serializers

from support_requests.access import is_support_request_analyst
from support_requests.models import SupportRequest
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


class AnalystSupportRequestListView(generics.ListAPIView):
    permission_classes = [IsSupportRequestAnalyst]
    queryset = SupportRequest.objects.order_by("-created_at")
    serializer_class = AnalystSupportRequestSerializer


class AnalystSupportRequestDetailView(generics.RetrieveAPIView):
    permission_classes = [IsSupportRequestAnalyst]
    queryset = SupportRequest.objects.all()
    serializer_class = AnalystSupportRequestSerializer
