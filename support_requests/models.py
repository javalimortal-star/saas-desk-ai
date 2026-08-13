import uuid

from django.db import models


ANALYSIS_SUMMARY_MAX_LENGTH = 1000
SUGGESTED_RESPONSE_MAX_LENGTH = 4000


class SupportRequest(models.Model):
    class Stage(models.TextChoices):
        RECEIVED = "received", "Recebida"
        ANALYZING = "analyzing", "Em análise"
        AWAITING_REVIEW = "awaiting_review", "Aguardando revisão"
        ANALYSIS_FAILED = "analysis_failed", "Falha na análise"
        RESOLVED = "resolved", "Resolvida"

    class Category(models.TextChoices):
        ACCESS = "access", "Acesso"
        BILLING = "billing", "Cobrança"
        TECHNICAL_PROBLEM = "technical_problem", "Problema técnico"
        FEATURE_QUESTION = "feature_question", "Dúvida sobre funcionalidade"
        OTHER = "other", "Outro"

    class Priority(models.TextChoices):
        LOW = "low", "Baixa"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Alta"

    requester_name = models.CharField(max_length=120)
    requester_email = models.EmailField()
    subject = models.CharField(max_length=160)
    message = models.TextField(max_length=4000)
    protocol = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    stage = models.CharField(max_length=24, choices=Stage, default=Stage.RECEIVED)
    created_at = models.DateTimeField(auto_now_add=True)


class AnalysisAttemptManager(models.Manager):
    def record_for(self, support_request, assisted_analysis):
        attempt = self.model(
            support_request=support_request,
            summary=assisted_analysis.summary,
            recommended_category=assisted_analysis.category,
            recommended_priority=assisted_analysis.priority,
            suggested_response=assisted_analysis.suggested_response,
        )
        attempt.full_clean()
        attempt.save()
        return attempt


class AnalysisAttempt(models.Model):
    support_request = models.ForeignKey(
        SupportRequest,
        on_delete=models.CASCADE,
        related_name="analysis_attempts",
    )
    summary = models.TextField(max_length=ANALYSIS_SUMMARY_MAX_LENGTH)
    recommended_category = models.CharField(max_length=32, choices=SupportRequest.Category)
    recommended_priority = models.CharField(max_length=16, choices=SupportRequest.Priority)
    suggested_response = models.TextField(max_length=SUGGESTED_RESPONSE_MAX_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AnalysisAttemptManager()
