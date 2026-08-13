import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-local-development-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [
    host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host
]
if render_hostname := os.getenv("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(render_hostname)
if not DEBUG and SECRET_KEY == "unsafe-local-development-key":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY deve ser configurada em produção.")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "support_requests",
]
REST_FRAMEWORK = {"DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema"}
SPECTACULAR_SETTINGS = {
    "TITLE": "SaaS Desk AI API",
    "DESCRIPTION": "API de Solicitações e operações privadas do Analista.",
    "VERSION": "1.0.0",
    "ENUM_NAME_OVERRIDES": {
        "SupportRequestStage": "support_requests.models.SupportRequest.Stage",
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "saas_desk_ai"),
        "USER": os.getenv("POSTGRES_USER", "saas_desk_ai"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "saas_desk_ai"),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "55432"),
    }
}
if database_url := os.getenv("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.config(
        default=database_url,
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=not DEBUG,
    )

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "support_requests:analyst-login"
LOGIN_REDIRECT_URL = "support_requests:analyst-list"
LOGOUT_REDIRECT_URL = "support_requests:analyst-login"

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"

ANALYSIS_PROVIDER = os.getenv("ANALYSIS_PROVIDER", "fake")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
OPENROUTER_TIMEOUT_SECONDS = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "20"))
ANALYSIS_RETRY_COOLDOWN_SECONDS = int(os.getenv("ANALYSIS_RETRY_COOLDOWN_SECONDS", "60"))
PUBLIC_SUBMISSION_LIMIT = int(os.getenv("PUBLIC_SUBMISSION_LIMIT", "5"))
PUBLIC_SUBMISSION_WINDOW_SECONDS = int(os.getenv("PUBLIC_SUBMISSION_WINDOW_SECONDS", "3600"))
DEMO_RETENTION_DAYS = int(os.getenv("DEMO_RETENTION_DAYS", "7"))
DEMO_ANALYST_PASSWORD = os.getenv("DEMO_ANALYST_PASSWORD", "demo-password")
TRUSTED_PROXY_IPS = {
    ip.strip() for ip in os.getenv("TRUSTED_PROXY_IPS", "").split(",") if ip.strip()
}
TRUST_RENDER_PROXY = os.getenv("RENDER", "false").lower() == "true"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    if render_url := os.getenv("RENDER_EXTERNAL_URL"):
        CSRF_TRUSTED_ORIGINS = [render_url]
