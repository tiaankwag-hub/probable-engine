from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/risk_platform"
    storage_root: str = "./.data/storage"
    cors_allow_origins: list[str] = ["http://localhost:3000"]


def get_settings() -> Settings:
    return Settings()
