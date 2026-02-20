FROM python:3.12-slim

WORKDIR /code

# Install system deps for asyncpg (libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app
COPY ./migrations /code/migrations
COPY ./alembic.ini /code/alembic.ini

# Azure Container Apps uses HTTP health probes on /api/v1/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

# --proxy-headers: reads X-Forwarded-For set by Azure Container Apps TLS termination
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
