"""Recommendation engine: runs all rules, filters by optimization mode and sorts."""

from __future__ import annotations

from app.services.recommendations.models import MODE_TAGS, Recommendation
from app.services.recommendations.rules import ALL_RULES
from app.services.terraform.parser import TerraformConfig

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _resolve_source_locations(
    config: TerraformConfig, recs: list[Recommendation]
) -> None:
    """Populate source_file and source_line from target resources.

    Rules don't know about source locations; the engine resolves them from
    the target resource IDs after all rules have run.
    """
    by_id = {r.id: r for r in config.resources}
    for rec in recs:
        if rec.source_file or rec.source_line:
            continue  # already set by the rule
        for target_id in rec.target:
            res = by_id.get(target_id)
            if res and res.module:
                rec.source_file = res.module
                rec.source_line = res.line
                break


def run_recommendations(config: TerraformConfig, mode: str = "balanced") -> list[Recommendation]:
    """Run every rule, filter to the requested optimization mode, dedupe & sort."""
    mode = mode if mode in MODE_TAGS else "balanced"
    allowed_categories = MODE_TAGS[mode]

    collected: dict[str, Recommendation] = {}
    for _, rule_fn in ALL_RULES:
        try:
            for rec in rule_fn(config):
                # Category relevance filter for the selected mode
                if mode != "balanced" and rec.category not in allowed_categories:
                    continue
                if rec.category in ("security", "compliance") and mode in (
                    "lowest-cost",
                    "startup-budget",
                    "lowest-carbon",
                    "lowest-latency",
                ):
                    if rec.category == "compliance" and mode in (
                        "lowest-cost",
                        "lowest-carbon",
                        "startup-budget",
                        "lowest-latency",
                    ):
                        continue
                collected[rec.key] = rec
        except Exception:
            # A single broken rule must never sink the whole analysis
            continue

    recs = list(collected.values())

    # Auto-populate source locations from target resources
    _resolve_source_locations(config, recs)

    recs.sort(key=lambda r: (SEVERITY_RANK.get(r.severity, 9), -r.savings_monthly))
    return recs
