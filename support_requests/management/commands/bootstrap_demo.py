from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria somente os dados fictícios ausentes, preservando o trabalho do avaliador."

    def handle(self, *args, **options):
        call_command("seed_demo", preserve_existing=True)
