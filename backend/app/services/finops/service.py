"""FinOps dashboard computation.

Turns the parsed resources + recommendations into the numbers a finance team
cares about: current vs. optimized spend, savings, cost by service, a 12-month
trend projection and the top-cost resources.
"""

from __future__ import annotations

from app.services.recommendations.models import Recommendation
from app.services.terraform.parser import TerraformConfig

SERVICE_LABELS = {
    "compute": "Compute",
    "network": "Networking",
    "storage": "Storage",
    "database": "Databases",
    "messaging": "Messaging",
    "dns": "DNS & CDN",
    "security": "Security & IAM",
    "observability": "Observability",
    "reliability": "Backup & DR",
    "data": "Analytics",
}


def build_finops(
    config: TerraformConfig,
    resources_cost: dict[str, float],
    recommendations: list[Recommendation],
    current_monthly: float,
    optimized_monthly: float,
    canonical_categories: dict[str, float] | None = None,
    usage_monthly: float = 0.0,
    usage_available: bool = False,
) -> dict:
    """Compute the full FinOps dashboard payload.

    ``canonical_categories`` is the authoritative service-group breakdown
    from the orchestrator's CanonicalCostModel. It MUST be used for the
    by_service display — do NOT recalculate from resources_cost, which may
    include usage-dependent charges that inflate the total.
    """

    # --- by service: use canonical categories when available ---
    if canonical_categories is not None:
        by_service = []
        for service, total in sorted(canonical_categories.items(), key=lambda kv: -kv[1]):
            by_service.append(
                {
                    "service": service,
                    "service_label": SERVICE_LABELS.get(service, service.title()),
                    "monthly": round(total, 2),
                    "yearly": round(total * 12, 2),
                    "pct": round(total / max(current_monthly, 0.01) * 100, 1),
                }
            )
        # Verify reconciliation
        cat_sum = round(sum(s["monthly"] for s in by_service), 2)
        assert abs(cat_sum - round(current_monthly, 2)) < 0.10, (
            f"FinOps by_service sum {cat_sum} != current_monthly {current_monthly}"
        )
    else:
        # Fallback: compute from resources_cost (legacy path)
        service_totals: dict[str, float] = {}
        for res in config.resources:
            cost = resources_cost.get(res.id, 0.0)
            service_totals[res.service] = service_totals.get(res.service, 0.0) + cost
        by_service = []
        for service, total in sorted(service_totals.items(), key=lambda kv: -kv[1]):
            by_service.append(
                {
                    "service": service,
                    "service_label": SERVICE_LABELS.get(service, service.title()),
                    "monthly": round(total, 2),
                    "yearly": round(total * 12, 2),
                    "pct": round(total / max(current_monthly, 0.01) * 100, 1),
                }
            )

    # Top resources from config
    top_resources: list[dict] = []
    for res in config.resources:
        cost = resources_cost.get(res.id, 0.0)
        top_resources.append(
            {
                "id": res.id,
                "name": res.type_name,
                "label": res.label,
                "service": res.service,
                "service_label": SERVICE_LABELS.get(res.service, res.service.title()),
                "monthly_cost": round(cost, 2),
                "region": res.region,
            }
        )
    top_resources.sort(key=lambda r: r["monthly_cost"], reverse=True)
    top_resources = top_resources[:10]

    # --- 12-month trend (optimization applied from month 2) ---
    trend = []
    for i in range(1, 13):
        month_label = f"M{i}"
        base = current_monthly
        optimized = optimized_monthly if i > 1 else current_monthly
        trend.append(
            {
                "month": month_label,
                "current": round(base, 2),
                "optimized": round(optimized, 2),
                "savings": round(max(0, base - optimized), 2),
            }
        )

    monthly_savings = max(0.0, current_monthly - optimized_monthly)
    return {
        "current_monthly": round(current_monthly, 2),
        "optimized_monthly": round(optimized_monthly, 2),
        "monthly_savings": round(monthly_savings, 2),
        "annual_savings": round(monthly_savings * 12, 2),
        "savings_pct": round(monthly_savings / max(current_monthly, 0.01) * 100, 1),
        "usage_monthly": round(usage_monthly, 2),
        "usage_available": usage_available,
        "by_service": by_service,
        "trend": trend,
        "top_resources": top_resources,
        "service_labels": SERVICE_LABELS,
    }
