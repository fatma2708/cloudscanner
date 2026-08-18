"""Optimization endpoints: mode-aware optimization plans and generated code."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body

from app.services.optimization.engine import MODE_META, optimize
from app.services.pricing.engine import estimate_all
from app.services.recommendations.engine import run_recommendations
from app.services.terraform.parser import parse_terraform_files

router = APIRouter()

FilesPayload = Annotated[dict[str, str], Body(description="path -> HCL content")]


@router.get("/modes")
def modes() -> dict:
    """List available optimization modes with metadata."""
    return {"modes": MODE_META}


@router.post("")
def optimize_files(
    files: FilesPayload,
    mode: str = "balanced",
) -> dict:
    """Build an optimization plan (cost deltas + generated Terraform) for files."""
    config = parse_terraform_files(files=files, default_region="us-east-1")
    costs = estimate_all(config.resources)
    for res in config.resources:
        res.attributes["_monthly_cost"] = costs.get(res.id, 0.0)
    current = round(sum(costs.values()), 2)
    recommendations = run_recommendations(config, mode=mode)
    plan = optimize(config, recommendations, current_monthly=current, mode=mode)
    return plan.summary
