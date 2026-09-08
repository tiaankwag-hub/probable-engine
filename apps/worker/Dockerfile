FROM python:3.11-slim AS base

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY packages ./packages
COPY apps/worker ./apps/worker
COPY database ./database

ENV PYTHONPATH=/srv
# Cloud Run requires a listening port even for this polling worker — see
# the health-check server in apps/worker/app/main.py. PORT is injected by
# Cloud Run at runtime; 8080 here only documents the local-dev default.
EXPOSE 8080
CMD ["python", "-m", "apps.worker.app.main"]
