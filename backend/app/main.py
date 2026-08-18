"""CloudPilot AI — FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import router
from app.core.config import get_settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup for zero-config local runs."""
    try:
        init_db()
    except Exception:  # pragma: no cover - never block startup on DB issues
        pass
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        description=(
            "CloudPilot AI — AI-powered Infrastructure Optimization Platform. "
            "Analyze Terraform/OpenTofu, review architecture, compare providers, "
            "and generate optimized infrastructure code."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(router, prefix=settings.api_prefix)

    @application.get("/")
    async def root() -> dict:
        return {
            "service": "cloudpilot-ai",
            "version": __version__,
            "docs": "/docs",
            "health": "/api/v1/health",
            "demo": "/api/v1/demo/analyze",
        }

    return application


app = create_app()
