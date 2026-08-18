"""Recommendation engine: rule-based infrastructure review with AI explanations."""

from app.services.recommendations.engine import run_recommendations
from app.services.recommendations.models import Recommendation, Severity, all_categories
from app.services.recommendations.rules import ALL_RULES

__all__ = [
    "run_recommendations",
    "Recommendation",
    "Severity",
    "all_categories",
    "ALL_RULES",
]
