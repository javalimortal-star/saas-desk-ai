import os

import django
from django.core.management import call_command


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    call_command("migrate", interactive=False)
    call_command("bootstrap_demo")

    port = os.getenv("PORT", "8000")
    os.execvp(
        "gunicorn",
        ["gunicorn", "config.wsgi:application", "--bind", f"0.0.0.0:{port}"],
    )


if __name__ == "__main__":
    main()
