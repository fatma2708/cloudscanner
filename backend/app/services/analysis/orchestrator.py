"""Analysis orchestrator.

Runs the full CloudPilot pipeline on a set of Terraform files:

1. Parse + normalize into an infrastructure graph (``terraform``)
2. Estimate cost per resource (``pricing``)
3. Run the rules engine -> recommendations (``recommendations``)
4. Compute the production readiness score (``scoring``)
5. Build the optimization plan + generated code (``optimization``)
6. Compute the FinOps dashboard (``finops``)
7. Compare providers (``pricing.comparison``)
8. Estimate carbon (``sustainability``)
9. Build the interactive architecture graph (``architecture``)
10. Generate the narrative architecture review (``llm``)

Everything is deterministic except the LLM narrative, which degrades gracefully.

**Canonical Cost Model**:
    There is exactly ONE source of truth for every cost number.
    ``baseline_total`` is the authoritative monthly cost from Terraform config
    (deterministic, no usage assumptions). Every downstream consumer
    (Overview, FinOps, Cloud Compare) MUST use this same number and derive
    category totals from the same per-resource known costs.
"""

from __future__ import annotations

from app.services.architecture.service import build_graph
from app.services.finops.service import build_finops
from app.services.llm.service import generate_review
from app.services.optimization.engine import optimize
from app.services.pricing.comparison import compare_providers
from app.services.pricing.engine import estimate_all, estimate_all_detailed
from app.services.recommendations.engine import run_recommendations
from app.services.scoring.service import compute_scores
from app.services.sustainability.service import estimate_carbon
from app.services.terraform.parser import parse_terraform_files

# Service group mapping for Cloud Compare categories.
# Maps resource service groups to comparison categories.
# Both FinOps (by_service) and Cloud Compare (by_category) must sum to
# the same baseline_total, just with different groupings.
_COMPARE_CATEGORIES = {
    "compute": "Compute",
    "network": "Networking",
    "storage": "Storage",
    "database": "Databases",
    "messaging": "Messaging",
    "dns": "Networking",
    "security": "Networking",
    "observability": "Compute",
    "reliability": "Storage",
    "data": "Compute",
}


def analyze(
    files: dict[str, str],
    mode: str = "balanced",
    provider: str = "aws",
    default_region: str = "us-east-1",
) -> dict:
    """Analyze Terraform files and return the complete analysis payload."""
    config = parse_terraform_files(files=files, provider=provider, default_region=default_region)

    # 1. Costs
    costs = estimate_all(config.resources)
    detailed_costs = estimate_all_detailed(config.resources)

    # Build the canonical cost model — ONE source of truth.
    # Compute baseline from detailed_costs (known_cost only, no usage assumptions).
    # Compute from config.resources directly (deduplicated) to avoid
    # parser duplicate-resource-ID issues inflating totals.
    baseline_total = 0.0
    usage_total = 0.0
    resource_known_costs: dict[str, float] = {}
    resource_usage_costs: dict[str, float] = {}

    finops_categories: dict[str, float] = {}
    compare_categories: dict[str, float] = {}
    seen_ids: set[str] = set()

    # Build a lookup of known_cost from detailed costs
    detailed_known: dict[str, float] = {}
    detailed_usage: dict[str, float] = {}
    for d in detailed_costs:
        detailed_known[d["resource_id"]] = d.get("known_cost", 0.0)
        detailed_usage[d["resource_id"]] = d.get("usage_cost", 0.0)

    for res in config.resources:
        if res.is_data or not res.billable:
            continue
        if res.id in seen_ids:
            continue
        seen_ids.add(res.id)

        known = round(detailed_known.get(res.id, 0.0), 2)
        usage = round(detailed_usage.get(res.id, 0.0), 2)

        resource_known_costs[res.id] = known
        resource_usage_costs[res.id] = usage
        baseline_total += known
        # usage_total is intentionally NOT accumulated here.
        # Usage-dependent charges are not quantified in the normal analysis flow.
        # They are only estimated when the user explicitly selects a scenario.

        # FinOps grouping (by service)
        finops_categories[res.service] = finops_categories.get(res.service, 0.0) + known

        # Cloud Compare grouping (by comparison category)
        compare_cat = _COMPARE_CATEGORIES.get(res.service, "Compute")
        compare_categories[compare_cat] = compare_categories.get(compare_cat, 0.0) + known

    baseline_total = round(baseline_total, 2)
    usage_total = 0.0

    # Round categories
    finops_categories = {k: round(v, 2) for k, v in finops_categories.items()}
    compare_categories = {k: round(v, 2) for k, v in compare_categories.items()}

    # Build lookup for cost classification and confidence per resource
    cost_detail_map: dict[str, dict] = {d["resource_id"]: d for d in detailed_costs}

    for res in config.resources:
        res.attributes["_monthly_cost"] = costs.get(res.id, 0.0)
        detail = cost_detail_map.get(res.id, {})
        res.attributes["_cost_classification"] = detail.get("cost_classification", "unknown")
        res.attributes["_cost_confidence"] = detail.get("confidence", "unknown")

    # Detailed costs with confidence levels and classification
    total_confidence = _aggregate_cost_confidence(detailed_costs)

    # 2. Recommendations + scores
    recommendations = run_recommendations(config, mode=mode)
    scores = compute_scores(config, recommendations)
    scores["evidence_coverage_formula"] = "sum(dimensions_with_evidence * weight) / sum(weight_of_dimensions_with_evidence)"

    # 3. Optimization plan (uses canonical baseline)
    plan = optimize(config, recommendations, current_monthly=baseline_total, mode=mode)

    # 4. FinOps — uses canonical cost model categories
    finops = build_finops(
        config=config,
        resources_cost=costs,
        recommendations=recommendations,
        current_monthly=baseline_total,
        optimized_monthly=plan.optimized_monthly,
        canonical_categories=finops_categories,
        usage_monthly=usage_total,
        usage_available=False,
    )

    # 5. Comparison — uses canonical cost model for baseline provider
    comparison = compare_providers(
        config,
        baseline_provider=config.provider,
        baseline_cost=baseline_total,
        canonical_categories=compare_categories,
    )
    carbon = estimate_carbon(config, plan.optimized_monthly)
    graph = build_graph(config)

    # 6. Narrative review (pass full config context for LLM guardrails)
    review_payload = {
        "scores": scores,
        "finops": finops,
        "recommendations": [r.to_dict() for r in recommendations],
        "resources": [r.to_dict() for r in config.resources],
        "config_summary": {
            "resource_types": sorted({r.resource_type for r in config.resources}),
            "services": sorted({r.service for r in config.resources}),
            "regions": sorted({r.region for r in config.resources if r.region}),
            "modules": config.modules,
        },
    }
    review = generate_review(review_payload)

    # 7. Analysis metadata
    from app.core.config import get_settings
    settings = get_settings()
    metadata = _build_metadata(settings, config, scores, recommendations)

    # Count assessed dimensions for score transparency
    assessed = sum(1 for c in scores["categories"] if c.get("evidence_status") == "available")
    total_dims = len(scores["categories"])

    return {
        "resources": [r.to_dict() for r in config.resources],
        "graph": graph,
        "recommendations": [r.to_dict() for r in recommendations],
        "scores": scores,
        "costs": {
            "current_monthly": baseline_total,
            "known_monthly": baseline_total,
            "usage_monthly": usage_total,
            "usage_available": False,
            "confidence": total_confidence,
            "detailed": detailed_costs,
        },
        "comparison": comparison,
        "carbon": carbon,
        "finops": finops,
        "optimization": plan.summary,
        "review": review,
        "analysis_metadata": metadata,
        "summary": {
            "resource_count": len([r for r in config.resources if not r.is_data]),
            "data_source_count": len([r for r in config.resources if r.is_data]),
            "total_block_count": len(config.resources),
            "providers": sorted({r.provider for r in config.resources}),
            "services": sorted({r.service for r in config.resources}),
            "regions": sorted({r.region for r in config.resources}),
            "modules": config.modules,
            "variables": list(config.variables.keys()),
            "current_monthly": baseline_total,
            "known_monthly": baseline_total,
            "usage_monthly": usage_total,
            "usage_available": False,
            "cost_confidence": total_confidence,
            "optimized_monthly": plan.optimized_monthly,
            "monthly_savings": plan.monthly_savings,
            "annual_savings": round(plan.monthly_savings * 12, 2),
            "score": scores["overall"],
            "grade": scores["grade"],
            "dimensions_assessed": assessed,
            "dimensions_total": total_dims,
            "evidence_coverage": scores.get("evidence_coverage", "unknown"),
            "evidence_coverage_pct": scores.get("evidence_coverage_pct", 0.0),
        },
    }


def _aggregate_cost_confidence(detailed: list[dict]) -> dict:
    """Aggregate per-resource confidence into an overall cost confidence level.

    Returns a dict with:
      - level: "high" | "medium" | "low" | "unknown"
      - breakdown: counts per confidence level
      - notes: list of human-readable notes about the estimate
    """
    counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    notes: list[str] = []
    seen_notes: set[str] = set()

    for item in detailed:
        conf = item.get("confidence", "unknown")
        counts[conf] = counts.get(conf, 0) + 1
        assumption = item.get("assumptions", "")
        if assumption and assumption not in seen_notes:
            notes.append(assumption)
            seen_notes.add(assumption)

    # Overall confidence = lowest confidence of any cost-bearing resource
    if counts.get("unknown", 0) > 0:
        level = "unknown"
    elif counts.get("low", 0) > 0:
        level = "low"
    elif counts.get("medium", 0) > 0:
        level = "medium"
    else:
        level = "high"

    return {
        "level": level,
        "breakdown": counts,
        "notes": notes,
        "reasons": _cost_confidence_reasons(detailed),
    }


def _cost_confidence_reasons(detailed: list[dict]) -> list[str]:
    """Generate human-readable reasons explaining why cost confidence is at its current level."""
    reasons: list[str] = []

    usage_based = [d for d in detailed if d.get("cost_classification") == "usage_based"]
    unknown = [d for d in detailed if d.get("confidence") == "unknown"]
    estimated = [d for d in detailed if d.get("cost_classification") == "estimated"]
    fixed = [d for d in detailed if d.get("cost_classification") == "fixed"]

    if usage_based:
        kinds = sorted({d["kind"] for d in usage_based})
        reasons.append(f"Runtime usage data unavailable for: {', '.join(kinds)}")

    if unknown:
        kinds = sorted({d["kind"] for d in unknown})
        reasons.append(f"Pricing data insufficient for: {', '.join(kinds)}")

    has_transfer = any("egress" in d.get("assumptions", "").lower() for d in detailed)
    if has_transfer:
        reasons.append("Data transfer volumes not available")

    has_request = any("requests" in d.get("assumptions", "").lower() or "invocations" in d.get("assumptions", "").lower() for d in detailed)
    if has_request:
        reasons.append("Request volumes not available")

    if not reasons:
        if fixed and not usage_based and not unknown:
            reasons.append("All costs are based on fixed, published pricing — high confidence")
        else:
            reasons.append("Cost estimates based on Terraform configuration and catalog pricing")

    return reasons


def _build_metadata(settings, config, scores, recommendations) -> dict:
    """Build analysis metadata for transparency."""
    from app.services.recommendations.rules import ALL_RULES
    from app.services.llm.router import get_provider

    provider = get_provider(settings)
    provider_name = provider.name if provider else "deterministic-fallback"

    # Resolve display model name from settings
    model_name = ""
    if provider_name == "huggingface":
        model_name = settings.hf_model.split("/")[-1] if settings.hf_model else ""
    elif provider_name == "openai":
        model_name = settings.openai_model
    elif provider_name == "anthropic":
        model_name = settings.anthropic_model
    elif provider_name == "gemini":
        model_name = settings.gemini_model

    provider_label = {
        "huggingface": "Hugging Face",
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "gemini": "Google Gemini",
    }.get(provider_name, "Deterministic")

    return {
        "llm_provider": provider_name,
        "llm_model": model_name,
        "llm_provider_label": provider_label,
        "rules_evaluated": len(ALL_RULES),
        "resources_parsed": len(config.resources),
        "cost_estimates_confident": _aggregate_cost_confidence(
            estimate_all_detailed(config.resources)
        )["level"],
        "evidence_coverage": scores.get("evidence_coverage", "unknown"),
        "evidence_coverage_pct": scores.get("evidence_coverage_pct", 0.0),
    }
