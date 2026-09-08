from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/risk_platform"
    storage_root: str = "./.data/storage"
    cors_allow_origins: list[str] = ["http://localhost:3000"]

    # "mock": local dev/CI only — POST /api/v1/auth/mock-login mints a valid
    # token for any seeded email, no password, no verification. Never set
    # this in a deployed environment; it is a deliberate backdoor that only
    # exists because standing up real IAP/SSO for every dev machine and CI
    # run isn't worth it (ADR 0010). "iap": production — identity comes
    # exclusively from Google IAP's signed assertion header, verified
    # against Google's public keys; mock-login is not registered at all.
    auth_mode: Literal["mock", "iap"] = "mock"

    # Required when auth_mode="iap": the audience IAP's JWT is issued for.
    # Obtained from the deployed resource, not chosen freely — see
    # docs/architecture/milestone-11-plan.md and the deployment runbook for
    # exactly how to read it back with gcloud once the Cloud Run service
    # and IAP are provisioned.
    iap_audience: str | None = None


def get_settings() -> Settings:
    return Settings()
