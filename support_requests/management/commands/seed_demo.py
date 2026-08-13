import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from support_requests.analysis import AssistedAnalysis
from support_requests.models import AnalysisAttempt, SupportRequest

DEMO_NAMESPACE = uuid.UUID("876ff131-23af-44fe-a55f-1f8cab850738")
DEMO_ANALYST_EMAIL = "demo-analyst@saas-desk-ai.invalid"
DEMO_REQUESTS = (
    ("recebida", SupportRequest.Stage.RECEIVED, None, None),
    ("em-analise", SupportRequest.Stage.ANALYZING, None, None),
    ("acesso", SupportRequest.Stage.AWAITING_REVIEW, "access", "high"),
    ("cobranca", SupportRequest.Stage.AWAITING_REVIEW, "billing", "normal"),
    ("problema-tecnico", SupportRequest.Stage.AWAITING_REVIEW, "technical_problem", "high"),
    ("duvida-funcionalidade", SupportRequest.Stage.AWAITING_REVIEW, "feature_question", "low"),
    ("outro", SupportRequest.Stage.RESOLVED, "other", "normal"),
    ("falha", SupportRequest.Stage.ANALYSIS_FAILED, None, None),
)


class Command(BaseCommand):
    help = "Cria um Analista e Solicitações fictícias para avaliar a demonstração."

    def handle(self, *args, **options):
        user, created = get_user_model().objects.get_or_create(
            username="demo-analyst",
            defaults={"email": DEMO_ANALYST_EMAIL},
        )
        if not created and user.email != DEMO_ANALYST_EMAIL:
            raise CommandError(
                "O nome demo-analyst já pertence a uma conta que não foi criada pelo seed."
            )
        user.is_staff = False
        user.is_superuser = False
        user.set_password(settings.DEMO_ANALYST_PASSWORD)
        user.save()
        user.user_permissions.add(Permission.objects.get(codename="view_supportrequest"))

        for slug, stage, category, priority in DEMO_REQUESTS:
            is_resolved = stage == SupportRequest.Stage.RESOLVED
            support_request, _ = SupportRequest.objects.update_or_create(
                protocol=uuid.uuid5(DEMO_NAMESPACE, slug),
                defaults={
                    "requester_name": "Pessoa Fictícia",
                    "requester_email": f"{slug}@example.com",
                    "subject": f"Solicitação fictícia: {slug}",
                    "message": "Conteúdo fictício criado pelo comando seed_demo.",
                    "stage": stage,
                    "final_category": category if is_resolved else "",
                    "final_priority": priority if is_resolved else "",
                    "approved_response": "Resposta fictícia aprovada." if is_resolved else "",
                    "resolved_at": timezone.now() if is_resolved else None,
                },
            )
            if category and not is_resolved:
                if not support_request.analysis_attempts.filter(
                    outcome=AnalysisAttempt.Outcome.SUCCEEDED
                ).exists():
                    AnalysisAttempt.objects.record_for(
                        support_request,
                        AssistedAnalysis(
                            summary="Resumo fictício para avaliação.",
                            category=category,
                            priority=priority,
                            suggested_response="Resposta fictícia sugerida.",
                            provider_model="demo/seed",
                            input_tokens=10,
                            output_tokens=10,
                        ),
                        duration_ms=1,
                    )
            if (
                stage == SupportRequest.Stage.ANALYSIS_FAILED
                and not support_request.analysis_attempts.exists()
            ):
                AnalysisAttempt.objects.record_failure(
                    support_request,
                    "Falha fictícia para avaliação.",
                    duration_ms=1,
                    provider_model="demo/seed",
                )

        self.stdout.write(self.style.SUCCESS("Dados fictícios de demonstração prontos."))
