"""Optimization engine: applies the selected optimization mode and produces the
optimized cost model plus downloadable, improved Terraform."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.optimization.render import render_optimized_project, validate_generated_code
from app.services.recommendations.models import Recommendation
from app.services.terraform.parser import TerraformConfig

# Mode metadata for UI + API
MODE_META = {
    "lowest-cost": {
        "label": "Lowest Cost",
        "description": "Aggressive FinOps: right-sizing, spot, shared NAT, gp3.",
        "icon": "Wallet",
    },
    "max-availability": {
        "label": "Maximum Availability",
        "description": "Multi-AZ, ASGs, health checks, alarms and DR posture.",
        "icon": "ShieldCheck",
    },
    "lowest-latency": {
        "label": "Lowest Latency",
        "description": "Edge caching, regional placement and connection tuning.",
        "icon": "Zap",
    },
    "lowest-carbon": {
        "label": "Lowest Carbon",
        "description": "Green regions, ARM compute and consolidation.",
        "icon": "Leaf",
    },
    "balanced": {
        "label": "Balanced",
        "description": "The senior-engineer default: cost + reliability + security.",
        "icon": "Scale",
    },
    "startup-budget": {
        "label": "Startup Budget",
        "description": "Ship fast and cheap: minimal managed services, spot compute.",
        "icon": "Rocket",
    },
    "enterprise": {
        "label": "Enterprise",
        "description": "Compliance, HA, DR, observability and governance first.",
        "icon": "Building2",
    },
}


@dataclass
class OptimizationPlan:
    mode: str
    label: str
    description: str
    applied: list[Recommendation] = field(default_factory=list)
    current_monthly: float = 0.0
    optimized_monthly: float = 0.0
    monthly_savings: float = 0.0
    generated_blocks: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def optimize(
    config: TerraformConfig,
    recommendations: list[Recommendation],
    current_monthly: float,
    mode: str = "balanced",
) -> OptimizationPlan:
    """Build an optimization plan for the requested mode.

    The optimized cost is the current cost minus the savings of recommendations
    whose categories are relevant to the selected mode (recs already carry the
    mode relevance via the engine's filtering).
    """
    meta = MODE_META.get(mode, MODE_META["balanced"])
    relevant = [r for r in recommendations if r.savings_monthly > 0 or r.generated_code]
    applied: list[Recommendation] = []
    savings = 0.0
    for rec in relevant:
        # Only count savings for this mode if the rec targets a cost lever
        if rec.savings_monthly > 0 and rec.category in ("cost", "networking", "security"):
            applied.append(rec)
            savings += rec.savings_monthly
        elif rec.generated_code and mode in ("balanced", "enterprise", "max-availability"):
            applied.append(rec)

    optimized = max(0.0, current_monthly - savings)
    blocks = [r.generated_code for r in applied if r.generated_code]
    generated_blocks: list[dict] = []
    for block in blocks:
        for resource_type, payload in block.items():
            if isinstance(payload, dict) and "name" in payload:
                generated_blocks.append(
                    {
                        "resource_type": resource_type,
                        "name": payload["name"],
                        "config": payload.get("config", {}),
                    }
                )

    plan = OptimizationPlan(
        mode=mode,
        label=meta["label"],
        description=meta["description"],
        applied=applied,
        current_monthly=round(current_monthly, 2),
        optimized_monthly=round(optimized, 2),
        monthly_savings=round(savings, 2),
        generated_blocks=generated_blocks,
    )
    plan.summary = {
        "mode": mode,
        "label": meta["label"],
        "description": meta["description"],
        "current_monthly": plan.current_monthly,
        "optimized_monthly": plan.optimized_monthly,
        "monthly_savings": plan.monthly_savings,
        "annual_savings": round(plan.monthly_savings * 12, 2),
        "savings_pct": round(plan.monthly_savings / max(plan.current_monthly, 1) * 100, 1),
        "applied_recommendations": len(applied),
        "generated_code_blocks": len(generated_blocks),
        "code": render_optimized_project(generated_blocks),
        "code_validation": validate_generated_code(generated_blocks),
    }
    return plan


def apply_optimization_to_resources(config: TerraformConfig, plan: OptimizationPlan) -> list[dict]:
    """Return the resource list annotated with optimized monthly costs.

    Recommendations that target a resource and carry savings are applied to the
    resource's optimized cost.
    """
    savings_by_target: dict[str, float] = {}
    for rec in plan.applied:
        per_target = rec.savings_monthly / max(len(rec.target), 1)
        for target in rec.target:
            savings_by_target[target] = savings_by_target.get(target, 0.0) + per_target

    result: list[dict] = []
    for res in config.resources:
        current = res.attributes.get("_monthly_cost", 0.0)
        optimized = max(0.0, current - savings_by_target.get(res.id, 0.0))
        d = res.to_dict()
        d["monthly_cost"] = round(current, 2)
        d["optimized_monthly_cost"] = round(optimized, 2)
        result.append(d)
    return result
