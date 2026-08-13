import uuid

from django.db import models


ANALYSIS_SUMMARY_MAX_LENGTH = 1000
SUGGESTED_RESPONSE_MAX_LENGTH = 4000


class SupportRequestCategory(models.TextChoices):
    ACCESS = "access", "Acesso"
    BILLING = "billing", "Cobrança"
    TECHNICAL_PROBLEM = "technical_problem", "Problema técnico"
    FEATURE_QUESTION = "feature_question", "Dúvida sobre funcionalidade"
    OTHER = "other", "Outro"


class SupportRequestPriority(models.TextChoices):
    LOW = "low", "Baixa"
    NORMAL = "normal", "Normal"
    HIGH = "high", "Alta"


class SupportRequest(models.Model):
    class Stage(models.TextChoices):
        RECEIVED = "received", "Recebida"
        ANALYZING = "analyzing", "Em análise"
        AWAITING_REVIEW = "awaiting_review", "Aguardando revisão"
        ANALYSIS_FAILED = "analysis_failed", "Falha na análise"
        RESOLVED = "resolved", "Resolvida"

    Category = SupportRequestCategory
    Priority = SupportRequestPriority

    requester_name = models.CharField(max_length=120)
    requester_email = models.EmailField()
    subject = models.CharField(max_length=160)
    message = models.TextField(max_length=4000)
    protocol = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    stage = models.CharField(max_length=24, choices=Stage, default=Stage.RECEIVED)
    final_category = models.CharField(max_length=32, choices=Category, blank=True)
    final_priority = models.CharField(max_length=16, choices=Priority, blank=True)
    approved_response = models.TextField(max_length=SUGGESTED_RESPONSE_MAX_LENGTH, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~models.Q(stage="resolved")
                    | (
                        ~models.Q(final_category="")
                        & ~models.Q(final_priority="")
                        & ~models.Q(approved_response="")
                        & models.Q(resolved_at__isnull=False)
                    )
                ),
                name="resolved_request_has_human_review",
            )
        ]


class AnalysisAttemptManager(models.Manager):
    def record_for(self, support_request, assisted_analysis, duration_ms=0):
        attempt = self.model(
            support_request=support_request,
            outcome=self.model.Outcome.SUCCEEDED,
            summary=assisted_analysis.summary,
            recommended_category=assisted_analysis.category,
            recommended_priority=assisted_analysis.priority,
            suggested_response=assisted_analysis.suggested_response,
            provider_model=assisted_analysis.provider_model,
            duration_ms=duration_ms,
            input_tokens=assisted_analysis.input_tokens,
            output_tokens=assisted_analysis.output_tokens,
        )
        attempt.full_clean()
        attempt.save()
        return attempt

    def record_failure(self, support_request, sanitized_error, duration_ms=0):
        attempt = self.model(
            support_request=support_request,
            outcome=self.model.Outcome.FAILED,
            sanitized_error=sanitized_error,
            duration_ms=duration_ms,
        )
        attempt.full_clean()
        attempt.save()
        return attempt


class AnalysisAttempt(models.Model):
    class Outcome(models.TextChoices):
        SUCCEEDED = "succeeded", "Concluída"
        FAILED = "failed", "Falhou"

    support_request = models.ForeignKey(
        SupportRequest,
        on_delete=models.CASCADE,
        related_name="analysis_attempts",
    )
    outcome = models.CharField(max_length=16, choices=Outcome, default=Outcome.SUCCEEDED)
    summary = models.TextField(max_length=ANALYSIS_SUMMARY_MAX_LENGTH, null=True, blank=True)
    recommended_category = models.CharField(
        max_length=32, choices=SupportRequest.Category, null=True, blank=True
    )
    recommended_priority = models.CharField(
        max_length=16, choices=SupportRequest.Priority, null=True, blank=True
    )
    suggested_response = models.TextField(
        max_length=SUGGESTED_RESPONSE_MAX_LENGTH, null=True, blank=True
    )
    provider_model = models.CharField(max_length=160, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    sanitized_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AnalysisAttemptManager()

    class Meta:
        ordering = ("created_at", "pk")


class AnalysisRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        PROCESSING = "processing", "Em processamento"
        COMPLETED = "completed", "Concluído"
        SKIPPED = "skipped", "Ignorado"

    support_request = models.ForeignKey(
        SupportRequest,
        on_delete=models.CASCADE,
        related_name="analysis_runs",
    )
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    attempt = models.OneToOneField(
        AnalysisAttempt,
        on_delete=models.PROTECT,
        related_name="analysis_run",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
