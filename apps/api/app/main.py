from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.config import get_settings
from apps.api.app.middleware import RequestIdMiddleware
from apps.api.app.routers import (
    actions,
    appetite,
    auth,
    categories,
    controls,
    dashboard,
    health,
    imports,
    jobs,
    risks,
    scoring_config,
)
from packages.shared.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="Risk Intelligence Platform API",
        version="0.1.0",
        description=(
            "Milestone 1-3: Risk Register CRUD, Import Wizard, Executive Dashboard, "
            "Controls, Actions, Risk Appetite, Governance Health."
        ),
    )

    app.add_middleware(RequestIdMiddleware)
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
    app.include_router(dashboard.router)
    app.include_router(scoring_config.router)
    app.include_router(controls.router)
    app.include_router(actions.router)
    app.include_router(appetite.router)

    return app


app = create_app()
