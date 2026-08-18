"""Project schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    source_type: str = Field(default="zip", pattern="^(zip|github)$")
    source_url: str | None = None
    provider: str = Field(default="aws")
    default_region: str = Field(default="us-east-1")


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    default_region: str | None = None


class ProjectSummary(BaseModel):
    id: int
    name: str
    description: str | None
    source_type: str
    source_url: str | None
    provider: str
    default_region: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetail(ProjectSummary):
    latest_analysis_id: int | None = None
    latest_stats: dict = Field(default_factory=dict)
