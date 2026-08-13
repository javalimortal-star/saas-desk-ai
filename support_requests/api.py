from rest_framework import generics, serializers

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

