"""Project endpoints: CRUD for analysis workspaces."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.analysis import Analysis
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectDetail, ProjectSummary, ProjectUpdate

router = APIRouter()


def _get_owned(db: DbSession, user_id: int, project_id: int) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == user_id)
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


@router.get("", response_model=list[ProjectSummary])
def list_projects(db: DbSession, current: CurrentUser) -> list[Project]:
    """List the current user's projects, newest first."""
    return list(
        db.scalars(
            select(Project)
            .where(Project.owner_id == current.id)
            .order_by(Project.created_at.desc())
        )
    )


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: DbSession, current: CurrentUser) -> ProjectDetail:
    """Create a project workspace."""
    project = Project(
        owner_id=current.id,
        name=payload.name,
        description=payload.description,
        source_type=payload.source_type,
        source_url=payload.source_url,
        provider=payload.provider,
        default_region=payload.default_region,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _detail(db, current.id, project)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, db: DbSession, current: CurrentUser) -> ProjectDetail:
    """Fetch a project with its latest analysis summary."""
    project = _get_owned(db, current.id, project_id)
    return _detail(db, current.id, project)


@router.patch("/{project_id}", response_model=ProjectDetail)
def update_project(
    project_id: int, payload: ProjectUpdate, db: DbSession, current: CurrentUser
) -> ProjectDetail:
    """Update project metadata."""
    project = _get_owned(db, current.id, project_id)
    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    if payload.default_region is not None:
        project.default_region = payload.default_region
    db.commit()
    db.refresh(project)
    return _detail(db, current.id, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: DbSession, current: CurrentUser) -> None:
    """Delete a project and all its analyses."""
    project = _get_owned(db, current.id, project_id)
    db.delete(project)
    db.commit()


def _detail(db: DbSession, user_id: int, project: Project) -> ProjectDetail:
    detail = ProjectDetail.model_validate(project)
    latest = db.scalar(
        select(Analysis)
        .where(Analysis.project_id == project.id)
        .order_by(Analysis.created_at.desc())
    )
    if latest is not None:
        detail.latest_analysis_id = latest.id
        detail.latest_stats = latest.summary_stats or {}
    return detail
