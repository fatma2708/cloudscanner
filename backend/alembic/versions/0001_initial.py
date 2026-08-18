"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01
"""
import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("public_id", sa.String(36), unique=True, index=True),
        sa.Column("email", sa.String(320), unique=True, index=True),
        sa.Column("full_name", sa.String(200)),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("hashed_password", sa.String(200)),
        sa.Column("provider", sa.String(20), default="email"),
        sa.Column("role", sa.String(20), default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(200)),
        sa.Column("description", sa.Text),
        sa.Column("source_type", sa.String(20), default="zip"),
        sa.Column("source_url", sa.String(500)),
        sa.Column("provider", sa.String(20), default="aws"),
        sa.Column("default_region", sa.String(40), default="us-east-1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("status", sa.String(20), default="completed"),
        sa.Column("commit_sha", sa.String(64)),
        sa.Column("mode", sa.String(30), default="balanced"),
        sa.Column("resources", sa.JSON),
        sa.Column("graph", sa.JSON),
        sa.Column("recommendations", sa.JSON),
        sa.Column("scores", sa.JSON),
        sa.Column("costs", sa.JSON),
        sa.Column("comparison", sa.JSON),
        sa.Column("carbon", sa.JSON),
        sa.Column("finops", sa.JSON),
        sa.Column("summary_stats", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "resource_nodes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("analysis_id", sa.Integer, sa.ForeignKey("analyses.id", ondelete="CASCADE")),
        sa.Column("resource_type", sa.String(120), index=True),
        sa.Column("resource_name", sa.String(200)),
        sa.Column("provider", sa.String(20)),
        sa.Column("service", sa.String(60), index=True),
        sa.Column("region", sa.String(40), default="global"),
        sa.Column("monthly_cost", sa.Float, default=0.0),
        sa.Column("status", sa.String(20), default="ok"),
        sa.Column("meta", sa.JSON),
    )
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("analysis_id", sa.Integer, sa.ForeignKey("analyses.id", ondelete="CASCADE")),
        sa.Column("key", sa.String(120)),
        sa.Column("severity", sa.String(20), default="medium"),
        sa.Column("category", sa.String(40), default="cost"),
        sa.Column("title", sa.String(300)),
        sa.Column("description", sa.Text),
        sa.Column("savings_monthly", sa.Float, default=0.0),
        sa.Column("risk", sa.String(40), default="low"),
        sa.Column("difficulty", sa.String(40), default="medium"),
        sa.Column("status", sa.String(20), default="open"),
        sa.Column("explanation", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("recommendations")
    op.drop_table("resource_nodes")
    op.drop_table("analyses")
    op.drop_table("projects")
    op.drop_table("users")
