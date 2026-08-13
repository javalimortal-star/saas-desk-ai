import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SupportRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("requester_name", models.CharField(max_length=120)),
                ("requester_email", models.EmailField(max_length=254)),
                ("subject", models.CharField(max_length=160)),
                ("message", models.TextField(max_length=4000)),
                ("protocol", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("stage", models.CharField(choices=[("received", "Recebida")], default="received", max_length=24)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]

