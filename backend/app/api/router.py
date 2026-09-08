"""API router aggregating all v1 endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    analyses,
    architecture,
    auth,
    comparison,
    demo,
    finops,
    health,
    projects,
    reports,
    risk,
    scenario,
    score,
    sustainability,
)

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(analyses.router, prefix="/analyses", tags=["analyses"])
router.include_router(comparison.router, prefix="/comparison", tags=["comparison"])
router.include_router(score.router, prefix="/score", tags=["score"])
router.include_router(architecture.router, prefix="/architecture", tags=["architecture"])
router.include_router(finops.router, prefix="/finops", tags=["finops"])
router.include_router(sustainability.router, prefix="/sustainability", tags=["sustainability"])
router.include_router(reports.router, prefix="/reports", tags=["reports"])
router.include_router(scenario.router, prefix="/scenario", tags=["scenario"])
router.include_router(demo.router, prefix="/demo", tags=["demo"])
router.include_router(risk.router, prefix="/risk", tags=["risk"])
