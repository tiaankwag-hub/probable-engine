FROM python:3.11-slim AS base

WORKDIR /srv

COPY apps/mcp/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/mcp/app ./apps/mcp/app

ENV PYTHONPATH=/srv
EXPOSE 8080

CMD ["uvicorn", "apps.mcp.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
