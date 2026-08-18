"""Demo endpoints: analyze the bundled sample project without an upload.

This makes the product instantly explorable — every dashboard page can call
``/demo/analyze`` and receive a full, realistic analysis payload.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.analysis.demo_data import load_sample_files
from app.services.analysis.orchestrator import analyze
from app.services.ingestion.service import IngestionError, fetch_github

router = APIRouter()


@router.get("/sample-files")
def sample_files() -> dict:
    """Return the bundled sample Terraform project files."""
    return {"files": load_sample_files()}


@router.get("/analyze")
def demo_analyze(mode: str = Query(default="balanced")) -> dict:
    """Run a full analysis on the bundled sample project."""
    result = analyze(
        files=load_sample_files(),
        mode=mode,
        provider="aws",
        default_region="us-east-1",
    )
    return result


@router.get("/analyze-github")
def demo_analyze_github(
    url: str = Query(description="Public GitHub repository URL"),
    mode: str = Query(default="balanced"),
) -> dict:
    """Analyze a public GitHub repository's Terraform code without an account."""
    try:
        files = fetch_github(url)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = analyze(
        files=files,
        mode=mode,
        provider="aws",
        default_region="us-east-1",
    )
    return result


@router.get("/analyze/{mode}")
def demo_analyze_mode(mode: str) -> dict:
    """Run a full analysis in the given optimization mode."""
    result = analyze(
        files=load_sample_files(),
        mode=mode,
        provider="aws",
        default_region="us-east-1",
    )
    return result
