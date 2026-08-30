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
CMD ["python", "-m", "apps.worker.app.main"]
