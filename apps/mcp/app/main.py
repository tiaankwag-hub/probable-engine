"""Entrypoint: `uvicorn apps.mcp.app.main:app`."""

from __future__ import annotations

from apps.mcp.app.server import build_app

app = build_app()
