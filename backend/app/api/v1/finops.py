"""FinOps dashboard endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body

from app.services.finops.service import build_finops
from app.services.optimization.engine import optimize
from app.services.pricing.engine import estimate_all
from app.services.recommendations.engine import run_recommendations
from app.services.terraform.parser import parse_terraform_files

router = APIRouter()

FilesPayload = Annotated[dict[str, str], Body(description="path -> HCL content")]


@router.post("")
def finops(files: FilesPayload, mode: str = "balanced") -> dict:
    """Compute the FinOps dashboard for the described infrastructure."""
    config = parse_terraform_files(files=files, default_region="us-east-1")
    costs = estimate_all(config.resources)
    for res in config.resources:
        res.attributes["_monthly_cost"] = costs.get(res.id, 0.0)
    current = round(sum(costs.values()), 2)
    recommendations = run_recommendations(config, mode=mode)
    plan = optimize(config, recommendations, current_monthly=current, mode=mode)
    return build_finops(
        config=config,
        resources_cost=costs,
        recommendations=recommendations,
        current_monthly=current,
        optimized_monthly=plan.optimized_monthly,
    )
