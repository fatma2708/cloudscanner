"""ORM models for CloudPilot AI. Importing this package registers all models
with ``app.core.database.Base.metadata`` for Alembic autogenerate and tests."""

from app.models.analysis import Analysis, ResourceNode
from app.models.project import Project
from app.models.recommendation import Recommendation
from app.models.user import User

__all__ = ["User", "Project", "Analysis", "ResourceNode", "Recommendation"]
