from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.config import get_settings
from apps.api.app.routers import auth, categories, health, imports, jobs, risks


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Risk Intelligence Platform API",
        version="0.1.0",
        description="Milestone 1: Risk Register CRUD + Import Wizard.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(categories.router)
    app.include_router(risks.router)
    app.include_router(imports.router)
    app.include_router(jobs.router)

    return app


app = create_app()
