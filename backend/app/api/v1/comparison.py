"""Provider comparison endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body

from app.services.pricing.comparison import compare_providers
from app.services.pricing.providers import all_providers
from app.services.terraform.parser import parse_terraform_files

router = APIRouter()

FilesPayload = Annotated[dict[str, str], Body(description="path -> HCL content")]


@router.get("/providers")
def providers() -> list[dict]:
    """List all supported providers with metadata."""
    return [
        {
            "key": p.key,
            "label": p.label,
            "region": p.region,
            "availability": p.availability,
            "notes": list(p.notes),
        }
        for p in all_providers()
    ]


@router.post("")
def compare(files: FilesPayload) -> dict:
    """Compare the described workload across all providers."""
    config = parse_terraform_files(files=files, default_region="us-east-1")
    return compare_providers(config)
