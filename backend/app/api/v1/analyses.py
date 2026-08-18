"""Analysis endpoints: run and retrieve infrastructure analyses.

Upload a Terraform zip (multipart) or point at a public GitHub repository; the
orchestrator parses, prices, reviews, scores, compares, and reports.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.analysis import Analysis, ResourceNode
from app.models.project import Project
from app.services.analysis.orchestrator import analyze
from app.services.ingestion.service import IngestionError, fetch_github, read_zip

router = APIRouter()


def _get_project(db: DbSession, user_id: int, project_id: int) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == user_id)
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def _get_analysis(db: DbSession, user_id: int, analysis_id: int) -> Analysis:
    analysis = db.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.project.has(owner_id=user_id),
        )
    )
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found.")
    return analysis


def _store_result(
    db: DbSession,
    project_id: int,
    mode: str,
    result: dict,
) -> Analysis:
    analysis = Analysis(
        project_id=project_id,
        status="completed",
        mode=mode,
        resources=result["resources"],
        graph=result["graph"],
        recommendations=result["recommendations"],
        scores=result["scores"],
        costs=result["costs"],
        comparison=result["comparison"],
        carbon=result["carbon"],
        finops=result["finops"],
        summary_stats=result["summary"],
    )
    db.add(analysis)
    db.flush()

    for res in result["resources"]:
        db.add(
            ResourceNode(
                analysis_id=analysis.id,
                resource_type=res["resource_type"],
                resource_name=res["name"],
                provider=res["provider"],
                service=res["service"],
                region=res["region"],
                monthly_cost=res.get("monthly_cost", 0.0),
                meta={"kind": res.get("kind"), "label": res.get("label")},
            )
        )
    db.commit()
    db.refresh(analysis)
    return analysis


@router.post("/{project_id}/analyze-zip")
async def analyze_zip(
    project_id: int,
    db: DbSession,
    current: CurrentUser,
    mode: str = Query(default="balanced"),
    file: UploadFile = File(...),  # noqa: B008
) -> dict:
    """Analyze an uploaded Terraform/OpenTofu zip archive."""
    project = _get_project(db, current.id, project_id)
    data = await file.read()
    try:
        files = read_zip(data)
    except IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    result = analyze(
        files=files,
        mode=mode,
        provider=project.provider,
        default_region=project.default_region,
    )
    analysis = _store_result(db, project_id, mode, result)
    return {
        "analysis_id": analysis.id,
        "created_at": analysis.created_at.isoformat(),
        **result,
    }


@router.post("/{project_id}/analyze-github")
def analyze_github(
    project_id: int,
    db: DbSession,
    current: CurrentUser,
    url: str = Query(description="GitHub repository URL"),
    mode: str = Query(default="balanced"),
) -> dict:
    """Analyze a public GitHub repository's Terraform code."""
    project = _get_project(db, current.id, project_id)
    try:
        files = fetch_github(url)
    except IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    result = analyze(
        files=files,
        mode=mode,
        provider=project.provider,
        default_region=project.default_region,
    )
    analysis = _store_result(db, project_id, mode, result)
    return {
        "analysis_id": analysis.id,
        "created_at": analysis.created_at.isoformat(),
        **result,
    }


@router.get("")
def list_analyses(project_id: int | None = None, db: DbSession = None, current: CurrentUser = None):
    """List analyses, optionally filtered by project."""
    query = select(Analysis).join(Project)
    if project_id is not None:
        query = query.where(Analysis.project_id == project_id, Project.owner_id == current.id)
    else:
        query = query.where(Project.owner_id == current.id)
    rows = db.scalars(query.order_by(Analysis.created_at.desc())).all()
    return [
        {
            "id": a.id,
            "project_id": a.project_id,
            "status": a.status,
            "mode": a.mode,
            "created_at": a.created_at.isoformat(),
            "summary": a.summary_stats,
        }
        for a in rows
    ]


@router.get("/{analysis_id}")
def get_analysis(analysis_id: int, db: DbSession, current: CurrentUser) -> dict:
    """Fetch a stored analysis with all its domain payloads."""
    analysis = _get_analysis(db, current.id, analysis_id)
    return {
        "id": analysis.id,
        "project_id": analysis.project_id,
        "status": analysis.status,
        "mode": analysis.mode,
        "created_at": analysis.created_at.isoformat(),
        "resources": analysis.resources,
        "graph": analysis.graph,
        "recommendations": analysis.recommendations,
        "scores": analysis.scores,
        "costs": analysis.costs,
        "comparison": analysis.comparison,
        "carbon": analysis.carbon,
        "finops": analysis.finops,
        "summary": analysis.summary_stats,
    }
