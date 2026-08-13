from django import forms

from support_requests.models import SUGGESTED_RESPONSE_MAX_LENGTH, SupportRequest


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


class HumanReviewForm(forms.Form):
    category = forms.ChoiceField(choices=SupportRequest.Category, label="Categoria")
    priority = forms.ChoiceField(choices=SupportRequest.Priority, label="Prioridade")
    approved_response = forms.CharField(
        label="Resposta aprovada",
        max_length=SUGGESTED_RESPONSE_MAX_LENGTH,
        strip=True,
        widget=forms.Textarea,
    )


class AnalysisRetryForm(forms.Form):
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)
