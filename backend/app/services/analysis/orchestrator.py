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

Everything is deterministic except the LLM narrative, which is powered by the
configured LLM provider (HuggingFace by default).

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
from app.services.llm.router import LLMConfigError
from app.services.llm.service import generate_review
from app.services.ml_scoring import predict as predict_ml
from app.services.optimization.engine import optimize
from app.services.optimization.render import render_generated_code
from app.services.pricing.comparison import compare_providers
from app.services.pricing.engine import estimate_all, estimate_all_detailed
from app.services.recommendations.engine import run_recommendations
from app.services.risk_intelligence.pipeline import classify_resources
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


def _finding_ml_classification(targets: list[str], by_id: dict[str, dict | None]) -> dict | None:
    """Resolve the advisory CRIM classification for a finding.

    A finding may target several resources; CRIM classifies the resource, not the
    rule. The classification is shared unchanged only when every targeted resource
    agreed, so rule identity never influences the ML input. Targets outside the
    classified resources (e.g. data sources) yield ``None``.
    """
    values = [by_id[target] for target in targets if target in by_id]
    if not values:
        return None
    first = values[0]
    if any(value != first for value in values):
        return None
    return first


def analyze(
    files: dict[str, str],
    mode: str = "balanced",
    provider: str = "aws",
    default_region: str = "us-east-1",
) -> dict:
    """Analyze Terraform files and return the complete analysis payload."""
    config = parse_terraform_files(files=files, provider=provider, default_region=default_region)

    crim_by_address, crim_summary = classify_resources(config)
    crim_by_id = {
        resource.id: crim_by_address.get(resource.address) for resource in config.resources
    }

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
    ml_predictions = []
    for resource in config.resources:
        if resource.is_data:
            continue
        prediction = predict_ml(resource)
        ml_predictions.append({"resource_id": resource.id, **prediction})
    scores["evidence_coverage_formula"] = (
        "sum(dimensions_with_evidence * weight) / sum(weight_of_dimensions_with_evidence)"
    )

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
    modules_payload = [m.to_dict() for m in config.modules]
    review_payload = {
        "scores": scores,
        "finops": finops,
        "recommendations": [r.to_dict() for r in recommendations],
        "resources": [r.to_dict() for r in config.resources],
        "modules": modules_payload,
        "config_summary": {
            "resource_types": sorted({r.resource_type for r in config.resources}),
            "services": sorted({r.service for r in config.resources}),
            "regions": sorted({r.region for r in config.resources if r.region}),
            "modules": [
                {
                    "module": m.address,
                    "source": m.source,
                    "version": m.version,
                    "expanded": m.expansion == "expanded",
                }
                for m in config.modules
            ],
        },
    }
    try:
        review = generate_review(review_payload)
    except LLMConfigError:
        review = _fallback_review(review_payload)

    # 7. Analysis metadata
    from app.core.config import get_settings

    settings = get_settings()
    metadata = _build_metadata(settings, config, scores, recommendations)

    # When no LLM provider is configured, the analysis is rule-engine only.
    # Strip ML classifications so the UI does not show ML badges that would
    # be misleading — the CRIM model output is advisory metadata, not a
    # full ML review.
    ml_available = metadata["llm_provider"] != "none"

    # Count assessed dimensions for score transparency
    assessed = sum(1 for c in scores["categories"] if c.get("evidence_status") == "available")
    total_dims = len(scores["categories"])

    unexpanded = config.unexpanded_modules()
    resource_count = len([r for r in config.resources if not r.is_data])
    data_source_count = len([r for r in config.resources if r.is_data])
    module_count = len(config.modules)

    return {
        "resources": [
            {
                **resource.to_dict(),
                "ml_classification": (
                    crim_by_address.get(resource.address) if ml_available else None
                ),
            }
            for resource in config.resources
        ],
        "modules": modules_payload,
        "graph": graph,
        "recommendations": [
            {
                **r.to_dict(),
                "ml_classification": (
                    _finding_ml_classification(r.target, crim_by_id) if ml_available else None
                ),
                "generated_code_hcl": render_generated_code(r.generated_code),
            }
            for r in recommendations
        ],
        "scores": scores,
        "costs": {
            "current_monthly": baseline_total,
            "known_monthly": baseline_total,
            "usage_monthly": usage_total,
            "usage_available": False,
            "confidence": total_confidence,
            "detailed": detailed_costs,
            # Unexpanded modules are infrastructure CloudPilot could not
            # price — reported explicitly instead of silently $0.
            "modules_unquantified": [
                {
                    "address": m.address,
                    "source": m.source,
                    "version": m.version,
                    "reason": (
                        "Module source was not available for resource-level pricing."
                        if m.expansion != "expanded"
                        else ""
                    ),
                }
                for m in unexpanded
            ],
        },
        "comparison": comparison,
        "carbon": carbon,
        "finops": finops,
        "optimization": plan.summary,
        "review": review,
        "ml": {
            "predictions": ml_predictions,
            "ml_unavailable": bool(ml_predictions)
            and all(prediction["ml_unavailable"] for prediction in ml_predictions),
        },
        "crim": crim_summary,
        "analysis_metadata": metadata,
        "summary": {
            "resource_count": resource_count,
            "data_source_count": data_source_count,
            "module_count": module_count,
            "unexpanded_module_count": len(unexpanded),
            "total_block_count": resource_count + data_source_count + module_count,
            "providers": sorted({r.provider for r in config.resources}),
            "services": sorted({r.service for r in config.resources}),
            "regions": sorted({r.region for r in config.resources}),
            "modules": modules_payload,
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
            "scope": scores.get("scope", "complete_configuration"),
            "scope_label": scores.get("scope_label", "Full configuration"),
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

    has_request = any(
        "requests" in d.get("assumptions", "").lower()
        or "invocations" in d.get("assumptions", "").lower()
        for d in detailed
    )
    if has_request:
        reasons.append("Request volumes not available")

    if not reasons:
        if fixed and not usage_based and not unknown:
            reasons.append("All costs are based on fixed, published pricing — high confidence")
        else:
            reasons.append("Cost estimates based on Terraform configuration and catalog pricing")

    return reasons


def _fallback_review(payload: dict) -> dict:
    """Deterministic review used when no LLM provider is configured.

    Mirrors the shape returned by :func:`generate_review` so downstream
    consumers need no special handling.
    """
    scores = payload.get("scores", {})
    finops = payload.get("finops", {})
    recommendations = payload.get("recommendations", [])

    grade = scores.get("grade", "N/A")
    overall = scores.get("overall")
    current = finops.get("current_monthly")
    optimized = finops.get("optimized_monthly")

    lines = [
        "## Automated review (LLM not configured)",
        "",
        "No LLM API key is configured, so this review was generated by the",
        "deterministic rules engine. Set `HF_API_KEY` (or another provider key)",
        "to enable narrative AI reviews.",
        "",
        f"- **Production readiness score:** {overall if overall is not None else 'N/A'} "
        f"(grade {grade})",
    ]
    if current is not None:
        line = f"- **Estimated monthly cost:** ${current:,.2f}"
        if optimized is not None and optimized < current:
            line += f" (optimized: ${optimized:,.2f})"
        lines.append(line)

    by_severity: dict[str, int] = {}
    for r in recommendations:
        sev = r.get("severity", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
    if by_severity:
        summary = ", ".join(f"{count} {sev}" for sev, count in sorted(by_severity.items()))
        lines.append(f"- **Findings:** {len(recommendations)} ({summary})")

    modules = payload.get("modules", [])
    unexpanded = [m for m in modules if not m.get("expanded")]
    if unexpanded:
        lines += [
            "",
            "**Modules detected but not expanded:**",
        ]
        for m in unexpanded:
            source = m.get("source") or "unknown source"
            version = f" v{m.get('version')}" if m.get("version") else ""
            lines.append(
                f"- `{m.get('module')}` — {source}{version}. Module source not "
                "included in upload; detailed module resource analysis unavailable."
            )
        lines.append(
            "\nModule costs are **not quantified** and the score reflects the "
            "root configuration only."
        )

    top = [r for r in recommendations if r.get("severity") in ("critical", "high")]
    if top:
        lines += ["", "**Priority actions:**"]
        for r in top[:5]:
            lines.append(f"- [{r.get('severity', '').upper()}] {r.get('title', 'Unknown')}")

    text = "\n".join(lines)

    return {
        "provider": "rule-engine",
        "executive_summary": text.split("\n\n")[0],
        "architecture_review": text,
        "top_severities": [],
        "guardrail_applied": False,
    }


def _build_metadata(settings, config, scores, recommendations) -> dict:
    """Build analysis metadata for transparency."""
    from app.services.llm.router import LLMConfigError, get_provider
    from app.services.recommendations.rules import ALL_RULES

    try:
        provider = get_provider(settings)
        provider_name = provider.name
    except LLMConfigError:
        provider_name = "none"

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
        "none": "Rule engine only",
    }.get(provider_name, provider_name)

    return {
        "llm_provider": provider_name,
        "llm_model": model_name,
        "llm_provider_label": provider_label,
        "rules_evaluated": len(ALL_RULES),
        "resources_parsed": len(config.resources),
        "modules_detected": len(config.modules),
        "modules_expanded": sum(1 for m in config.modules if m.expansion == "expanded"),
        "cost_estimates_confident": _aggregate_cost_confidence(
            estimate_all_detailed(config.resources)
        )["level"],
        "evidence_coverage": scores.get("evidence_coverage", "unknown"),
        "evidence_coverage_pct": scores.get("evidence_coverage_pct", 0.0),
    }
