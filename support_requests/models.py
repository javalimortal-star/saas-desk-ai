import uuid

from django.db import models


class SupportRequest(models.Model):
    class Stage(models.TextChoices):
        RECEIVED = "received", "Recebida"

    requester_name = models.CharField(max_length=120)
    requester_email = models.EmailField()
    subject = models.CharField(max_length=160)
    message = models.TextField(max_length=4000)
    protocol = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    stage = models.CharField(max_length=24, choices=Stage, default=Stage.RECEIVED)
    created_at = models.DateTimeField(auto_now_add=True)

