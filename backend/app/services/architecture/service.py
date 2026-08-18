"""Architecture diagram generator.

Produces a node/edge graph with network-boundary grouping so the frontend can
render an interactive, zoomable architecture diagram. Nodes carry a stable id,
a label, a Lucide icon hint, a status, their region and a layer classification.
Groups represent VPCs, subnets, and logical service clusters.
"""

from __future__ import annotations

import re

from app.services.terraform.parser import Resource, TerraformConfig

# icon hints align with registry.resource_icon
GROUP_COLORS = {
    "network": "#3b82f6",
    "storage": "#22c55e",
    "database": "#a855f7",
    "compute": "#f59e0b",
    "messaging": "#14b8a6",
    "dns": "#f43f5e",
    "security": "#8b5cf6",
    "observability": "#06b6d4",
    "reliability": "#10b981",
    "data": "#6366f1",
}


_GRAPH_KINDS_TO_SKIP = frozenset({
    "iam", "kms", "route53", "cloudfront", "waf", "acm",
    "security_group", "nacl", "route_table", "route",
    "subnet_group", "parameter_group",
})

# Primary topology kinds — visually prominent
_PRIMARY_KINDS = frozenset({
    "vpc", "subnet", "igw", "nat", "eip",
    "alb", "elb",
    "ec2", "asg", "ecs", "eks", "lambda",
    "rds", "elasticache", "dynamodb", "elasticsearch", "opensearch",
    "s3", "efs",
})

# Supporting infrastructure kinds — lighter visual treatment
_SUPPORTING_KINDS = frozenset({
    "ecr", "cloudwatch", "events", "step_functions",
    "sqs", "sns", "kinesis",
    "apigateway", "launch_template",
    "target_group", "listener",
})

_SANITIZE_RE = re.compile(r"[^\w\s\-./()]")


def _sanitize_label(label: str) -> str:
    """Remove characters that could corrupt SVG or React rendering."""
    return _SANITIZE_RE.sub("", label).strip() or "unknown"


def build_graph(config: TerraformConfig) -> dict:
    """Return the architecture graph payload (nodes, edges, groups).

    Filters out data sources and non-infrastructure configuration resources
    (IAM, security groups, route tables) that clutter the diagram without
    adding architectural value. Edges referencing skipped resources are
    still preserved so connectivity is visible.
    """
    nodes: list[dict] = []
    groups: dict[str, dict] = {}
    node_ids: set[str] = set()

    # Map resources to logical groups
    group_of: dict[str, str] = _assign_groups(config)

    for res in config.resources:
        # Skip data sources — they represent lookups, not real infrastructure
        if res.is_data:
            continue
        # Skip pure-configuration resources that don't represent deployable infra
        if res.kind in _GRAPH_KINDS_TO_SKIP:
            continue
        # Deduplicate by resource ID (parser can create duplicates)
        if res.id in node_ids:
            continue

        group_key = _sanitize_label(group_of.get(res.id, "Global"))
        groups.setdefault(
            group_key,
            {
                "id": group_key,
                "label": group_key,
                "color": GROUP_COLORS.get(res.service, "#64748b"),
                "kind": "network"
                if res.kind in ("vpc", "subnet", "igw", "nat")
                else res.service,
            },
        )

        layer = "primary" if res.kind in _PRIMARY_KINDS else (
            "supporting" if res.kind in _SUPPORTING_KINDS else "implementation"
        )

        cost = res.attributes.get("_monthly_cost", 0.0)
        cost_class = res.attributes.get("_cost_classification", "unknown")
        cost_conf = res.attributes.get("_cost_confidence", "unknown")
        resource_address = f"{res.resource_type}.{res.name}"

        node = {
            "id": res.id,
            "label": _sanitize_label(res.name),
            "displayName": _display_name(res),
            "name": res.name,
            "type": res.resource_type,
            "resourceAddress": resource_address,
            "category": res.service,
            "kind": res.kind,
            "service": res.service,
            "group": group_key,
            "region": res.region,
            "status": "ok",
            "is_data": False,
            "layer": layer,
            "metrics": {
                "monthly_cost": cost,
                "cost_classification": cost_class,
                "cost_confidence": cost_conf,
            },
            "icon": _icon_for(res),
        }
        nodes.append(node)
        node_ids.add(res.id)

    edges = config.graph_edges()
    edges = _infer_edges(config, edges)

    # Add relationship type to edges
    for edge in edges:
        if "relationship" not in edge:
            edge["relationship"] = "dependency"

    # Filter edges to only include those between visible nodes
    edges = [e for e in edges if e["source"] in node_ids and e["target"] in node_ids]

    topology_count = len(nodes)

    return {
        "nodes": nodes,
        "edges": edges,
        "groups": list(groups.values()),
        "topology_count": topology_count,
    }


def _icon_for(res: Resource) -> str:
    from app.services.terraform.registry import resource_icon

    return resource_icon(res.kind)


def _display_name(res: Resource) -> str:
    """Return human-readable display name from registry."""
    from app.services.terraform.registry import classify
    kind_info = classify(res.resource_type)
    return kind_info.label


def _assign_groups(config: TerraformConfig) -> dict[str, str]:
    """Map each resource to a group label describing its network boundary."""
    group_of: dict[str, str] = {}

    # VPCs
    vpc_by_name: dict[str, str] = {}
    for res in config.resources:
        if res.kind == "vpc":
            label = res.name if res.name != "main" else f"VPC ({res.name})"
            group_of[res.id] = label
            vpc_by_name[res.type_name] = label

    # Subnets -> attach to their VPC, mark public/private
    subnet_group: dict[str, str] = {}
    for res in config.resources:
        if res.kind == "subnet":
            vpc_refs = [r for r in res.references if r in vpc_by_name]
            vpc_label = (
                vpc_by_name.get(vpc_refs[0], "VPC (default)") if vpc_refs else "VPC (default)"
            )
            label = f"{vpc_label} / {res.name}"
            group_of[res.id] = label
            subnet_group[res.type_name] = label

    # Detect public subnets via route table -> igw references
    for res in config.resources:
        if res.kind == "route_table":
            refs = [r for r in res.references if r.startswith("aws_internet_gateway.")]
            if refs:
                # find subnets referencing this route table
                for res2 in config.resources:
                    if res2.kind == "subnet" and res.type_name in res2.references:
                        group_of[res2.id] = group_of.get(res2.id, "") + " (public)"

    # Everything else
    for res in config.resources:
        if res.id in group_of:
            continue
        if res.kind in ("iam", "kms", "route53", "cloudfront", "waf", "acm"):
            group_of[res.id] = "Global / Edge"
        else:
            # Attach to a subnet if referenced
            subnet_ref = next(
                (r for r in res.references if r in subnet_group and r.startswith("aws_subnet.")),
                None,
            )
            if subnet_ref:
                group_of[res.id] = subnet_group[subnet_ref]
            else:
                group_of[res.id] = res.label
    return group_of


def _infer_edges(config: TerraformConfig, edges: list[dict]) -> list[dict]:
    """Add structural edges not captured by interpolation references."""
    seen = {(e["source"], e["target"]) for e in edges}
    by_type_name = {r.type_name: r for r in config.resources}

    def add(source_id: str, target_id: str):
        if source_id == target_id:
            return
        if (source_id, target_id) not in seen and (target_id, source_id) not in seen:
            edges.append({"source": source_id, "target": target_id})
            seen.add((source_id, target_id))

    for res in config.resources:
        # Instance -> subnet
        if res.kind in ("ec2", "rds", "elasticache", "alb") and res.references:
            for ref in res.references:
                if ref.startswith("aws_subnet.") and ref in by_type_name:
                    add(res.id, by_type_name[ref].id)
        # SG -> resource (resource references SG)
        if res.kind == "security_group":
            for other in config.resources:
                if other.id != res.id and res.type_name in other.references:
                    add(other.id, res.id)
        # ALB -> EC2 (target group attachment)
        if res.kind == "target_group":
            for ref in res.references:
                if ref in by_type_name and by_type_name[ref].kind in ("ec2", "asg"):
                    add(res.id, by_type_name[ref].id)
    return edges
