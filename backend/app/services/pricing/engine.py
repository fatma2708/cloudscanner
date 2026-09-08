"""Resource-level cost estimation engine.

Estimates a defensible monthly USD cost for every normalized resource using the
AWS pricing catalog. The estimates feed the FinOps dashboard, the recommendation
engine (savings), the cross-provider comparison and the sustainability model.
"""

from __future__ import annotations

from app.services.pricing import catalog
from app.services.terraform.parser import Resource

MONTHLY_HOURS = catalog.MONTHLY_HOURS


def _count_of(resource: Resource) -> int:
    """Estimate how many instances of a resource exist (count / for_each)."""
    attrs = resource.attributes
    count = attrs.get("count")
    if isinstance(count, int):
        return max(1, count)
    if isinstance(count, str) and count.isdigit():
        return max(1, int(count))
    for_each = attrs.get("for_each")
    if isinstance(for_each, dict):
        return max(1, len(for_each))
    if isinstance(for_each, list):
        return max(1, len(for_each))
    return 1


def _is_spot(resource: Resource) -> bool:
    attrs = resource.attributes
    if attrs.get("instance_market_options") is not None:
        return True
    lifecycle = attrs.get("lifecycle")
    if isinstance(lifecycle, list) and lifecycle:
        if any("create_before_destroy" in lc for lc in lifecycle):
            pass
    return bool(attrs.get("spot_price") is not None or attrs.get("capacity_type") in ("SPOT",))


def _num(resource: Resource, key: str, default: float) -> float:
    value = resource.attr(key, default)
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.isdigit():
        return float(value)
    return float(default)


def _egress_cost(resource: Resource, data_gb: float | None = None) -> float:
    gb = data_gb if data_gb is not None else catalog.DEFAULT_EGRESS_GB
    return gb * catalog.PER_UNIT["data_transfer_egress"]


# --------------------------------------------------------------------------- handlers


def _ec2(resource: Resource) -> float:
    spec = catalog.get_ec2(str(resource.attr("instance_type", catalog.DEFAULT_EC2)))
    if spec is None:
        spec = catalog.get_ec2(catalog.DEFAULT_EC2)
    base = spec.monthly
    if _is_spot(resource):
        base *= catalog.SPOT_DISCOUNT
    cost = base * _count_of(resource)
    cost += _egress_cost(resource)
    return round(cost, 2)


def _asg(resource: Resource) -> float:
    min_size = int(_num(resource, "min_size", 1))
    return round(_egress_cost(resource) + catalog.get_ec2("t3.medium").monthly * min_size, 2)


def _rds(resource: Resource) -> float:
    cls = str(resource.attr_any("instance_class", "instance_type", default=catalog.DEFAULT_RDS))
    spec = catalog.get_rds(cls) or catalog.get_rds(catalog.DEFAULT_RDS)
    storage_gb = _num(resource, "allocated_storage", 100)
    cost = spec.monthly + storage_gb * catalog.STORAGE_GB["ebs_gp3"]
    if resource.attr("multi_az") is True:
        cost += spec.monthly  # second AZ doubles compute
    return round(cost, 2)


def _ebs(resource: Resource) -> float:
    size = _num(resource, "size", catalog.DEFAULT_EBS_GB)
    vol_type = str(resource.attr("type", "gp3"))
    per_gb = catalog.STORAGE_GB.get(
        {"gp2": "ebs_gp2", "io1": "ebs_io1", "standard": "ebs_standard"}.get(vol_type, "ebs_gp3"),
        catalog.STORAGE_GB["ebs_gp3"],
    )
    return round(size * per_gb * _count_of(resource), 2)


def _s3(resource: Resource) -> float:
    size = _num(resource, "size_gb", catalog.DEFAULT_S3_GB)
    storage = size * catalog.STORAGE_GB["s3_standard"]
    requests = 1_000_000 * 0.0000005  # ~$0.50 per 1M API calls
    return round(storage + requests, 2)


def _efs(resource: Resource) -> float:
    size = _num(resource, "size_gb", catalog.DEFAULT_EFS_GB)
    return round(size * catalog.STORAGE_GB["efs_standard"], 2)


def _lambda_(resource: Resource) -> float:
    invocations = _num(resource, "invocations_per_month", 1_000_000)
    gbs = invocations * 0.1 * 0.5  # 100ms, 512MB average
    cost = gbs * catalog.PER_UNIT["lambda_gbs"] + invocations * catalog.PER_UNIT["lambda_request"]
    return round(cost, 2)


def _alb(resource: Resource) -> float:
    return round(catalog.FLAT_MONTHLY["alb"] + _egress_cost(resource), 2)


def _elb(resource: Resource) -> float:
    return round(catalog.FLAT_MONTHLY["elb"] + _egress_cost(resource), 2)


def _nat(resource: Resource) -> float:
    data = catalog.DEFAULT_EGRESS_GB * catalog.PER_UNIT["nat_gb_processing"]
    return round(catalog.FLAT_MONTHLY["nat_gateway"] + data, 2)


def _eip(resource: Resource) -> float:
    return round(catalog.FLAT_MONTHLY["eip"], 2)


def _eks(resource: Resource) -> float:
    return round(catalog.FLAT_MONTHLY["eks_cluster"], 2)


def _ecs(resource: Resource) -> float:
    # Fargate estimate if task definition style attrs present
    vcpu = _num(resource, "cpu", 0.25)
    ram = _num(resource, "memory", 0.5)
    return round((vcpu * 0.04048 + ram * 0.004445) * MONTHLY_HOURS, 2)


def _ecr(resource: Resource) -> float:
    size = _num(resource, "size_gb", 2.0)
    return round(size * 0.10, 2)


def _elasticache(resource: Resource) -> float:
    node_type = str(resource.attr("node_type", "cache.t3.micro"))
    spec = catalog.get_ec2(node_type.replace("cache.", "")) or catalog.get_ec2("t3.micro")
    return round(spec.monthly * 1.5, 2)


def _dynamodb(resource: Resource) -> float:
    storage = _num(resource, "size_gb", 10.0)
    requests = _num(resource, "requests_per_month", 1_000_000)
    cost = storage * catalog.STORAGE_GB["dynamodb_standard"]
    cost += requests * catalog.PER_UNIT["dynamodb_request"]
    return round(cost, 2)


def _route53(resource: Resource) -> float:
    queries = _num(resource, "queries_per_month", 1_000_000)
    return round(
        catalog.FLAT_MONTHLY["route53_zone"] + queries * catalog.PER_UNIT["route53_query"], 2
    )


def _cloudfront(resource: Resource) -> float:
    transfer = catalog.DEFAULT_EGRESS_GB * catalog.PER_UNIT["cloudfront_data_transfer"]
    return round(transfer, 2)


def _cloudwatch(resource: Resource) -> float:
    if resource.kind == "cloudwatch":
        return round(catalog.FLAT_MONTHLY["cloudwatch_alarm"], 2)
    return 0.0


def _sqs_sns(resource: Resource) -> float:
    requests = _num(resource, "requests_per_month", 1_000_000)
    return round(requests * 0.40e-6, 2)


def _kinesis(resource: Resource) -> float:
    shards = _num(resource, "shard_count", 1)
    return round(shards * 22.0, 2)  # ~$22/shard/month


def _api_gateway(resource: Resource) -> float:
    requests = _num(resource, "requests_per_month", 1_000_000)
    return round(requests * 3.5e-6, 2)


def _backup(resource: Resource) -> float:
    size = _num(resource, "size_gb", 20.0)
    return round(
        catalog.FLAT_MONTHLY["backup_vault"] + size * catalog.STORAGE_GB["ebs_snapshot"], 2
    )


def _kms(resource: Resource) -> float:
    return round(catalog.FLAT_MONTHLY["kms_key"], 2)


def _secrets(resource: Resource) -> float:
    return round(0.40 * _count_of(resource), 2)


def _waf(resource: Resource) -> float:
    return round(catalog.FLAT_MONTHLY["waf"], 2)


def _ssm(resource: Resource) -> float:
    return 0.05  # small advanced param cost


def _free(resource: Resource) -> float:
    return 0.0


# kind -> estimator
_KIND_HANDLERS = {
    "ec2": _ec2,
    "asg": _asg,
    "rds": _rds,
    "ebs": _ebs,
    "s3": _s3,
    "efs": _efs,
    "lambda": _lambda_,
    "alb": _alb,
    "elb": _elb,
    "nat": _nat,
    "eip": _eip,
    "eks": _eks,
    "ecs": _ecs,
    "ecr": _ecr,
    "elasticache": _elasticache,
    "dynamodb": _dynamodb,
    "route53": _route53,
    "cloudfront": _cloudfront,
    "cloudwatch": _cloudwatch,
    "sqs": _sqs_sns,
    "sns": _sqs_sns,
    "kinesis": _kinesis,
    "apigateway": _api_gateway,
    "backup": _backup,
    "kms": _kms,
    "secrets_manager": _secrets,
    "waf": _waf,
    "ssm": _ssm,
}


def estimate_resource_cost(resource: Resource) -> float:
    """Return estimated monthly cost (USD) for a single resource.

    Returns 0.0 for data sources and non-billable resources.
    """
    if resource.is_data:
        return 0.0
    if not resource.billable:
        return 0.0
    handler = _KIND_HANDLERS.get(resource.kind, _free)
    try:
        return round(handler(resource), 2)
    except Exception:
        import logging

        logging.exception("Pricing handler failed for %s", resource.id)
        return 0.0


def estimate_all(resources: list[Resource]) -> dict[str, float]:
    """Return ``{resource_id: monthly_cost}`` for billable resources only.

    Data sources and non-billable resources are excluded from the result.
    """
    return {
        res.id: estimate_resource_cost(res) for res in resources if not res.is_data and res.billable
    }


# ---------------------------------------------------------------------------
# Confidence-aware pricing
# ---------------------------------------------------------------------------

# Confidence levels for each kind based on how well we can estimate from static config
_KIND_CONFIDENCE: dict[str, str] = {
    "ec2": "high",  # instance_type -> catalog lookup is reliable
    "rds": "high",  # instance_class -> catalog lookup
    "ebs": "high",  # size * type per-GB is reliable
    "s3": "medium",  # we assume default size_gb, no real data
    "nat": "high",  # flat + known egress formula
    "alb": "medium",  # flat fee + unknown egress volume
    "elb": "medium",
    "lambda": "low",  # invocations are pure guesses
    "ecs": "medium",  # Fargate vcpu/memory is reliable, but we don't know runtime hours
    "dynamodb": "low",  # capacity mode unknown, provisioned vs on-demand
    "elasticache": "medium",
    "eks": "medium",  # cluster fee is flat, but data transfer is unknown
    "cloudwatch": "high",  # flat alarm cost
    "kms": "high",  # flat key cost
    "waf": "medium",  # flat + rule-based scaling unknown
    "route53": "low",  # query volume is a guess
    "cloudfront": "low",  # data transfer varies wildly
    "sqs": "low",
    "sns": "low",
    "kinesis": "medium",
    "apigateway": "low",
    "backup": "medium",
    "secrets_manager": "high",
    "ssm": "high",
    "ecr": "medium",
    "efs": "medium",
    "eip": "high",  # flat fee per month
    "vpc": "high",  # VPCs are free
}

# Cost classification: how the estimate was derived
# "fixed"         — flat fee from catalog, no usage assumptions needed
# "usage_based"   — depends on runtime volume (invocations, queries, egress)
# "estimated"     — catalog lookup using config values (instance type, size)
# "unknown"       — significant assumptions required, no config data available
_COST_CLASSIFICATION: dict[str, str] = {
    "ec2": "estimated",
    "rds": "estimated",
    "ebs": "estimated",
    "s3": "estimated",
    "nat": "fixed",
    "alb": "estimated",
    "elb": "estimated",
    "lambda": "usage_based",
    "ecs": "estimated",
    "dynamodb": "usage_based",
    "elasticache": "estimated",
    "eks": "fixed",
    "cloudwatch": "fixed",
    "kms": "fixed",
    "waf": "fixed",
    "route53": "usage_based",
    "cloudfront": "usage_based",
    "sqs": "usage_based",
    "sns": "usage_based",
    "kinesis": "estimated",
    "apigateway": "usage_based",
    "backup": "estimated",
    "secrets_manager": "fixed",
    "ssm": "fixed",
    "ecr": "estimated",
    "efs": "estimated",
    "eip": "fixed",
    "vpc": "fixed",
}

_CONFIDENCE_NOTES: dict[str, str] = {
    "ec2": "Based on instance_type catalog pricing; actual cost varies by region and usage.",
    "rds": "Based on instance_class catalog pricing; excludes IOPS and backup storage.",
    "ebs": "Based on volume size and type; excludes IOPS and snapshot costs.",
    "s3": "Assumes default 100 GB storage and 1M requests; actual depends on access patterns.",
    "nat": "Based on flat gateway fee + default 100 GB egress; actual depends on traffic.",
    "alb": "Based on flat ALB fee; data processing charges depend on actual traffic volume.",
    "lambda": "Assumes 1M invocations at 100ms/512MB; actual depends on workload.",
    "ecs": "Fargate pricing based on CPU/memory; excludes data transfer and logging.",
    "dynamodb": "Assumes 10 GB storage and 1M requests; provisioned vs on-demand unknown.",
    "elasticache": "Based on node type; assumes 1.5x EC2 equivalent.",
    "eks": "Cluster fee only; Fargate/node costs depend on workload.",
    "route53": "Assumes 1M queries/month; actual depends on DNS traffic.",
    "cloudfront": "Assumes default egress volume; actual depends on distribution.",
    "waf": "Based on WAFv2 standard pricing; rule count unknown.",
    "backup": "Assumes 20 GB vault + snapshots; actual depends on backup policy.",
    "eip": "Flat monthly fee when attached; free when unattached.",
    "vpc": "VPCs have no direct AWS charges; data transfer and gateway costs are separate.",
}


def _usage_assumption_cost(resource: Resource) -> float:
    """Return the portion of a resource's cost that comes from assumed usage volumes.

    "Known" costs are deterministic from the Terraform config (instance type, storage size, flat fees).
    "Usage-dependent" costs require assumptions about runtime volumes not present in Terraform
    (data transfer, request counts, invocations, etc.).
    """
    kind = resource.kind
    if kind == "ec2":
        return _egress_cost(resource)
    if kind == "asg":
        return _egress_cost(resource)
    if kind in ("alb", "elb"):
        return _egress_cost(resource)
    if kind == "nat":
        return catalog.DEFAULT_EGRESS_GB * catalog.PER_UNIT["nat_gb_processing"]
    if kind == "s3":
        return round(1_000_000 * 0.0000005, 2)
    if kind == "dynamodb":
        return round(estimate_resource_cost(resource), 2)
    if kind in ("sns", "sqs"):
        return round(estimate_resource_cost(resource), 2)
    if kind == "lambda":
        return round(estimate_resource_cost(resource), 2)
    if kind == "route53":
        return round(
            _num(resource, "queries_per_month", 1_000_000) * catalog.PER_UNIT["route53_query"], 2
        )
    if kind == "cloudfront":
        return round(estimate_resource_cost(resource), 2)
    if kind == "apigateway":
        return round(estimate_resource_cost(resource), 2)
    return 0.0


def estimate_all_detailed(resources: list[Resource]) -> list[dict]:
    """Return detailed cost estimates with confidence levels, classification, and assumptions.

    Each entry contains: resource_id, kind, name, monthly_cost, known_cost,
    usage_cost, confidence, cost_classification, and assumptions.
    """
    results: list[dict] = []
    for res in resources:
        if res.is_data or not res.billable:
            continue
        cost = estimate_resource_cost(res)
        usage = _usage_assumption_cost(res)
        known = max(0.0, round(cost - usage, 2))
        usage = round(usage, 2)
        confidence = _KIND_CONFIDENCE.get(res.kind, "unknown")
        classification = _COST_CLASSIFICATION.get(res.kind, "unknown")
        assumptions = _CONFIDENCE_NOTES.get(res.kind, "No assumptions documented.")
        if cost == 0.0 and confidence == "unknown":
            classification = "unknown"
        results.append(
            {
                "resource_id": res.id,
                "kind": res.kind,
                "name": res.name,
                "monthly_cost": round(cost, 2),
                "known_cost": known,
                "usage_cost": usage,
                "confidence": confidence,
                "cost_classification": classification,
                "assumptions": assumptions,
            }
        )
    return results
