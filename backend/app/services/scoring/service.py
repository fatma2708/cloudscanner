"""Production Readiness Score.

Scores the infrastructure 0-100 across eight categories and produces an overall
grade. Category scores are derived from the recommendations emitted by the rules
engine plus structural signals from the parsed configuration (HA posture,
observability coverage, backup presence).

The scoring is deterministic and explainable: each deduction can be traced back
to a specific finding.

Key principles:
  - "No evidence of problem" is NOT the same as "excellent" (score 100).
    Categories with zero findings but also zero evidence examined are scored
    at 60 (neutral) instead of 100.
  - A+ (95+) is only achievable when evidence_coverage >= 80%.
  - Every finding deduction is scaled by the finding's confidence level.
  - The response includes an evidence_coverage field so the frontend can
    display "Evidence Coverage: 62%" alongside the score.
"""

from __future__ import annotations

from app.services.recommendations.models import Recommendation
from app.services.terraform.parser import TerraformConfig

# Category -> weight in the overall score
WEIGHTS = {
    "cost": 0.15,
    "security": 0.20,
    "reliability": 0.18,
    "performance": 0.12,
    "compliance": 0.10,
    "observability": 0.12,
    "maintainability": 0.08,
    "sustainability": 0.05,
}

CATEGORY_LABELS = {
    "cost": "Cost Efficiency",
    "security": "Security",
    "reliability": "Reliability",
    "performance": "Performance",
    "compliance": "Compliance",
    "observability": "Observability",
    "maintainability": "Maintainability",
    "sustainability": "Sustainability",
}

# Base deductions per severity; scaled by confidence at scoring time
_SEVERITY_DEDUCTION = {"critical": 20, "high": 12, "medium": 6, "low": 2}

# Confidence scaling: low-confidence findings deduct less
_CONFIDENCE_SCALE = {"high": 1.0, "medium": 0.75, "low": 0.5, "unknown": 0.3}

# When a category has zero findings AND zero evidence examined, use this
# neutral score instead of 100 — "absence of evidence is not evidence of
# absence".
_ZERO_EVIDENCE_SCORE = None  # sentinel — categories with no evidence get null, not a fake score

_GRADES = [
    (95, "A+"),
    (90, "A"),
    (85, "A-"),
    (80, "B+"),
    (75, "B"),
    (70, "B-"),
    (65, "C+"),
    (60, "C"),
    (55, "C-"),
    (50, "D+"),
    (40, "D"),
    (0, "F"),
]


def grade_for(score: float) -> str:
    for threshold, grade in _GRADES:
        if score >= threshold:
            return grade
    return "F"


def _structural_signals(config: TerraformConfig) -> dict[str, list[str]]:
    """Collect structural posture signals that affect score beyond rule findings.

    Only checks for actual aws_instance resources, not ECS or other compute.

    Absence-based signals ("no X found") are suppressed when the configuration
    contains unexpanded modules: the referenced resource types may live inside
    those modules, so absence cannot be established from the root config alone.
    """
    signals: dict[str, list[str]] = {cat: [] for cat in WEIGHTS}
    resources = [r for r in config.resources if not r.is_data]
    all_resources = config.resources
    kinds = [r.kind for r in resources]

    has_unexpanded = config.has_unexpanded_modules

    has_actual_instances = any(
        r.resource_type == "aws_instance" and not r.is_data for r in all_resources
    )
    has_asg = "asg" in kinds
    has_alb = "alb" in kinds
    has_rds = "rds" in kinds
    has_backup = "backup" in kinds
    has_alarms = "cloudwatch" in kinds
    has_iam = any(r.service == "security" and r.kind == "iam" for r in resources)
    has_sg = "security_group" in kinds
    has_nat = "nat" in kinds

    if has_actual_instances and not has_asg and not has_unexpanded:
        signals["performance"].append("EC2 instances are not managed by an Auto Scaling Group")
        signals["reliability"].append("EC2 instances have no auto-healing (no ASG)")
    if has_actual_instances and not has_alb and not has_asg and not has_unexpanded:
        signals["maintainability"].append("No load balancer in front of compute")
    if has_rds and not has_backup and not has_unexpanded:
        signals["reliability"].append("No backup plan found for databases")
    if has_actual_instances and not has_alarms and not has_unexpanded:
        signals["observability"].append("No CloudWatch alarms for compute")
    if not has_iam and not has_unexpanded:
        signals["compliance"].append("No IAM roles found (least-privilege posture unknown)")
    if has_nat and len([r for r in resources if r.kind == "nat"]) > 1:
        signals["cost"].append("Multiple NAT gateways without HA justification")
    if not has_sg and not has_unexpanded:
        signals["security"].append("No explicit security groups found")

    return signals


def _compute_evidence_coverage(
    config: TerraformConfig,
    recommendations: list[Recommendation],
    signals: dict[str, list[str]],
) -> tuple[str, float, list[str]]:
    """Compute evidence coverage: what % of the analyzed scope has at least one
    finding or an explicit 'no issue' evidence note.

    Unexpanded modules count as uninspected scope units: their contents were
    never examined, so they reduce coverage even though no resource list is
    known for them.

    Returns (level, pct, notes) where level is "high" / "medium" / "low".
    """
    billable = [r for r in config.resources if not r.is_data and r.billable]
    unexpanded = config.unexpanded_modules()
    total = len(billable)
    if total == 0 and not unexpanded:
        return "high", 100.0, ["No billable resources to evaluate"]

    # Resources that are targets of at least one recommendation
    covered_by_findings: set[str] = set()
    for rec in recommendations:
        for tid in rec.target:
            covered_by_findings.add(tid)

    # Resources covered by structural signals (implicit)
    covered_by_signals: set[str] = set()
    for items in signals.values():
        if items:
            # Signals are system-wide, so count all billable resources as covered
            for res in billable:
                covered_by_signals.add(res.id)

    covered = covered_by_findings | covered_by_signals
    # Denominator includes uninspected module units — each unexpanded module
    # represents infrastructure CloudPilot could not examine.
    effective_total = total + len(unexpanded)
    coverage = min(100.0, len(covered) / max(effective_total, 1) * 100)

    notes: list[str] = []
    notes.append(f"{len(covered_by_findings)} resource(s) have explicit findings")
    notes.append(f"{len(covered_by_signals)} resource(s) covered by structural signals")
    notes.append(f"{total} billable resources total")
    if unexpanded:
        addresses = ", ".join(m.address for m in unexpanded)
        notes.append(
            f"{len(unexpanded)} module(s) not expanded and therefore uninspected: {addresses}"
        )

    if coverage >= 80:
        level = "high"
    elif coverage >= 50:
        level = "medium"
    else:
        level = "low"

    return level, round(coverage, 1), notes


def compute_scores(config: TerraformConfig, recommendations: list[Recommendation]) -> dict:
    """Compute category scores, overall score and grade.

    Each category now includes an ``explanation`` dict with:
      - ``findings_detail``: list of {title, severity, confidence, deduction}
      - ``signals_detail``: list of structural signal descriptions
      - ``to_improve``: list of actionable next steps
      - ``evidence_examined``: whether any evidence was gathered for this category

    The top-level response includes:
      - ``evidence_coverage``: "high" / "medium" / "low"
      - ``evidence_coverage_pct``: numeric percentage
      - ``coverage_notes``: human-readable notes about what was examined
    """
    # Deductions from recommendations (scaled by confidence)
    deductions: dict[str, float] = {cat: 0.0 for cat in WEIGHTS}
    findings_by_cat: dict[str, list[dict]] = {cat: [] for cat in WEIGHTS}
    for rec in recommendations:
        cat = rec.category if rec.category in WEIGHTS else "maintainability"
        base_ded = _SEVERITY_DEDUCTION.get(rec.severity, 6)
        conf_scale = _CONFIDENCE_SCALE.get(rec.confidence, 0.5)
        ded = round(base_ded * conf_scale, 1)
        deductions[cat] += ded
        findings_by_cat[cat].append(
            {
                "title": rec.title,
                "severity": rec.severity,
                "confidence": rec.confidence,
                "deduction": ded,
            }
        )

    # Structural signals add a smaller flat deduction
    signals = _structural_signals(config)
    for cat, items in signals.items():
        deductions[cat] += len(items) * 3

    # Evidence coverage
    coverage_level, coverage_pct, coverage_notes = _compute_evidence_coverage(
        config, recommendations, signals
    )

    # Build category scores
    categories = []
    overall = 0.0
    categories_with_evidence = 0
    categories_with_evidence_weight = 0.0

    for cat, weight in WEIGHTS.items():
        has_evidence = bool(findings_by_cat[cat]) or bool(signals[cat])

        if has_evidence:
            # Normal scoring: start at 100, subtract deductions
            score = max(10.0, round(100.0 - deductions[cat], 1))
            categories_with_evidence += 1
            categories_with_evidence_weight += weight
        else:
            # No evidence examined: mark as insufficient, not a fake score
            score = None

        cat_findings = findings_by_cat[cat]
        cat_signals = signals[cat]

        actual_improve = []
        if cat_findings:
            actual_improve.append(
                f"Address {len(cat_findings)} finding(s) worth {deductions[cat]:.0f} deduction points"
            )
        if cat_signals:
            actual_improve.append(f"Resolve {len(cat_signals)} structural issue(s)")
        if not actual_improve:
            actual_improve.append("No issues detected — but limited evidence was examined")

        categories.append(
            {
                "key": cat,
                "label": CATEGORY_LABELS[cat],
                "score": score,
                "max": 100.0,
                "weight": round(weight * 100, 1),
                "deductions": round(deductions[cat], 1),
                "findings": len(cat_findings),
                "signals": cat_signals,
                "evidence_status": "available" if has_evidence else "insufficient_evidence",
                "explanation": {
                    "findings_detail": cat_findings,
                    "signals_detail": cat_signals,
                    "to_improve": actual_improve
                    if has_evidence
                    else [
                        "Insufficient evidence — no Terraform configuration signals found for this dimension"
                    ],
                    "evidence_examined": has_evidence,
                },
            }
        )
        if score is not None:
            overall += score * weight

    # Track unassessed categories for transparency
    unassessed = [CATEGORY_LABELS[c["key"]] for c in categories if c["score"] is None]

    # Calculate overall only from evidence-backed dimensions
    if categories_with_evidence == 0:
        overall = None
        grade = "N/A"
    else:
        # Normalize: score is weighted only across dimensions with evidence
        overall = (
            round(overall / categories_with_evidence_weight, 1)
            if categories_with_evidence_weight > 0
            else None
        )
        if overall is not None:
            grade = grade_for(overall)
            # A+ is only achievable when evidence coverage >= 80%
            if grade == "A+" and coverage_pct < 80:
                grade = "A"
                overall = min(overall, 94.9)

    # Scope transparency: when modules were detected but not expanded, the
    # score describes the ROOT configuration only — never the full
    # infrastructure. Cap the grade so hidden infrastructure cannot yield a
    # near-perfect readiness claim.
    unexpanded = config.unexpanded_modules()
    scope_notes: list[str] = []
    if unexpanded:
        addresses = ", ".join(m.address for m in unexpanded)
        scope_notes.append(
            f"{len(unexpanded)} module(s) not expanded ({addresses}); their "
            "contents were not assessed"
        )
        if overall is not None:
            overall = min(overall, 79.9)
            grade = grade_for(overall)

    return {
        "overall": overall,
        "grade": grade,
        "categories": categories,
        "evidence_coverage": coverage_level,
        "evidence_coverage_pct": coverage_pct,
        "coverage_notes": coverage_notes,
        "evidence_dimensions": _evidence_dimensions(config),
        "unassessed_categories": unassessed,
        "scope": "root_configuration_only" if unexpanded else "complete_configuration",
        "scope_label": "Root configuration only" if unexpanded else "Full configuration",
        "scope_notes": scope_notes,
        "modules_unexpanded": [m.address for m in unexpanded],
    }


def _evidence_dimensions(config: TerraformConfig) -> list[dict]:
    """Break down evidence availability into explicit dimensions.

    Each dimension has:
      - name: human-readable label
      - status: "available" | "partial" | "unavailable"
      - detail: explanation of what's available or missing
    """
    non_data = [r for r in config.resources if not r.is_data]
    has_compute = any(r.kind in ("ec2", "ecs", "eks", "lambda", "asg") for r in non_data)
    has_db = any(r.kind in ("rds", "elasticache", "dynamodb") for r in non_data)

    modules = config.modules
    unexpanded = [m for m in modules if m.expansion != "expanded"]
    expanded = [m for m in modules if m.expansion == "expanded"]

    if not modules:
        module_decls = {
            "name": "Module declarations",
            "status": "available",
            "detail": "No module blocks declared — configuration is self-contained",
        }
        module_contents = {
            "name": "Module contents",
            "status": "available",
            "detail": "No modules to inspect",
        }
    else:
        module_decls = {
            "name": "Module declarations",
            "status": "available",
            "detail": f"{len(modules)} module declaration(s) detected with source and configuration",
        }
        if not unexpanded:
            module_contents = {
                "name": "Module contents",
                "status": "available",
                "detail": f"All {len(expanded)} local module(s) expanded and inspected",
            }
        elif expanded:
            module_contents = {
                "name": "Module contents",
                "status": "partial",
                "detail": (
                    f"{len(expanded)} module(s) expanded; "
                    f"{len(unexpanded)} not inspected: " + ", ".join(m.address for m in unexpanded)
                ),
            }
        else:
            module_contents = {
                "name": "Module contents",
                "status": "unavailable",
                "detail": (
                    "Module source was not included in the upload — internals of "
                    + ", ".join(m.address for m in unexpanded)
                    + " were not inspected"
                ),
            }

    return [
        {
            "name": "Terraform root configuration",
            "status": "available",
            "detail": f"{len(non_data)} resource declaration(s) analyzed from HCL code",
        },
        module_decls,
        module_contents,
        {
            "name": "Runtime telemetry",
            "status": "unavailable",
            "detail": "CPU/memory utilization, request latency, and error rates require runtime monitoring data (CloudWatch metrics, APM, etc.)",
        },
        {
            "name": "Usage data",
            "status": "unavailable",
            "detail": "Actual traffic volume, request counts, and data transfer patterns are not available from Terraform alone",
        },
        {
            "name": "Pricing inputs",
            "status": "partial" if (has_compute or has_db) else "unavailable",
            "detail": "Instance types and storage sizes are known; request volume and data transfer inputs are unavailable",
        },
        {
            "name": "External provider data",
            "status": "unavailable",
            "detail": "Provider-specific pricing tiers, reserved capacity discounts, and negotiated rates are not available",
        },
    ]
