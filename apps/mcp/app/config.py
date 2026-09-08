"""Settings for the MCP gateway. Deliberately tiny: apps/mcp holds no
database URL, no storage root, no AI provider config — it has nothing to
configure beyond where apps/api lives, because it has no direct access to
anything else (ADR 0009).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_", env_file=".env", extra="ignore")

    api_base_url: str = "http://localhost:8000"
    request_timeout_seconds: float = 30.0

    # Declarative-only: identifies where callers are expected to have gotten
    # their token from (surfaced in OAuth discovery metadata for MCP client
    # tooling). Verification itself never dereferences this URL — it always
    # goes through RiskPlatformTokenVerifier calling apps/api directly. Set
    # this to the real Google IAP/corporate SSO issuer in production; the
    # local-dev default just names this stack's own mock-auth as the source.
    identity_issuer_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
