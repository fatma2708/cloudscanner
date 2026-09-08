"""CloudPilot AI — FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import router
from app.core.config import get_settings
from app.core.database import init_db
from app.services.risk_intelligence.service import get_risk_intelligence_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup for zero-config local runs."""
    logger = logging.getLogger("main")
    try:
        init_db()
    except Exception:
        logger.exception("Failed to initialize database on startup")
    try:
        # Fail loudly if the trusted CRIM-v4.2 artifact is missing/incompatible.
        # The risk endpoint returns 503 when unavailable; the rest of the API
        # (including Checkov-backed flows) keeps working independently.
        service = get_risk_intelligence_service()
        service.ensure_loaded()
        logger.info(
            "CRIM-v4.2 model loaded: classes=%s threshold=%.2f", service.classes, service.threshold
        )
    except Exception:
        logger.exception(
            "CRIM-v4.2 risk intelligence model unavailable; POST /risk/classify returns 503"
        )
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
