"""Multi-cloud comparison engine.

Translates an AWS Terraform workload into equivalent resources on every
supported provider, then estimates monthly cost. Each provider is evaluated
for *service equivalence* — whether the workload's managed services have
validated equivalents on the target provider. Providers without sufficient
equivalence are marked ``not_comparable`` or ``partially_comparable`` and
do NOT receive a fabricated price estimate.

Design principles:
  - A missing answer is better than a confidently wrong answer.
  - No provider is "Recommended" without validated equivalence.
  - Carbon numbers are not fabricated; only regional grid-intensity
    references are provided.
  - Performance labels are not assigned without benchmark data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.pricing.providers import ProviderCatalog, cheapest_vm, get_provider
from app.services.terraform.parser import TerraformConfig

# ---------------------------------------------------------------------------
# Service equivalence mapping
# ---------------------------------------------------------------------------

# AWS managed services that may NOT have direct equivalents on all providers.
# Each entry: (aws_kind, human_label, set of provider keys that have validated equivalents)
_EQUIVALENCE_MAP: dict[str, tuple[str, set[str]]] = {
    "ecs": ("ECS (managed containers)", {"aws", "azure", "google"}),
    "eks": ("EKS (managed Kubernetes)", {"aws", "azure", "google"}),
    "rds": ("RDS (managed database)", {"aws", "azure", "google", "oracle"}),
    "elasticache": ("ElastiCache (managed cache)", {"aws", "azure", "google"}),
    "dynamodb": ("DynamoDB (NoSQL)", {"aws", "azure", "google"}),
    "s3": (
        "S3 (object storage)",
        {
            "aws",
            "azure",
            "google",
            "digitalocean",
            "hetzner",
            "scaleway",
            "ovh",
            "oracle",
            "vultr",
            "linode",
        },
    ),
    "alb": (
        "ALB (managed load balancer)",
        {
            "aws",
            "azure",
            "google",
            "digitalocean",
            "hetzner",
            "scaleway",
            "ovh",
            "oracle",
            "vultr",
            "linode",
        },
    ),
    "elb": ("ELB (classic load balancer)", {"aws", "azure", "google"}),
    "nat": (
        "NAT Gateway (managed)",
        {"aws", "azure", "google", "digitalocean", "scaleway", "oracle"},
    ),
    "eip": (
        "Elastic IP",
        {
            "aws",
            "azure",
            "google",
            "digitalocean",
            "hetzner",
            "scaleway",
            "ovh",
            "oracle",
            "vultr",
            "linode",
        },
    ),
    "lambda": ("Lambda (serverless)", {"aws", "azure", "google", "digitalocean"}),
    "ec2": (
        "EC2 (VMs)",
        {
            "aws",
            "azure",
            "google",
            "digitalocean",
            "hetzner",
            "scaleway",
            "ovh",
            "oracle",
            "vultr",
            "linode",
        },
    ),
    "asg": ("Auto Scaling Group", {"aws", "azure", "google"}),
    "ebs": (
        "EBS (block storage)",
        {
            "aws",
            "azure",
            "google",
            "digitalocean",
            "hetzner",
            "scaleway",
            "ovh",
            "oracle",
            "vultr",
            "linode",
        },
    ),
    "efs": ("EFS (NFS)", {"aws", "azure", "google"}),
    "ecr": (
        "ECR (container registry)",
        {"aws", "azure", "google", "digitalocean", "hetzner", "scaleway", "ovh"},
    ),
    "cloudwatch": ("CloudWatch (monitoring)", {"aws", "azure", "google"}),
    "codepipeline": ("CodePipeline (CI/CD)", {"aws"}),
    "codebuild": ("CodeBuild (build)", {"aws"}),
    "codedeploy": ("CodeDeploy (deployment)", {"aws"}),
    "sns": ("SNS (notifications)", {"aws", "azure", "google"}),
    "sqs": ("SQS (queues)", {"aws", "azure", "google"}),
    "apigateway": ("API Gateway", {"aws", "azure", "google"}),
    "route53": ("Route53 (DNS)", {"aws"}),
    "cloudfront": ("CloudFront (CDN)", {"aws", "azure", "google"}),
    "waf": ("WAF (firewall)", {"aws", "azure", "google"}),
    "kms": ("KMS (encryption)", {"aws", "azure", "google"}),
}

# Services that are "infrastructure primitives" available everywhere
_PRIMITIVE_KINDS = {"vpc", "subnet", "igw", "eip", "security_group", "route_table", "route", "nacl"}


@dataclass
class Workload:
    compute: list[tuple[int, float]] = field(default_factory=list)  # (vcpu, ram_gb)
    block_gb: float = 0.0
    object_gb: float = 0.0
    efs_gb: float = 0.0
    dbs: list[tuple[int, float]] = field(default_factory=list)  # (vcpu, ram_gb)
    lbs: int = 0
    nats: int = 0
    eips: int = 0
    egress_gb: float = 100.0
    lambdas: int = 0

    @property
    def total_vcpu(self) -> int:
        return sum(v for v, _ in self.compute)


def build_workload(config: TerraformConfig) -> Workload:
    """Summarize a parsed configuration into a portable workload description."""
    wl = Workload()

    for res in config.resources:
        attrs = res.attributes

        if res.kind == "ec2" and res.service == "compute":
            from app.services.pricing.catalog import DEFAULT_EGRESS_GB, get_ec2

            spec = get_ec2(str(attrs.get("instance_type", "")))
            n = 1
            if spec:
                wl.compute.append((spec.vcpu * n, spec.ram_gb * n))
            else:
                wl.compute.append((2 * n, 4 * n))
            wl.egress_gb += DEFAULT_EGRESS_GB

        elif res.kind == "asg":
            from app.services.pricing.catalog import DEFAULT_EGRESS_GB

            min_size = attrs.get("min_size", 1)
            try:
                min_size = int(min_size) if isinstance(min_size, (int, float)) else 1
            except (TypeError, ValueError):
                min_size = 1
            wl.compute.append((2 * min_size, 4 * min_size))
            wl.egress_gb += DEFAULT_EGRESS_GB

        elif res.kind in ("eks", "ecs"):
            vcpu = attrs.get("vcpu") or 2
            ram = attrs.get("ram_gb") or 4
            try:
                vcpu = int(vcpu)
                ram = float(ram)
            except (TypeError, ValueError):
                vcpu, ram = 2, 4
            wl.compute.append((vcpu, ram))

        elif res.kind == "lambda":
            wl.lambdas += 1

        elif res.kind == "ebs":
            from app.services.pricing.catalog import DEFAULT_EBS_GB

            size = attrs.get("size", DEFAULT_EBS_GB)
            try:
                wl.block_gb += float(size)
            except (TypeError, ValueError):
                wl.block_gb += DEFAULT_EBS_GB

        elif res.kind == "efs":
            from app.services.pricing.catalog import DEFAULT_EFS_GB

            size = attrs.get("size_gb", DEFAULT_EFS_GB)
            try:
                wl.efs_gb += float(size)
            except (TypeError, ValueError):
                wl.efs_gb += DEFAULT_EFS_GB

        elif res.kind == "s3":
            from app.services.pricing.catalog import DEFAULT_S3_GB

            size = attrs.get("size_gb", DEFAULT_S3_GB)
            try:
                wl.object_gb += float(size)
            except (TypeError, ValueError):
                wl.object_gb += DEFAULT_S3_GB

        elif res.kind == "rds":
            from app.services.pricing.catalog import get_rds

            cls = str(attrs.get("instance_class") or attrs.get("instance_type") or "")
            spec = get_rds(cls)
            if spec:
                wl.dbs.append((spec.vcpu, spec.ram_gb))
            else:
                wl.dbs.append((2, 4))
            storage = attrs.get("allocated_storage", 100)
            try:
                wl.block_gb += float(storage)
            except (TypeError, ValueError):
                wl.block_gb += 100

        elif res.kind == "alb":
            wl.lbs += 1

        elif res.kind == "nat":
            wl.nats += 1

        elif res.kind == "eip":
            wl.eips += 1

    return wl


def _assess_equivalence(config: TerraformConfig, provider_key: str) -> dict:
    """Determine which AWS services have equivalents on the given provider.

    Returns:
        {
            "supported": [(kind, label), ...],
            "unsupported": [(kind, label), ...],
            "status": "comparable" | "partially_comparable" | "not_comparable",
            "coverage_pct": float (0-100),
        }
    """
    kinds_present: dict[str, str] = {}
    for res in config.resources:
        if res.is_data:
            continue
        if res.kind in _PRIMITIVE_KINDS or res.kind == "resource":
            continue
        if res.kind in _EQUIVALENCE_MAP and res.kind not in kinds_present:
            kinds_present[res.kind] = _EQUIVALENCE_MAP[res.kind][0]

    if not kinds_present:
        return {
            "supported": [],
            "unsupported": [],
            "status": "comparable",
            "coverage_pct": 100.0,
            "mapping_coverage_pct": 100.0,
            "architecture_equivalence": "high",
        }

    supported = []
    unsupported = []
    for kind, label in kinds_present.items():
        _, providers_with_equivalent = _EQUIVALENCE_MAP.get(kind, (kind, set()))
        if provider_key in providers_with_equivalent:
            supported.append({"kind": kind, "label": label})
        else:
            unsupported.append({"kind": kind, "label": label})

    total = len(kinds_present)
    n_supported = len(supported)
    coverage = (n_supported / total * 100) if total > 0 else 0.0

    if coverage >= 80:
        status = "comparable"
    elif coverage >= 40:
        status = "partially_comparable"
    else:
        status = "not_comparable"

    # Service mapping coverage = % of services that have equivalent on target provider
    # Architecture equivalence = qualitative assessment based on service parity
    arch_equivalence = "high" if coverage >= 90 else "medium" if coverage >= 60 else "low"

    return {
        "supported": supported,
        "unsupported": unsupported,
        "status": status,
        "coverage_pct": round(coverage, 1),
        "mapping_coverage_pct": round(coverage, 1),
        "architecture_equivalence": arch_equivalence,
    }


def estimate_provider(provider: ProviderCatalog, wl: Workload) -> dict:
    """Estimate monthly cost breakdown for a single provider given a workload."""
    monthly = 0.0
    breakdown: dict[str, float] = {}

    compute = sum(cheapest_vm(provider, vcpu, ram).monthly for vcpu, ram in wl.compute)
    monthly += compute
    breakdown["Compute"] = round(compute, 2)

    dbs = sum(
        cheapest_vm(provider, vcpu, ram).monthly * provider.managed_db_factor
        for vcpu, ram in wl.dbs
    )
    monthly += dbs
    breakdown["Databases"] = round(dbs, 2)

    storage = (
        wl.block_gb * provider.block_storage_gb
        + wl.object_gb * provider.object_storage_gb
        + wl.efs_gb * provider.block_storage_gb
    )
    monthly += storage
    breakdown["Storage"] = round(storage, 2)

    lb = wl.lbs * provider.lb_monthly
    nat = wl.nats * provider.nat_monthly
    eip = wl.eips * provider.eip_monthly
    networking = lb + nat + eip
    monthly += networking
    breakdown["Networking"] = round(networking, 2)

    egress = wl.egress_gb * provider.egress_gb
    monthly += egress
    breakdown["Data Transfer"] = round(egress, 2)

    monthly = max(0.0, monthly - provider.monthly_free_tier)
    return {"monthly": round(monthly, 2), "breakdown": breakdown}


def compare_providers(
    config: TerraformConfig,
    baseline_provider: str = "aws",
    baseline_cost: float | None = None,
    canonical_categories: dict[str, float] | None = None,
) -> dict:
    """Produce the full comparison payload for all supported providers.

    ``canonical_categories`` is the authoritative comparison-category breakdown
    from the orchestrator's CanonicalCostModel. For the baseline provider,
    this MUST be used instead of the independent workload estimate to ensure
    the breakdown total matches the canonical baseline.
    """
    wl = build_workload(config)
    results: list[dict] = []

    for catalog in _ordered_providers(baseline_provider):
        equiv = _assess_equivalence(config, catalog.key)

        if equiv["status"] == "not_comparable":
            results.append(
                {
                    "provider": catalog.key,
                    "label": catalog.label,
                    "region": catalog.region,
                    "status": "not_comparable",
                    "comparison_confidence": "none",
                    "estimated_monthly_cost": None,
                    "yearly": None,
                    "breakdown": None,
                    "unsupported_services": [s["label"] for s in equiv["unsupported"]],
                    "supported_services": [s["label"] for s in equiv["supported"]],
                    "coverage_pct": equiv["coverage_pct"],
                    "mapping_coverage_pct": equiv["mapping_coverage_pct"],
                    "architecture_equivalence": equiv["architecture_equivalence"],
                    "availability": catalog.availability,
                    "notes": list(catalog.notes),
                    "sustainability_note": "Regional carbon-intensity reference available",
                    "delta_vs_baseline": None,
                    "delta_pct": None,
                    "cost_type": None,
                }
            )
            continue

        estimate = estimate_provider(catalog, wl)

        confidence = "high"
        if equiv["status"] == "partially_comparable":
            confidence = "low"
        elif len(wl.dbs) > 0 or wl.lambdas > 0:
            confidence = "medium"

        results.append(
            {
                "provider": catalog.key,
                "label": catalog.label,
                "region": catalog.region,
                "status": equiv["status"],
                "comparison_confidence": confidence,
                "estimated_monthly_cost": estimate["monthly"],
                "yearly": round(estimate["monthly"] * 12, 2),
                "breakdown": estimate["breakdown"],
                "unsupported_services": [s["label"] for s in equiv["unsupported"]],
                "supported_services": [s["label"] for s in equiv["supported"]],
                "coverage_pct": equiv["coverage_pct"],
                "mapping_coverage_pct": equiv["mapping_coverage_pct"],
                "architecture_equivalence": equiv["architecture_equivalence"],
                "availability": catalog.availability,
                "notes": list(catalog.notes),
                "sustainability_note": "Regional carbon-intensity reference available",
                "delta_vs_baseline": None,
                "delta_pct": None,
                "cost_type": "estimated",
            }
        )

    baseline = next((r for r in results if r["provider"] == baseline_provider), None)
    baseline_monthly = (
        baseline_cost
        if baseline_cost is not None
        else (baseline["estimated_monthly_cost"] if baseline else 0.0)
    )

    if baseline_cost is not None and baseline:
        baseline["estimated_monthly_cost"] = round(baseline_cost, 2)
        baseline["yearly"] = round(baseline_cost * 12, 2)
        # Mark baseline cost as "known_baseline" - usage-dependent charges are not included
        baseline["cost_type"] = "known_baseline"

        # Use canonical categories for the baseline breakdown (NOT independent estimate)
        if canonical_categories is not None:
            baseline["breakdown"] = {k: round(v, 2) for k, v in canonical_categories.items()}
        elif baseline["breakdown"] and baseline["estimated_monthly_cost"] != baseline_cost:
            # Fallback: scale proportionally if canonical not provided
            orig = estimate_provider(get_provider(baseline_provider), wl)
            if orig["monthly"] > 0:
                factor = baseline_cost / orig["monthly"]
                baseline["breakdown"] = {
                    k: round(v * factor, 2) for k, v in baseline["breakdown"].items()
                }

    for r in results:
        if (
            r["provider"] != baseline_provider
            and r["estimated_monthly_cost"] is not None
            and baseline_monthly is not None
        ):
            delta = r["estimated_monthly_cost"] - baseline_monthly
            r["delta_vs_baseline"] = round(delta, 2)
            r["delta_pct"] = round(delta / max(baseline_monthly, 1) * 100, 1)

    return {
        "baseline_provider": baseline_provider,
        "baseline_monthly": baseline_monthly,
        "providers": results,
    }


def _ordered_providers(baseline: str) -> list[ProviderCatalog]:
    """Return providers with the baseline first."""
    keys = [
        baseline,
        *[
            k
            for k in (
                "aws",
                "azure",
                "google",
                "digitalocean",
                "hetzner",
                "scaleway",
                "ovh",
                "oracle",
                "vultr",
                "linode",
            )
            if k != baseline
        ],
    ]
    return [get_provider(k) for k in keys]
