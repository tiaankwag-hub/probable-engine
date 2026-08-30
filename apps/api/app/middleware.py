from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from packages.shared.logging import request_id_var

logger = logging.getLogger("apps.api.request")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns/propagates X-Request-Id (brief's Observability section) and
    logs one structured line per request with latency and status, so every
    request is traceable end-to-end through structured logs without
    threading an id through every function call."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        started = time.monotonic()
        try:
            response = await call_next(request)
            duration_ms = round((time.monotonic() - started) * 1000, 2)
            response.headers["X-Request-Id"] = request_id
            logger.info(
                "%s %s -> %s (%sms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            request_id_var.reset(token)
