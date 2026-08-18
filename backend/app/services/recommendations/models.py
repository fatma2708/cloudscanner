"""Domain model for an infrastructure recommendation.

A recommendation is fully explainable: it always carries the *why*, the
expected impact across dimensions, implementation steps and a cost saving, so
the frontend can render it as a senior cloud engineer review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["critical", "high", "medium", "low"]
Risk = Literal["low", "medium", "high"]
Difficulty = Literal["easy", "medium", "hard"]
Confidence = Literal["high", "medium", "low", "unknown"]

# Canonical scoring categories (also used by the production score service)
CATEGORY_LABELS = {
    "security": "Security",
    "scalability": "Scalability",
    "reliability": "Reliability",
    "observability": "Observability",
    "cost": "Cost Efficiency",
    "disaster-recovery": "Disaster Recovery",
    "networking": "Networking",
    "compliance": "Compliance",
}


def all_categories() -> list[str]:
    return list(CATEGORY_LABELS.keys())


SEVERITY_WEIGHTS = {"critical": 4, "high": 3, "medium": 2, "low": 1}
MAX_SEVERITY = {"critical": 4, "high": 3, "medium": 2, "low": 1}

# Which optimization modes a category is relevant to
MODE_TAGS = {
    "lowest-cost": {"cost", "security", "networking"},
    "max-availability": {"reliability", "disaster-recovery", "observability", "scalability"},
    "lowest-latency": {"networking", "reliability", "observability"},
    "lowest-carbon": {"cost", "scalability", "networking"},
    "balanced": set(CATEGORY_LABELS.keys()),
    "startup-budget": {"cost", "security", "scalability"},
    "enterprise": {"security", "reliability", "disaster-recovery", "observability", "compliance"},
}


@dataclass
class Recommendation:
    key: str
    title: str
    description: str
    severity: Severity = "medium"
    category: str = "cost"
    target: list[str] = field(default_factory=list)
    savings_monthly: float = 0.0
    risk: Risk = "medium"
    difficulty: Difficulty = "medium"
    confidence: Confidence = "high"
    improvement: str = ""
    why: str = ""
    impact: str = ""
    cost_saved: str = ""
    performance_impact: str = ""
    reliability_impact: str = ""
    security_impact: str = ""
    source_file: str = ""
    source_line: int = 0
    implementation: list[str] = field(default_factory=list)
    modes: set[str] = field(default_factory=lambda: set(MODE_TAGS["balanced"]))
    generated_code: dict | None = None
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "category_label": CATEGORY_LABELS.get(self.category, self.category.title()),
            "confidence": self.confidence,
            "target": self.target,
            "savings_monthly": round(self.savings_monthly, 2),
            "risk": self.risk,
            "difficulty": self.difficulty,
            "improvement": self.improvement,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "explanation": {
                "why": self.why or self.description,
                "impact": self.impact,
                "cost_saved": self.cost_saved or f"${self.savings_monthly:,.2f}/mo",
                "performance": self.performance_impact,
                "reliability": self.reliability_impact,
                "security": self.security_impact,
            },
            "implementation": self.implementation,
            "modes": sorted(self.modes),
            "generated_code": self.generated_code,
            "evidence": self.evidence,
        }


def savings_floor(value: float) -> float:
    """Round tiny savings up to a readable floor of $1/mo."""
    if value <= 0:
        return 0.0
    return max(1.0, round(value, 2))
