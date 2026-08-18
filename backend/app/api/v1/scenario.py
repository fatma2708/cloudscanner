"""Scenario calculator endpoint.

Allows users to input explicit usage assumptions and see estimated total cost.
Without explicit inputs, the scenario is unavailable — we never silently
choose arbitrary defaults.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body

from app.services.pricing.catalog import PER_UNIT

router = APIRouter()


@router.post("")
def scenario_estimate(
    files: Annotated[dict[str, str], Body(description="path -> HCL content")],
    assumptions: dict = Body(
        default={},
        description="Optional usage assumptions: requests_per_month, data_transfer_gb, etc.",
    ),
) -> dict:
    """Estimate total cost with explicit user-provided usage assumptions.

    Without assumptions, returns usage_available=false and total=null.
    With assumptions, returns a breakdown showing known + estimated usage costs.
    """
    from app.services.terraform.parser import parse_terraform_files
    from app.services.pricing.engine import estimate_resource_cost, _usage_assumption_cost

    config = parse_terraform_files(files=files, default_region="us-east-1")

    # Known baseline: deterministic from Terraform config
    known_total = 0.0
    usage_resources = []
    for res in config.resources:
        if res.is_data or not res.billable:
            continue
        cost = estimate_resource_cost(res)
        usage = _usage_assumption_cost(res)
        known = max(0.0, round(cost - usage, 2))
        known_total += known
        if usage > 0:
            usage_resources.append({
                "resource_id": res.id,
                "kind": res.kind,
                "name": res.name,
                "known_cost": round(known, 2),
                "usage_cost_default": round(usage, 2),
            })

    if not assumptions:
        return {
            "usage_available": False,
            "assumptions": {},
            "known_baseline": round(known_total, 2),
            "usage_estimate": None,
            "total_estimate": None,
            "usage_resources": usage_resources,
            "message": "No usage assumptions provided. Add requests_per_month, data_transfer_gb, etc. to see a total estimate.",
        }

    # With explicit assumptions, compute usage-dependent costs
    usage_total = 0.0
    assumption_details = []

    req_per_month = assumptions.get("requests_per_month", 0)
    data_transfer_gb = assumptions.get("data_transfer_gb", 0)
    lambda_invocations = assumptions.get("lambda_invocations", 0)

    # Data transfer egress cost
    if data_transfer_gb > 0:
        egress_cost = data_transfer_gb * PER_UNIT["data_transfer_egress"]
        usage_total += egress_cost
        assumption_details.append(f"{data_transfer_gb:,} GB data transfer: ${egress_cost:.2f}/mo")

    # NAT data processing
    nat_count = sum(1 for r in config.resources if r.kind == "nat" and not r.is_data)
    if nat_count > 0 and data_transfer_gb > 0:
        nat_cost = nat_count * data_transfer_gb * PER_UNIT["nat_gb_processing"]
        usage_total += nat_cost
        assumption_details.append(f"NAT processing ({nat_count} gateways × {data_transfer_gb} GB): ${nat_cost:.2f}/mo")

    # S3 requests
    if req_per_month > 0:
        s3_cost = req_per_month * 0.0000005
        usage_total += s3_cost
        assumption_details.append(f"{req_per_month:,} S3 API requests: ${s3_cost:.2f}/mo")

    # Route53 queries
    r53_count = sum(1 for r in config.resources if r.kind == "route53" and not r.is_data)
    if r53_count > 0 and req_per_month > 0:
        r53_cost = r53_count * req_per_month * PER_UNIT["route53_query"]
        usage_total += r53_cost
        assumption_details.append(f"Route53 queries ({r53_count} zones × {req_per_month:,}): ${r53_cost:.2f}/mo")

    # API Gateway
    apigw_count = sum(1 for r in config.resources if r.kind == "apigateway" and not r.is_data)
    if apigw_count > 0 and req_per_month > 0:
        apigw_cost = apigw_count * req_per_month * 3.5e-6
        usage_total += apigw_cost
        assumption_details.append(f"API Gateway ({apigw_count} APIs × {req_per_month:,} requests): ${apigw_cost:.2f}/mo")

    # Lambda invocations
    if lambda_invocations > 0:
        lambda_cost = lambda_invocations * 0.0000002 + lambda_invocations * 0.1 * 0.5 * PER_UNIT["lambda_gbs"]
        usage_total += lambda_cost
        assumption_details.append(f"{lambda_invocations:,} Lambda invocations: ${lambda_cost:.2f}/mo")

    # SQS/SNS
    sqs_sns_count = sum(1 for r in config.resources if r.kind in ("sqs", "sns") and not r.is_data)
    if sqs_sns_count > 0 and req_per_month > 0:
        messaging_cost = sqs_sns_count * req_per_month * 0.40e-6
        usage_total += messaging_cost
        assumption_details.append(f"SQS/SNS ({sqs_sns_count} resources × {req_per_month:,}): ${messaging_cost:.2f}/mo")

    total = known_total + usage_total

    return {
        "usage_available": True,
        "assumptions": assumptions,
        "assumption_details": assumption_details,
        "known_baseline": round(known_total, 2),
        "usage_estimate": round(usage_total, 2),
        "total_estimate": round(total, 2),
        "usage_resources": usage_resources,
        "message": None,
    }
