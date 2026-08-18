"""Sustainability / carbon endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body

from app.services.optimization.engine import optimize
from app.services.pricing.engine import estimate_all
from app.services.recommendations.engine import run_recommendations
from app.services.sustainability.service import estimate_carbon
from app.services.terraform.parser import parse_terraform_files

router = APIRouter()

FilesPayload = Annotated[dict[str, str], Body(description="path -> HCL content")]


@router.post("")
def sustainability(files: FilesPayload, mode: str = "balanced") -> dict:
    """Estimate carbon footprint and greener alternatives."""
    config = parse_terraform_files(files=files, default_region="us-east-1")
    costs = estimate_all(config.resources)
    current = round(sum(costs.values()), 2)
    recommendations = run_recommendations(config, mode=mode)
    plan = optimize(config, recommendations, current_monthly=current, mode=mode)
    return estimate_carbon(config, plan.optimized_monthly)
