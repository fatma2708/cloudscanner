"""Architecture graph endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body

from app.services.architecture.service import build_graph
from app.services.terraform.parser import parse_terraform_files

router = APIRouter()

FilesPayload = Annotated[dict[str, str], Body(description="path -> HCL content")]


@router.post("")
def architecture(files: FilesPayload) -> dict:
    """Build the interactive architecture graph for the given infrastructure."""
    config = parse_terraform_files(files=files, default_region="us-east-1")
    return build_graph(config)
