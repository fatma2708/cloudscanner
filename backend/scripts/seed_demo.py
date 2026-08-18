"""Seed a demo user + project and run a full analysis for local exploration.

Usage:
    python -m scripts.seed_demo
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import get_session_factory, init_db
from app.core.security import hash_password
from app.models.analysis import Analysis
from app.models.project import Project
from app.models.user import User
from app.services.analysis.demo_data import load_sample_files
from app.services.analysis.orchestrator import analyze

DEMO_EMAIL = "demo@cloudpilot.ai"


def run() -> None:
    init_db()
    with get_session_factory()() as db:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                full_name="Demo User",
                hashed_password=hash_password("cloudpilot-demo"),
                provider="email",
            )
            db.add(user)
            db.flush()
            print(f"Created demo user: {DEMO_EMAIL}")

        project = db.scalar(select(Project).where(Project.owner_id == user.id))
        if project is None:
            project = Project(
                owner_id=user.id,
                name="Sample Web App",
                description="Bundled sample Terraform project",
                provider="aws",
                default_region="us-east-1",
            )
            db.add(project)
            db.flush()
            print(f"Created project: {project.name}")

        result = analyze(files=load_sample_files(), mode="balanced", provider="aws", default_region="us-east-1")
        analysis = Analysis(
            project_id=project.id,
            mode="balanced",
            status="completed",
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
        db.commit()
        print(
            f"Seeded analysis: {result['summary']['resource_count']} resources, "
            f"${result['summary']['current_monthly']:.2f}/mo, grade {result['summary']['grade']}"
        )


if __name__ == "__main__":
    run()
