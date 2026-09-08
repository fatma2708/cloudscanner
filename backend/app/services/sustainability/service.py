"""Carbon / sustainability estimation.

Uses a simplified energy model to classify each region's grid carbon intensity
into qualitative ratings ("low", "moderate", "high") rather than producing
precise kgCO2e numbers.  This avoids giving users false precision while still
surfacing actionable sustainability insights: greener regions, Graviton
migration, and consolidation opportunities.

Key principles:
  - Never claim precise kgCO2e without documented methodology
  - Classify regions by grid carbon intensity category
  - Surface qualitative "potential" (minimal / moderate / significant) for
    optimization impact
  - Always include methodology notes so users know the source and limits
"""

from __future__ import annotations

import re

from app.services.pricing.catalog import GRID_INTENSITY, grid_intensity
from app.services.terraform.parser import TerraformConfig

HOURS_PER_MONTH = 730.0

# Grid intensity thresholds (gCO2e/kWh) — based on IEA 2023 averages
_GRID_LOW = 300  # e.g. eu-west-1, eu-central-1, us-west-2 (hydro)
_GRID_MODERATE = 450  # e.g. us-east-1, ap-southeast-1
_GRID_HIGH = 600  # e.g. ap-south-1, some coal-heavy regions

# Pattern for valid AWS region names (e.g. us-east-1, eu-west-2, ap-southeast-1)
_VALID_REGION_RE = re.compile(r"^[a-z]{2}-[a-z]+-[0-9]+$")


def _is_valid_region(region: str) -> bool:
    """Check if a string looks like a real AWS region, not a Terraform variable."""
    if not region or not isinstance(region, str):
        return False
    return bool(_VALID_REGION_RE.match(region))


def _region_rating(intensity: float) -> str:
    """Classify a region's grid carbon intensity."""
    if intensity <= _GRID_LOW:
        return "low"
    if intensity <= _GRID_MODERATE:
        return "moderate"
    return "high"


def _has_graviton(config: TerraformConfig) -> bool:
    """Check if any resource already uses ARM/Graviton."""
    for res in config.resources:
        instance_type = str(res.attributes.get("instance_type", ""))
        if instance_type.startswith(("m7g", "c7g", "r7g", "t4g", "m6g", "c6g", "r6g")):
            return True
    return False


def _compute_count(config: TerraformConfig, kind: str) -> int:
    """Count resources of a given kind."""
    return len([r for r in config.resources if r.kind == kind and not r.is_data])


def estimate_carbon(config: TerraformConfig, optimized_monthly: float) -> dict:
    """Produce the sustainability payload for the analysis.

    Returns qualitative ratings and actionable insights instead of precise
    kgCO2e numbers.
    """
    # Classify each region used in the config (skip Terraform variables like "var.region")
    region_ratings: dict[str, str] = {}
    regions_used: set[str] = set()
    for res in config.resources:
        if res.provider == "aws" and res.region and _is_valid_region(res.region):
            regions_used.add(res.region)
            if res.region not in region_ratings:
                intensity = grid_intensity(res.region)
                region_ratings[res.region] = _region_rating(intensity)

    # Find the dominant (most-used) region and its rating
    region_counts: dict[str, int] = {}
    for res in config.resources:
        if res.region and _is_valid_region(res.region):
            region_counts[res.region] = region_counts.get(res.region, 0) + 1
    dominant_region = max(region_counts, key=region_counts.get) if region_counts else "us-east-1"

    # Greener regions: regions with lower intensity than dominant
    dominant_intensity = grid_intensity(dominant_region)
    greener = [r for r, i in GRID_INTENSITY.items() if i < dominant_intensity * 0.7][:4]

    # Resource composition
    ec2_count = _compute_count(config, "ec2")
    rds_count = _compute_count(config, "rds")
    lambda_count = _compute_count(config, "lambda")
    has_graviton = _has_graviton(config)

    # Determine overall rating
    all_ratings = list(region_ratings.values())
    if all_ratings == ["low"] * len(all_ratings):
        overall = "low"
    elif all(r in ("low", "moderate") for r in all_ratings):
        overall = "moderate"
    else:
        overall = "high"

    # Determine optimization potential
    has_idle_compute = ec2_count > 2 or (ec2_count > 0 and rds_count > 0)
    potential = (
        "significant"
        if has_idle_compute
        else "moderate"
        if ec2_count > 0 or lambda_count > 0
        else "minimal"
    )

    # Qualitative notes
    notes: list[str] = []
    if greener:
        notes.append(
            f"Moving compute from {dominant_region} to a lower-carbon region "
            f"(e.g. {', '.join(greener[:2])}) could meaningfully reduce emissions."
        )
    if not has_graviton and ec2_count > 0:
        notes.append(
            "No Graviton (ARM) instances detected. Graviton instances typically "
            "draw ~20% less power per task than x86 equivalents."
        )
    if has_graviton:
        notes.append("Graviton (ARM) instances already in use — good energy efficiency posture.")
    if lambda_count > 0:
        notes.append(
            "Serverless (Lambda) functions scale to zero when idle, which is "
            "inherently more carbon-efficient than always-on compute."
        )
    if ec2_count > 2:
        notes.append(
            f"Found {ec2_count} EC2 instances. Consolidating idle compute is "
            "typically the single largest lever for both cost and carbon."
        )

    methodology = [
        "Region ratings based on IEA 2023 average grid carbon intensity (gCO2e/kWh)",
        "Classifications: low (<300), moderate (300-450), high (>450)",
        "Actual emissions vary by data center PUE, hardware generation, and utilization",
        "This is a qualitative assessment, not a precise carbon footprint measurement",
    ]

    return {
        "rating": overall,
        "greener_regions": greener,
        "region_emissions": region_ratings,
        "potential": potential,
        "methodology_notes": methodology,
        "notes": notes,
    }
