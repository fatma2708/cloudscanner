"""Analysis model — a single snapshot of parsed infrastructure, recommendations,
scores and costs for a project.

The heavy JSON payloads (resources, graph, recommendations, scores, costs,
carbon) are stored as JSON columns so the analysis object is opaque to the ORM
and the *services* layer owns all domain logic.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(
        String(20), default="completed"
    )  # running | completed | failed
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mode: Mapped[str] = mapped_column(String(30), default="balanced")  # optimization mode

    # Computed domain payloads (see app.services for their schemas)
    resources: Mapped[list] = mapped_column(JSON, default=list)
    graph: Mapped[dict] = mapped_column(JSON, default=dict)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    costs: Mapped[dict] = mapped_column(JSON, default=dict)
    comparison: Mapped[dict] = mapped_column(JSON, default=dict)
    carbon: Mapped[dict] = mapped_column(JSON, default=dict)
    finops: Mapped[dict] = mapped_column(JSON, default=dict)

    summary_stats: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="analyses")  # noqa: F821
    resources_detail: Mapped[list[ResourceNode]] = relationship(  # noqa: F821
        back_populates="analysis", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Analysis id={self.id} project={self.project_id} mode={self.mode}>"


class ResourceNode(Base):
    """Indexed snapshot of a single parsed resource for filtering and reporting."""

    __tablename__ = "resource_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    resource_type: Mapped[str] = mapped_column(String(120), index=True)
    resource_name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(20))
    service: Mapped[str] = mapped_column(String(60), index=True)
    region: Mapped[str] = mapped_column(String(40), default="global")
    monthly_cost: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    analysis: Mapped[Analysis] = relationship(back_populates="resources_detail")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ResourceNode {self.resource_type}.{self.resource_name}>"
