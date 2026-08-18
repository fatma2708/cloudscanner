"""Report endpoints: full architectural review reports."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.analysis import Analysis

router = APIRouter()


@router.get("/{analysis_id}")
def report(analysis_id: int, db: DbSession, current: CurrentUser) -> dict:
    """Bundle a stored analysis into a shareable report."""
    analysis = db.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.project.has(owner_id=current.id),
        )
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return {
        "id": analysis.id,
        "project_id": analysis.project_id,
        "created_at": analysis.created_at.isoformat(),
        "mode": analysis.mode,
        "summary": analysis.summary_stats,
        "scores": analysis.scores,
        "finops": analysis.finops,
        "comparison": analysis.comparison,
        "carbon": analysis.carbon,
        "review": {
            "provider": "cloudpilot",
            "executive_summary": (
                f"Production readiness {analysis.scores.get('overall', 0):.0f}/100 "
                f"({analysis.scores.get('grade', 'F')}) across "
                f"{len(analysis.resources or [])} resources. "
                f"Optimized spend is ${analysis.finops.get('optimized_monthly', 0):,.0f}/mo "
                f"(saving ${analysis.finops.get('monthly_savings', 0):,.0f}/mo)."
            ),
            "architecture_review": _build_report_body(analysis),
        },
        "recommendations": analysis.recommendations or [],
    }


def _build_report_body(analysis: Analysis) -> str:
    parts = ["## Executive Summary\n"]
    parts.append(
        f"This infrastructure scores **{analysis.scores.get('overall', 0):.0f}/100** "
        f"({analysis.scores.get('grade', 'F')}). The environment provisions "
        f"**{len(analysis.resources or [])}** resources costing an estimated "
        f"**${analysis.finops.get('current_monthly', 0):,.0f}/mo** "
        f"(${analysis.finops.get('annual_savings', 0):,.0f}/yr savings available).\n"
    )
    parts.append("## Category Scores\n")
    for cat in analysis.scores.get("categories", []):
        parts.append(f"- {cat['label']}: **{cat['score']:.0f}/100**")
    parts.append("\n## Top Recommendations\n")
    for rec in (analysis.recommendations or [])[:8]:
        parts.append(
            f"- **[{rec.get('severity', '').upper()}]** {rec.get('title')} "
            f"— {rec.get('description', '')[:160]}"
        )
    return "\n".join(parts)
