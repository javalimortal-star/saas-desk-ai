from rest_framework import generics, permissions, serializers

from support_requests.models import SupportRequest


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


class PublicSupportRequestCreateView(generics.CreateAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = PublicSupportRequestSerializer


class IsSupportRequestAnalyst(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_perm(
            "support_requests.view_supportrequest"
        )


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
