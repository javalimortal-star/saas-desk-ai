from django import forms

from support_requests.models import SupportRequest


class SupportRequestForm(forms.ModelForm):
    class Meta:
        model = SupportRequest
        fields = ("requester_name", "requester_email", "subject", "message")
        labels = {
            "requester_name": "Nome",
            "requester_email": "E-mail",
            "subject": "Assunto",
            "message": "Mensagem",
        }

