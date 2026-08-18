"""Analysis and recommendation schemas.

These mirror the domain shapes produced by the services layer so the API
contract and the internal domain models stay in sync.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low"]
Risk = Literal["low", "medium", "high"]
Difficulty = Literal["easy", "medium", "hard"]


class ResourceSchema(BaseModel):
    id: str
    resource_type: str
    name: str
    provider: str
    service: str
    region: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    references: list[str] = Field(default_factory=list)
    line: int = 0
    monthly_cost: float = 0.0


class RecommendationSchema(BaseModel):
    key: str
    severity: Severity
    category: str
    title: str
    description: str
    target: list[str] = Field(default_factory=list)
    savings_monthly: float = 0.0
    risk: Risk = "medium"
    difficulty: Difficulty = "medium"
    improvement: str = ""
    explanation: dict[str, str] = Field(default_factory=dict)
    implementation: list[str] = Field(default_factory=list)


class ScoreCategory(BaseModel):
    key: str
    label: str
    score: float = 100.0
    max: float = 100.0
    weight: float = 0.0


class ProductionScores(BaseModel):
    overall: float = 0.0
    grade: str = "D"
    categories: list[ScoreCategory] = Field(default_factory=list)


class CostBreakdown(BaseModel):
    service: str
    monthly: float
    yearly: float
    pct: float = 0.0


class ProviderCost(BaseModel):
    provider: str
    label: str
    monthly: float
    yearly: float
    breakdown: dict[str, float] = Field(default_factory=dict)
    highlights: list[str] = Field(default_factory=list)


class ComparisonSchema(BaseModel):
    baseline_provider: str
    baseline_monthly: float
    providers: list[ProviderCost] = Field(default_factory=list)


class CarbonSchema(BaseModel):
    current_monthly_kg: float = 0.0
    optimized_monthly_kg: float = 0.0
    reduction_pct: float = 0.0
    greener_regions: list[str] = Field(default_factory=list)
    provider_carbon: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class FinOpsSchema(BaseModel):
    current_monthly: float = 0.0
    optimized_monthly: float = 0.0
    monthly_savings: float = 0.0
    annual_savings: float = 0.0
    savings_pct: float = 0.0
    by_service: list[CostBreakdown] = Field(default_factory=list)
    trend: list[dict[str, Any]] = Field(default_factory=list)
    top_resources: list[dict[str, Any]] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    label: str
    type: str = "resource"
    kind: str = ""
    group: str = "network"
    region: str = "global"
    status: str = "ok"
    metrics: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str = ""


class ArchitectureGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    groups: list[dict[str, Any]] = Field(default_factory=list)


class OptimizationRequest(BaseModel):
    mode: Literal[
        "lowest-cost",
        "max-availability",
        "lowest-latency",
        "lowest-carbon",
        "balanced",
        "startup-budget",
        "enterprise",
    ] = "balanced"
    region: str | None = None


class AnalysisRequest(BaseModel):
    mode: str = Field(default="balanced")
    region: str | None = None


class AnalysisSummary(BaseModel):
    id: int
    project_id: int
    status: str
    mode: str
    created_at: str
    summary: dict[str, Any] = Field(default_factory=dict)


class AnalysisDetail(BaseModel):
    id: int
    project_id: int
    status: str
    mode: str
    created_at: str
    resources: list[ResourceSchema] = Field(default_factory=list)
    graph: ArchitectureGraph = Field(default_factory=ArchitectureGraph)
    recommendations: list[RecommendationSchema] = Field(default_factory=list)
    scores: ProductionScores = Field(default_factory=ProductionScores)
    costs: dict[str, Any] = Field(default_factory=dict)
    comparison: ComparisonSchema = Field(default_factory=ComparisonSchema)
    carbon: CarbonSchema = Field(default_factory=CarbonSchema)
    finops: FinOpsSchema = Field(default_factory=FinOpsSchema)
    generated_code: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
