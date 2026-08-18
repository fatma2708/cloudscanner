"""Production readiness score endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body

from app.services.recommendations.engine import run_recommendations
from app.services.scoring.service import compute_scores
from app.services.terraform.parser import parse_terraform_files

router = APIRouter()

FilesPayload = Annotated[dict[str, str], Body(description="path -> HCL content")]


@router.post("")
def score(files: FilesPayload, mode: str = "balanced") -> dict:
    """Score the infrastructure 0–100 across eight categories."""
    config = parse_terraform_files(files=files, default_region="us-east-1")
    recommendations = run_recommendations(config, mode=mode)
    return compute_scores(config, recommendations)
