FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY config ./config
COPY support_requests ./support_requests
RUN pip install --no-cache-dir .

COPY manage.py ./
COPY templates ./templates
RUN DJANGO_DEBUG=false DJANGO_SECRET_KEY=collectstatic-build-only python manage.py collectstatic --noinput

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
