"""Infrastructure review rules.

Each rule inspects the parsed configuration and returns zero or more
:class:`Recommendation` objects. Rules are pure and deterministic — the same
input always produces the same review — which keeps CloudPilot predictable and
testable. The LLM layer can later enrich these into prose.
"""

from __future__ import annotations

from collections.abc import Callable

from app.services.pricing.catalog import FLAT_MONTHLY, get_ec2
from app.services.recommendations.models import (
    Recommendation,
    savings_floor,
)
from app.services.terraform.parser import Resource, TerraformConfig

RuleFn = Callable[[TerraformConfig], list[Recommendation]]


def _ec2_attr(resource: Resource, key: str, default=None):
    return resource.attributes.get(key, default)


def _cidr_blocks(rule_attrs) -> list[str]:
    blocks: list[str] = []
    if not isinstance(rule_attrs, list):
        return blocks
    for entry in rule_attrs:
        if not isinstance(entry, dict):
            continue
        cidr = entry.get("cidr_blocks") or entry.get("ipv6_cidr_blocks") or []
        if isinstance(cidr, str):
            blocks.append(cidr)
        elif isinstance(cidr, list):
            blocks.extend(x for x in cidr if isinstance(x, str))
    return blocks


def _sg_open_ports(resource: Resource) -> list[tuple[str, str, dict]]:
    """Return [(kind, port_desc, rule)] of ingress rules exposing dangerous ports to 0.0.0.0/0.

    Detects:
    - SSH/RDP (22/3389)
    - Database ports (5432/3306/1433)
    - Datastore ports (6379/27017)
    - All-ports (protocol=-1, or from_port=0/to_port=65535)

    The returned ``rule`` is the offending ingress dict so callers can build a
    scoped remediation (restrict the same port/protocol, not unrelated resources).
    """
    dangerous: list[tuple[str, str, dict]] = []
    for rule in resource.attributes.get("ingress", []) or []:
        if not isinstance(rule, dict):
            continue
        cidr = rule.get("cidr_blocks") or rule.get("ipv6_cidr_blocks") or []
        if isinstance(cidr, str):
            cidr = [cidr]
        if not any(c in ("0.0.0.0/0", "::/0") for c in cidr):
            continue

        from_port = rule.get("from_port")
        to_port = rule.get("to_port")
        protocol = str(rule.get("protocol", "")).lower()

        # Normalize port range
        try:
            fp = int(from_port) if from_port is not None else None
        except (TypeError, ValueError):
            fp = None
        try:
            tp = int(to_port) if to_port is not None else None
        except (TypeError, ValueError):
            tp = None

        # Protocol -1 or "all" = all traffic
        if protocol in ("-1", "all"):
            dangerous.append(("all-ports", "*", rule))
            continue

        # Full port range (0-65535) or equivalent
        if fp == 0 and tp == 65535:
            dangerous.append(("all-ports", "0-65535", rule))
            continue
        if fp is None and tp is None:
            dangerous.append(("all-ports", "*", rule))
            continue

        # Individual dangerous ports
        if protocol in ("tcp", "tcp udp", ""):
            if fp in (22, 3389) or tp in (22, 3389):
                dangerous.append(("ssh/rdp", str(fp or tp), rule))
            elif fp in (5432, 3306, 1433) or tp in (5432, 3306, 1433):
                dangerous.append(("database", str(fp or tp), rule))
            elif fp in (6379, 27017) or tp in (6379, 27017):
                dangerous.append(("datastore", str(fp or tp), rule))
            # Also catch ranges that include dangerous ports
            elif fp is not None and tp is not None and fp <= 22 <= tp:
                dangerous.append(("ssh/rdp", f"{fp}-{tp}", rule))
            elif fp is not None and tp is not None and fp <= 5432 <= tp:
                dangerous.append(("database", f"{fp}-{tp}", rule))
            elif fp is not None and tp is not None and fp <= 6379 <= tp:
                dangerous.append(("datastore", f"{fp}-{tp}", rule))

    return dangerous


def _has_health_check(config: TerraformConfig) -> bool:
    """Check if any target group has an explicit health_check block."""
    for res in config.resources:
        if res.kind == "target_group" and not res.is_data:
            hc = res.attributes.get("health_check")
            if isinstance(hc, list) and hc:
                return True
            # health_check can also be a dict (non-list form)
            if isinstance(hc, dict):
                return True
    return False


def _instances(config: TerraformConfig) -> list[Resource]:
    """Return only actual aws_instance resources (not ECS, not data sources)."""
    return [
        r
        for r in config.resources
        if r.kind == "ec2" and r.resource_type == "aws_instance" and not r.is_data
    ]


def _nat_count(config: TerraformConfig) -> int:
    return len([r for r in config.resources if r.kind == "nat"])


def _sg_count(config: TerraformConfig) -> int:
    return len([r for r in config.resources if r.kind == "security_group"])


# --------------------------------------------------------------------------- rules


def rule_nat_gateway(config: TerraformConfig) -> list[Recommendation]:
    nats = [r for r in config.resources if r.kind == "nat"]
    if not nats:
        return []
    recs: list[Recommendation] = []
    # Multi-AZ NAT sprawl
    if len(nats) >= 2:
        savings = (len(nats) - 1) * (FLAT_MONTHLY["nat_gateway"] + 4.5)
        recs.append(
            Recommendation(
                key="nat-consolidation",
                title="Consolidate NAT Gateways into a shared instance",
                description=(
                    f"You have {len(nats)} NAT gateways, one per AZ. For workloads that do not "
                    "need zone-independent egress, a single shared NAT gateway (or a lightweight "
                    "bastion) is usually enough — NAT gateways cost $32.22/mo each plus "
                    "$0.045/GB processed."
                ),
                severity="high",
                category="cost",
                target=[r.id for r in nats],
                savings_monthly=savings_floor(savings),
                risk="medium",
                difficulty="medium",
                confidence="high",
                improvement=f"Save ${savings:,.0f}/mo (~{(savings * 12):,.0f}/yr) and simplify routing.",
                why="NAT gateways are billed per-hour regardless of use and cannot be shared across "
                "VPCs. Multiple gateways multiply fixed cost.",
                impact="One gateway becomes a single point of failure for egress; mitigate with "
                "an ASG-backed NAT instance or accept AZ-pinning.",
                cost_saved=f"${savings:,.0f}/mo",
                performance_impact="Slight added latency for cross-AZ egress (sub-millisecond).",
                reliability_impact="Reduced AZ redundancy unless a HA NAT instance is used.",
                security_impact="Fewer managed endpoints = smaller attack surface.",
                evidence=[
                    f"Found {len(nats)} NAT gateways; each costs ~$32.22/mo + $0.045/GB",
                    f"Consolidating to 1 saves ~${savings:,.0f}/mo",
                    "Confidence=high because NAT pricing is flat and well-documented",
                ],
                implementation=[
                    "Create a single shared NAT gateway in one AZ (or deploy a NAT instance with keepalived).",
                    "Update private route tables to point at the shared gateway.",
                    "Remove per-AZ gateways and their Elastic IPs.",
                    "Validate outbound connectivity from all private subnets.",
                ],
                modes={"lowest-cost", "startup-budget", "balanced"},
                generated_code={
                    "aws_nat_gateway": {
                        "name": "nat_shared",
                        "config": {
                            "subnet_id": "${aws_subnet.public_a.id}",
                            "allocation_id": "${aws_eip.nat.id}",
                        },
                    }
                },
            )
        )
    # NAT cost optimization opportunity — low confidence when workload size is unknown
    if len(nats) == 1:
        instances = _instances(config)
        has_ecs = any(r.kind == "ecs" and not r.is_data for r in config.resources)
        has_alb = any(r.kind in ("alb", "elb") and not r.is_data for r in config.resources)

        # Only claim "small workload" with high confidence if only standalone EC2 with no ALB/ECS
        if len(instances) <= 1 and not has_ecs and not has_alb:
            confidence = "high"
            title = "Replace NAT Gateway with a managed alternative for a small workload"
            description = (
                "A single NAT gateway costing $36+/mo appears to serve a small "
                "workload. Consider VPC endpoints for the services you use, or a "
                "NAT instance on a small spot VM."
            )
            savings = savings_floor(FLAT_MONTHLY["nat_gateway"] - 4.0)
        else:
            confidence = "low"
            title = "NAT Gateway cost optimization opportunity"
            description = (
                "A single NAT gateway costs $36+/mo plus $0.045/GB processed. "
                "Depending on workload size and traffic patterns, VPC endpoints "
                "or a managed NAT alternative may reduce cost."
            )
            savings = 0.0

        recs.append(
            Recommendation(
                key="nat-small-workload",
                title=title,
                description=description,
                severity="medium",
                category="cost",
                target=[nats[0].id],
                savings_monthly=savings,
                risk="medium",
                difficulty="medium",
                confidence=confidence,
                improvement="Potential to reduce NAT-related costs.",
                why="NAT gateways are a fixed cost that may exceed the value they add "
                "for smaller or endpoint-friendly workloads.",
                impact="Small risk if endpoints are not covered by private connectivity.",
                cost_saved="Not quantified" if savings == 0 else f"~${savings:,.0f}/mo",
                performance_impact="Negligible; VPC endpoints can actually reduce latency.",
                reliability_impact="VPC endpoints are highly available and redundant.",
                security_impact="Private traffic stays inside the VPC — improved.",
                evidence=[
                    "Found 1 NAT gateway at ~$36.72/mo + $0.045/GB processed",
                    "Workload size could not be fully determined from Terraform configuration alone",
                    "Confidence=low because additional workload/traffic information is required",
                ],
                implementation=[
                    "List AWS services your workload calls.",
                    "Create Interface/Gateway VPC endpoints for those services.",
                    "Attach endpoint policies scoped to your resources.",
                    "Remove the NAT gateway and Elastic IP after verification.",
                ],
                modes={"lowest-cost", "startup-budget", "lowest-carbon"},
            )
        )
    return recs


def rule_ec2_oversized(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for res in _instances(config):
        itype = str(_ec2_attr(res, "instance_type", ""))
        spec = get_ec2(itype)
        if spec and (spec.vcpu >= 16 or spec.ram_gb >= 64) and not res.attributes.get("spot_price"):
            recs.append(
                Recommendation(
                    key="ec2-rightsize",
                    title=f"Right-size EC2 instance {res.name}",
                    description=(
                        f"{res.name} runs a {itype} ({spec.vcpu} vCPU / {spec.ram_gb} GB RAM) "
                        "as on-demand. Unless your metrics show sustained >70% utilization, "
                        "a 2-4 vCPU instance is usually sufficient — the average EC2 fleet "
                        "utilization is below 15%."
                    ),
                    severity="high",
                    category="cost",
                    target=[res.id],
                    savings_monthly=savings_floor(spec.monthly * 0.4),
                    risk="medium",
                    difficulty="medium",
                    confidence="medium",
                    improvement="Cut monthly compute spend ~40% while keeping headroom.",
                    why="Large on-demand instances are the #1 source of cloud waste because they "
                    "are sized for peak load that rarely occurs.",
                    impact="Reduced capacity headroom; monitor CPU/RAM before and after.",
                    cost_saved=f"~${spec.monthly * 0.4:,.0f}/mo",
                    performance_impact="Lower peak throughput; fine for web/API workloads.",
                    reliability_impact="None, if utilization monitoring confirms headroom.",
                    security_impact="None.",
                    evidence=[
                        f"Instance type {itype} has {spec.vcpu} vCPU / {spec.ram_gb} GB RAM",
                        f"Monthly cost ~${spec.monthly:,.0f}; right-sizing could save ~${spec.monthly * 0.4:,.0f}/mo",
                        "Confidence=medium because actual utilization requires runtime metrics",
                    ],
                    implementation=[
                        "Enable detailed monitoring and collect 2 weeks of CPU/RAM metrics.",
                        "Pick a Graviton or next-gen family with similar vCPU/RAM.",
                        "Deploy the new size to staging, run load tests.",
                        "Roll out to production via an ASG to avoid downtime.",
                    ],
                    modes={"lowest-cost", "startup-budget", "balanced", "lowest-carbon"},
                )
            )
    return recs


def rule_spot_instances(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for res in _instances(config):
        itype = str(_ec2_attr(res, "instance_type", ""))
        spec = get_ec2(itype)
        if (
            not spec
            or res.attributes.get("spot_price")
            or res.attributes.get("capacity_type") == "SPOT"
        ):
            continue
        stateful = (
            any(key in res.attributes for key in ("ebs_block_device", "root_block_device"))
            or res.attributes.get("iam_instance_profile") is None
        )
        if stateful and res.attributes.get("root_block_device") is None:
            continue
        savings = spec.monthly * 0.7
        recs.append(
            Recommendation(
                key="spot-instances",
                title=f"Use Spot Instances for {res.name}",
                description=(
                    f"{res.name} runs on-demand {itype}. Spot instances can run the same "
                    "workload for ~70% less and are interrupted rarely for fault-tolerant, "
                    "horizontal workloads."
                ),
                severity="medium",
                category="cost",
                target=[res.id],
                savings_monthly=savings_floor(savings),
                risk="medium",
                difficulty="easy",
                confidence="medium",
                improvement=f"Reduce compute cost for {res.name} by up to 70%.",
                why="Spot pricing is driven by spare capacity auctions; interruptible workloads "
                "should never pay on-demand rates.",
                impact="Instances can be reclaimed with 2-minute warning — design for that.",
                cost_saved=f"~${savings:,.0f}/mo",
                performance_impact="Identical instance performance.",
                reliability_impact="Possible interruptions; mitigated by an ASG with mixed "
                "on-demand/spot strategy.",
                security_impact="None.",
                evidence=[
                    f"Instance {res.name} runs on-demand {itype} at ~${spec.monthly:,.0f}/mo",
                    f"Spot discount typically 60-70%; potential savings ~${savings:,.0f}/mo",
                    "Confidence=medium because spot availability varies by instance type and region",
                ],
                implementation=[
                    "Wrap the instance in an Auto Scaling Group with a mixed-instances policy.",
                    "Set a diversified instance type list (t3, m5, t4g...).",
                    "Make the workload stateless or persist state to EFS/S3.",
                    "Use capacity-rebalance signals to drain before interruption.",
                ],
                modes={"lowest-cost", "startup-budget", "balanced", "lowest-carbon"},
                generated_code={
                    "aws_autoscaling_group": {
                        "name": f"asg_{res.name}",
                        "config": {
                            "mixed_instances_policy": {
                                "instances_distribution": {
                                    "on_demand_percentage_above_base_capacity": 20,
                                    "spot_allocation_strategy": "capacity-optimized",
                                }
                            }
                        },
                    }
                },
            )
        )
    return recs


def rule_rds_backups(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for res in config.resources:
        if res.kind != "rds" or res.is_data:
            continue
        retention = res.attributes.get("backup_retention_period")
        has_backup = retention not in (None, "", 0, "0")
        if not has_backup:
            recs.append(
                Recommendation(
                    key="rds-no-backup",
                    title=f"RDS {res.name} has no automated backups",
                    description=(
                        f"{res.name} does not configure ``backup_retention_period``. Without "
                        "automated backups a single failed DDL or accidental DELETE is "
                        "permanently unrecoverable."
                    ),
                    severity="critical",
                    category="disaster-recovery",
                    target=[res.id],
                    savings_monthly=0.0,
                    risk="low",
                    difficulty="easy",
                    confidence="high",
                    improvement="Recover any point-in-time within a 7–35 day window.",
                    why="RDS snapshots are the default recovery mechanism; disabling them removes "
                    "your only point-in-time safety net.",
                    impact="No cost, no performance impact — backups run in the background.",
                    cost_saved="Not applicable (required baseline).",
                    performance_impact="Negligible; automated backups use the RDS storage layer.",
                    reliability_impact="Critical — enables point-in-time recovery.",
                    security_impact="Backups are encrypted with the DB key by default.",
                    evidence=[
                        f"backup_retention_period is {retention!r} (not set or 0) on {res.name}",
                        "AWS default is 0 (no backups) unless explicitly configured",
                    ],
                    implementation=[
                        "Set ``backup_retention_period = 7`` (or higher for prod).",
                        "Set ``backup_window`` to off-peak hours.",
                        "Enable ``delete_automated_backups = false``.",
                        "Test a restore drill in a staging account.",
                    ],
                    modes={"balanced", "enterprise", "max-availability", "startup-budget"},
                    generated_code={
                        "aws_db_instance": {
                            "name": res.name,
                            "config": {
                                "backup_retention_period": 7,
                                "backup_window": "03:00-04:00",
                            },
                        }
                    },
                )
            )
        elif isinstance(retention, str) and retention.isdigit() and int(retention) < 7:
            recs.append(
                Recommendation(
                    key="rds-short-backup",
                    title=f"Extend RDS {res.name} backup retention",
                    description=(
                        f"``backup_retention_period`` is {retention} days. For production "
                        "databases keep at least 7 days and enable point-in-time recovery."
                    ),
                    severity="medium",
                    category="disaster-recovery",
                    target=[res.id],
                    savings_monthly=0.0,
                    risk="low",
                    difficulty="easy",
                    improvement="Wider recovery window and PITR coverage.",
                    why="Short retention means you cannot recover from issues discovered days later.",
                    impact="None, small storage cost for extra snapshots.",
                    cost_saved="Not applicable.",
                    performance_impact="None.",
                    reliability_impact="Improved recovery horizon.",
                    security_impact="None.",
                    implementation=[
                        "Set ``backup_retention_period = 14`` for production.",
                        "Enable ``performance_insights`` if needed.",
                    ],
                    modes={"enterprise", "max-availability", "balanced"},
                )
            )
        multi_az = res.attributes.get("multi_az")
        if multi_az in (None, "", False, "false"):
            recs.append(
                Recommendation(
                    key="rds-single-az",
                    title=f"RDS {res.name} is configured for a single AZ",
                    description=(
                        f"{res.name} is configured for a single Availability Zone (multi_az is not "
                        "set to true). An AZ outage would take the database — and your "
                        "application — offline."
                    ),
                    severity="high",
                    category="reliability",
                    target=[res.id],
                    savings_monthly=0.0,
                    risk="low",
                    difficulty="easy",
                    improvement="Survive an AZ failure with automatic failover.",
                    why="Multi-AZ gives you synchronous replication to a standby in another AZ.",
                    impact="Compute cost roughly doubles for the standby.",
                    cost_saved="None (cost increase ~1x compute).",
                    performance_impact="Sub-10ms added write latency on synchronous commit.",
                    reliability_impact="Strong — automatic failover in ~60 seconds.",
                    security_impact="None.",
                    implementation=[
                        "Set ``multi_az = true``.",
                        "Ensure your connection string uses the writer endpoint.",
                        "Test failover with a maintenance window drill.",
                    ],
                    modes={"enterprise", "max-availability", "balanced"},
                    generated_code={
                        "aws_db_instance": {"name": res.name, "config": {"multi_az": True}}
                    },
                )
            )
    return recs


def rule_sg_open_world(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for res in config.resources:
        if res.kind != "security_group":
            continue
        open_ports = _sg_open_ports(res)
        if not open_ports:
            continue
        for kind, _port, rule in open_ports:
            desc = {
                "ssh/rdp": "SSH/RDP (22/3389)",
                "database": "a database port (5432/3306/1433)",
                "datastore": "a datastore port (6379/27017)",
                "all-ports": "ALL ports",
            }[kind]

            # Build a scoped remediation: restrict the SAME rule that exposes
            # the dangerous port to 0.0.0.0/0. The generated block narrows the
            # ingress CIDR to a private bastion range instead of the world.
            port_desc = rule.get("from_port", rule.get("to_port", 0))
            to_port = rule.get("to_port", rule.get("from_port", port_desc))
            protocol = rule.get("protocol") or "tcp"
            if str(protocol).lower() in ("-1", "all"):
                protocol = -1
            use_ipv6 = bool(rule.get("ipv6_cidr_blocks"))
            restricted_cidr = "fd00::/8" if use_ipv6 else "10.0.0.0/8"
            cidr_key = "ipv6_cidr_blocks" if use_ipv6 else "cidr_blocks"
            generated_code = {
                "aws_security_group_rule": {
                    "name": f"{res.name}_restrict_{kind.replace('/', '_')}",
                    "config": {
                        "type": "ingress",
                        "security_group_id": f"${{aws_security_group.{res.name}.id}}",
                        "from_port": int(port_desc)
                        if str(port_desc).lstrip("-").isdigit()
                        else port_desc,
                        "to_port": int(to_port) if str(to_port).lstrip("-").isdigit() else to_port,
                        "protocol": protocol,
                        cidr_key: [restricted_cidr],
                    },
                }
            }

            recs.append(
                Recommendation(
                    key="sg-open-world",
                    title=f"Security Group {res.name} exposes {desc} to the internet",
                    description=(
                        f"Security group ``{res.name}`` allows inbound {desc} from "
                        "0.0.0.0/0. This is one of the most common causes of real-world "
                        "breaches (open SSH, Redis, and PostgreSQL endpoints)."
                    ),
                    severity="critical",
                    category="security",
                    target=[res.id],
                    savings_monthly=0.0,
                    risk="low",
                    difficulty="easy",
                    confidence="high",
                    improvement="Remove internet-facing management and data ports.",
                    why="Any port open to 0.0.0.0/0 is reachable by the entire internet and will "
                    "be scanned within minutes of deployment.",
                    impact="None — restrictive ingress only removes access you shouldn't have.",
                    cost_saved="Prevents potentially millions in breach costs.",
                    performance_impact="None.",
                    reliability_impact="None.",
                    security_impact="Massive — closes publicly reachable management/database surface.",
                    evidence=[
                        f"Security group {res.name} has ingress from 0.0.0.0/0 exposing {desc}",
                        "Scanners (Shodan, Censys) detect open SSH/DB ports within minutes",
                    ],
                    implementation=[
                        "Replace 0.0.0.0/0 with your office/VPN CIDRs or a bastion SG.",
                        "Move databases into private subnets with no internet route.",
                        "Enable VPC flow logs and monitor the old SG before removing it.",
                        "Rotate credentials in case of prior exposure.",
                    ],
                    modes={"balanced", "enterprise", "startup-budget", "max-availability"},
                    generated_code=generated_code,
                )
            )
    return recs


def _sg_overlap_rules(resource: Resource) -> list[tuple[str, str]]:
    """Detect duplicate or overlapping ingress rules in a security group.

    Returns pairs of (rule_index, reason) for rules that are redundant.
    """
    overlaps: list[tuple[str, str]] = []
    ingress = resource.attributes.get("ingress", []) or []
    if not isinstance(ingress, list) or len(ingress) < 2:
        return overlaps

    def _normalize(rule: dict) -> tuple:
        fp = rule.get("from_port")
        tp = rule.get("to_port")
        proto = str(rule.get("protocol", "tcp")).lower()
        cidr = rule.get("cidr_blocks") or rule.get("ipv6_cidr_blocks") or []
        if isinstance(cidr, str):
            cidr = [cidr]
        return (
            proto,
            int(fp) if fp is not None else -1,
            int(tp) if tp is not None else -1,
            tuple(sorted(cidr)),
        )

    seen: dict[tuple, int] = {}
    for i, rule in enumerate(ingress):
        if not isinstance(rule, dict):
            continue
        key = _normalize(rule)
        if key in seen:
            overlaps.append((str(i + 1), f"Exact duplicate of rule #{seen[key] + 1}"))
        else:
            seen[key] = i

    return overlaps


def rule_sg_overlaps(config: TerraformConfig) -> list[Recommendation]:
    """Detect duplicate or overlapping ingress rules in security groups."""
    recs: list[Recommendation] = []
    for res in config.resources:
        if res.kind != "security_group" or res.is_data:
            continue
        overlaps = _sg_overlap_rules(res)
        if not overlaps:
            continue
        descriptions = "; ".join(f"rule #{idx}: {reason}" for idx, reason in overlaps[:5])
        recs.append(
            Recommendation(
                key="sg-overlaps",
                title=f"Security Group {res.name} has overlapping ingress rules",
                description=(
                    f"Security group ``{res.name}`` contains {len(overlaps)} duplicate or "
                    f"overlapping ingress rules ({descriptions}). Redundant rules make the "
                    "security posture harder to audit and increase the chance of unintended access."
                ),
                severity="low",
                category="security",
                target=[res.id],
                savings_monthly=0.0,
                risk="low",
                difficulty="easy",
                confidence="high",
                improvement="Consolidate duplicate rules for cleaner audit trails.",
                why="Overlapping rules are a sign of copy-paste drift and complicate compliance reviews.",
                impact="None — removing duplicates does not change effective access.",
                cost_saved="None.",
                performance_impact="None.",
                reliability_impact="None.",
                security_impact="Cleaner SGs are easier to audit and less likely to have stale access.",
                evidence=[
                    f"Security group {res.name} has {len(overlaps)} overlapping/duplicate ingress rules",
                    *[f"Rule #{idx}: {reason}" for idx, reason in overlaps[:5]],
                ],
                implementation=[
                    "Audit each rule's purpose; remove exact duplicates.",
                    "Consolidate overlapping port ranges into a single rule.",
                    "Use Terraform ``lifecycle ignore_changes`` to prevent SG drift.",
                ],
                modes={"balanced", "enterprise"},
            )
        )
    return recs


def rule_alb_health_checks(config: TerraformConfig) -> list[Recommendation]:
    """Check for ALBs with target groups that lack health checks.

    Only triggers when:
    - An ALB exists
    - At least one target_group exists
    - No target_group has an explicit health_check block
    - The target group is not TCP-only (TCP health checks are implicit)
    """
    albs = [r for r in config.resources if r.kind == "alb" and not r.is_data]
    if not albs:
        return []

    target_groups = [r for r in config.resources if r.kind == "target_group" and not r.is_data]
    if not target_groups:
        return []

    # Check if any target group already has a health check configured
    for tg in target_groups:
        hc = tg.attributes.get("health_check")
        if hc:
            return []  # At least one TG has health checks — assume OK

    # Check if target groups use TCP protocol (TCP health checks are implicit/default)
    for tg in target_groups:
        protocol = str(tg.attributes.get("protocol", "HTTP")).upper()
        if protocol == "TCP":
            return []  # TCP target groups don't need explicit health checks

    targets = [r.id for r in albs + target_groups]
    return [
        Recommendation(
            key="alb-health-checks",
            title="Load Balancer target groups have no health checks",
            description=(
                "The target groups attached to your load balancer do not define explicit "
                "health checks. Without configured health checks, unhealthy targets may "
                "continue receiving traffic, causing request failures during deployments."
            ),
            severity="medium",
            category="reliability",
            target=targets,
            savings_monthly=0.0,
            risk="low",
            difficulty="easy",
            confidence="medium",
            improvement="Automatically drain and replace unhealthy targets.",
            why="Explicit health checks let the LB detect and stop routing to broken instances. "
            "Note: AWS provides default health checks even without explicit configuration, "
            "but custom health check paths and thresholds give you finer control.",
            impact="None — adds a small amount of LB traffic for probes.",
            cost_saved="Reduces customer-facing incidents; enables ASG health-driven scaling.",
            performance_impact="Negligible.",
            reliability_impact="Moderate — custom health checks improve detection speed.",
            security_impact="None.",
            evidence=[
                f"Found {len(albs)} ALB(s) and {len(target_groups)} target group(s)",
                "No explicit health_check block found on any target group",
                "Target groups use HTTP/HTTPS protocol (not TCP)",
            ],
            implementation=[
                "Define a ``health_check`` block on each target group.",
                "Set ``path`` to a lightweight endpoint like ``/healthz``.",
                "Set ``interval`` to 30s, ``healthy_threshold`` to 3, ``unhealthy_threshold`` to 3.",
                "Set ``deregistration_delay`` to drain in-flight requests.",
            ],
            modes={"balanced", "max-availability", "enterprise"},
            generated_code={
                "aws_lb_target_group": {
                    "name": target_groups[0].name if target_groups else "app",
                    "config": {
                        "health_check": {
                            "enabled": True,
                            "path": "/healthz",
                            "interval": 30,
                            "timeout": 5,
                            "healthy_threshold": 3,
                            "unhealthy_threshold": 3,
                        }
                    },
                }
            },
        )
    ]


def rule_single_ec2_asg(config: TerraformConfig) -> list[Recommendation]:
    """Recommend ASG only for standalone aws_instance resources.

    Only triggers when:
    - Actual aws_instance resources exist (not ECS, not data sources)
    - No ASG resources exist in the config
    - The instance is not referenced by a launch template or ASG
    """
    instances = _instances(config)
    if len(instances) == 0:
        return []

    # Only check for actual ASG resources
    asg_count = len([r for r in config.resources if r.kind == "asg" and not r.is_data])

    # Filter to instances not referenced by launch templates/ASGs
    standalone = [r for r in instances if r.id not in _referenced_asg_instances(config)]

    if asg_count > 0 or not standalone:
        return []

    recs = []
    for res in standalone[:3]:
        # Determine if this looks like a production workload
        has_elb = any(r.kind in ("alb", "elb") for r in config.resources if not r.is_data)
        severity = "high" if has_elb else "medium"

        recs.append(
            Recommendation(
                key="asg-recommendation",
                title=f"Wrap {res.name} in an Auto Scaling Group",
                description=(
                    f"Resource ``{res.name}`` (``{res.resource_type}``) is a standalone instance "
                    "not managed by an Auto Scaling Group. A single VM is a single point "
                    "of failure — ASGs give you auto-healing, rolling deploys, and "
                    "scale-out during load spikes."
                ),
                severity=severity,
                category="reliability",
                target=[res.id],
                savings_monthly=0.0,
                risk="medium",
                difficulty="medium",
                confidence="high",
                improvement="Self-healing capacity with 1–N replicas.",
                why="ASGs are the canonical EC2 deployment unit: they replace failed instances "
                "and let you scale with load.",
                impact="Requires the workload to be stateless or share state via EFS/RDS.",
                cost_saved="Enables spot + right-sizing strategies for further savings.",
                performance_impact="Can scale horizontally during traffic spikes.",
                reliability_impact="High — replaces failed instances automatically.",
                security_impact="Requires an instance profile with least-privilege permissions.",
                evidence=[
                    f"Found {len(instances)} standalone aws_instance resource(s)",
                    f"No ASG or launch template references found for {res.name}",
                    f"Resource type: {res.resource_type}",
                ],
                implementation=[
                    "Create a launch template (AMI, instance type, user_data, SG).",
                    "Create an ASG with min/max/desired and the launch template.",
                    "Attach a target group and an ELB for horizontal scaling.",
                    "Add a scale-out/scale-in policy based on CPU or request count.",
                ],
                modes={"balanced", "max-availability", "enterprise", "startup-budget"},
                generated_code={
                    "aws_autoscaling_group": {
                        "name": f"asg_{res.name}",
                        "config": {
                            "min_size": 1,
                            "max_size": 4,
                            "desired_capacity": 1,
                            "availability_zones": ["us-east-1a", "us-east-1b"],
                        },
                    }
                },
            )
        )
    return recs


def _referenced_asg_instances(config: TerraformConfig) -> set[str]:
    """Instances that are explicitly referenced by launch templates/ASGs."""
    refs: set[str] = set()
    for res in config.resources:
        if res.kind in ("launch_template", "asg"):
            refs.update(res.references)
    return refs


def rule_ebs_encryption(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for res in config.resources:
        if res.kind != "ebs":
            continue
        encrypted = res.attributes.get("encrypted", False)
        if encrypted is True or str(encrypted).lower() in ("true", "1"):
            continue
        recs.append(
            Recommendation(
                key="ebs-encryption",
                title=f"Encrypt EBS volume {res.name}",
                description=(
                    f"EBS volume ``{res.name}`` does not set ``encrypted = true``. Unencrypted "
                    "volumes expose data at rest and are a compliance violation for most "
                    "standards (SOC 2, HIPAA, PCI)."
                ),
                severity="high",
                category="security",
                target=[res.id],
                savings_monthly=0.0,
                risk="low",
                difficulty="easy",
                confidence="high",
                improvement="All data at rest encrypted with AWS KMS.",
                why="EBS encryption is free in every region and is the default on new accounts.",
                impact="None.",
                cost_saved="None (free feature).",
                performance_impact="None measurable.",
                reliability_impact="None.",
                security_impact="Encrypts data at rest; required by most compliance frameworks.",
                evidence=[
                    f"EBS volume {res.name} has encrypted={encrypted!r} (not true)",
                    "EBS encryption is free and enabled by default on new AWS accounts",
                ],
                implementation=[
                    "Set ``encrypted = true`` on the volume.",
                    "Optionally pass ``kms_key_id`` for a customer-managed key.",
                    "Set ``aws_ebs_encryption_by_default`` account-wide.",
                ],
                modes={"balanced", "enterprise", "max-availability"},
                generated_code={
                    "aws_ebs_volume": {"name": res.name, "config": {"encrypted": True}}
                },
            )
        )
    return recs


def rule_s3_versioning(config: TerraformConfig) -> list[Recommendation]:
    """Check for S3 buckets without versioning.

    Checks both:
    1. Inline versioning block on the bucket
    2. Separate aws_s3_bucket_versioning resource
    """
    recs: list[Recommendation] = []

    # Collect bucket names that have a separate versioning resource
    versioned_buckets: set[str] = set()
    for res in config.resources:
        if res.resource_type == "aws_s3_bucket_versioning" and not res.is_data:
            versioned_buckets.add(res.name)

    for res in config.resources:
        if res.kind != "s3" or res.is_data:
            continue

        # Check if versioned via separate resource
        if res.name in versioned_buckets:
            continue

        # Check inline versioning
        versioning = res.attributes.get("versioning")
        enabled = False
        if isinstance(versioning, list) and versioning:
            enabled = versioning[0].get("enabled") is True
        if not enabled:
            recs.append(
                Recommendation(
                    key="s3-versioning",
                    title=f"Enable versioning on S3 bucket {res.name}",
                    description=(
                        f"Bucket ``{res.name}`` does not enable versioning. Versioning protects "
                        "you from accidental overwrites, deletions and ransomware-style attacks."
                    ),
                    severity="medium",
                    category="disaster-recovery",
                    target=[res.id],
                    savings_monthly=0.0,
                    risk="low",
                    difficulty="easy",
                    confidence="high",
                    improvement="Roll back any object to any prior version.",
                    why="Unversioned buckets lose data permanently on overwrite or delete.",
                    impact="Storage grows with versions; use lifecycle rules to expire old ones.",
                    cost_saved="Prevents data-loss incidents.",
                    performance_impact="None.",
                    reliability_impact="High — recoverability of object store.",
                    security_impact="Versioning + MFA delete mitigates ransomware.",
                    evidence=[
                        f"No inline versioning block found on bucket {res.name}",
                        "No separate aws_s3_bucket_versioning resource found",
                    ],
                    implementation=[
                        "Add a ``versioning`` block with ``enabled = true``.",
                        "Add lifecycle rule to expire old noncurrent versions (e.g. 30 days).",
                        "Consider ``object_lock_enabled`` with retention for critical buckets.",
                    ],
                    modes={"balanced", "enterprise", "max-availability"},
                    generated_code={
                        "aws_s3_bucket_versioning": {
                            "name": res.name,
                            "config": {
                                "bucket": f"aws_s3_bucket.{res.name}.id",
                                "versioning_configuration": {"status": "Enabled"},
                            },
                        }
                    },
                )
            )
    return recs


def rule_ebs_gp2_to_gp3(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for res in config.resources:
        if res.kind != "ebs":
            continue
        vtype = str(res.attributes.get("type", "gp3"))
        if vtype != "gp2":
            continue
        size = res.attributes.get("size", 30)
        try:
            size = float(size)
        except (TypeError, ValueError):
            size = 30
        savings = size * 0.02
        recs.append(
            Recommendation(
                key="ebs-gp3",
                title=f"Upgrade EBS volume {res.name} from gp2 to gp3",
                description=(
                    f"Volume ``{res.name}`` uses gp2. gp3 provides the same baseline "
                    "performance for ~20% less ($0.08 vs $0.10/GB-mo) with burst-free "
                    "IOPS and throughput."
                ),
                severity="low",
                category="cost",
                target=[res.id],
                savings_monthly=savings_floor(savings),
                risk="low",
                difficulty="easy",
                confidence="high",
                improvement="Cut EBS spend ~20% with equal or better performance.",
                why="gp3 is the current default and cheaper at every size.",
                impact="None — gp3 can match gp2 IOPS at 3000 baseline.",
                cost_saved=f"~${savings:,.2f}/mo",
                performance_impact="Improved: gp3 baseline 3000 IOPS/125 MB/s vs gp2 100 IOPS/GB.",
                reliability_impact="None.",
                security_impact="None.",
                evidence=[
                    f"Volume {res.name} is type=gp2, size={size:.0f}GB",
                    f"gp3 pricing $0.08/GB-mo vs gp2 $0.10/GB-mo; savings ~${savings:,.2f}/mo",
                ],
                implementation=[
                    'Change ``type = "gp3"`` (AWS converts live with no downtime).',
                    "Optionally set ``iops``/``throughput`` for high-perf workloads.",
                ],
                modes={"lowest-cost", "startup-budget", "balanced", "lowest-carbon"},
                generated_code={"aws_ebs_volume": {"name": res.name, "config": {"type": "gp3"}}},
            )
        )
    return recs


def rule_graviton(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for res in _instances(config):
        itype = str(_ec2_attr(res, "instance_type", ""))
        if itype.startswith("t") and not itype.startswith("t4"):
            spec = get_ec2(itype)
            if not spec:
                continue
            savings = spec.monthly * 0.2
            recs.append(
                Recommendation(
                    key="graviton",
                    title=f"Consider Graviton (t4g) for {res.name}",
                    description=(
                        f"{res.name} runs a {itype}. Graviton (ARM) instances like t4g offer "
                        "~20% lower cost and up to 40% better price-performance for most "
                        "workloads."
                    ),
                    severity="low",
                    category="cost",
                    target=[res.id],
                    savings_monthly=savings_floor(savings),
                    risk="medium",
                    difficulty="hard",
                    confidence="medium",
                    improvement="~20% cheaper compute with better performance.",
                    why="Graviton3/4 outpaces x86 on price-performance for typical services.",
                    impact="Must verify container images & compiled binaries are arm64.",
                    cost_saved=f"~${savings:,.0f}/mo",
                    performance_impact="Better for many workloads; test first.",
                    reliability_impact="None.",
                    security_impact="None.",
                    evidence=[
                        f"Instance {res.name} runs {itype} (x86); t4g equivalent saves ~20%",
                        "Confidence=medium because arm64 compatibility requires runtime verification",
                    ],
                    implementation=[
                        "Build arm64 container images (multi-arch).",
                        "Test in staging on t4g with identical code.",
                        "Switch instance type and re-run benchmarks.",
                    ],
                    modes={"lowest-cost", "balanced", "lowest-carbon", "startup-budget"},
                )
            )
    return recs


def rule_lambda_memory(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for res in config.resources:
        if res.kind != "lambda":
            continue
        mem = res.attributes.get("memory_size", 128)
        try:
            mem = int(mem)
        except (TypeError, ValueError):
            mem = 128
        if mem == 128 and "timeout" in res.attributes:
            recs.append(
                Recommendation(
                    key="lambda-memory",
                    title=f"Check Lambda {res.name} memory configuration",
                    description=(
                        f"{res.name} uses the default 128 MB. Many Lambdas run 1–2s slower at "
                        "128 MB than at 512 MB/1024 MB — and Lambda is billed by GB-second, so "
                        "faster execution can be *cheaper* at higher memory."
                    ),
                    severity="low",
                    category="cost",
                    target=[res.id],
                    savings_monthly=savings_floor(0.5),
                    risk="low",
                    difficulty="easy",
                    confidence="low",
                    improvement="Lower latency and potentially lower cost.",
                    why="Lambda billing favors fast execution; 512–1024 MB often pays for itself.",
                    impact="None — this is a tuning recommendation.",
                    cost_saved="~$0.5/mo typical, plus latency wins.",
                    performance_impact="Up to 60% faster execution.",
                    reliability_impact="None.",
                    security_impact="None.",
                    evidence=[
                        f"Lambda {res.name} has memory_size=128 (default)",
                        "Confidence=low because optimal memory depends on runtime profile — requires testing",
                    ],
                    implementation=[
                        "Load-test the function at 128/512/1024 MB.",
                        "Pick the cheapest setting that meets your latency target.",
                        "Enable Lambda Power Tuning to automate the search.",
                    ],
                    modes={"lowest-cost", "lowest-latency", "balanced", "startup-budget"},
                )
            )
        if not res.attributes.get("dead_letter_config") and res.attributes.get(
            "event_source_mapping"
        ):
            pass
    return recs


def rule_observability(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    # Absence of alarms cannot be established when unexpanded modules may
    # contain them — never claim a gap we did not inspect.
    if config.has_unexpanded_modules:
        return recs
    alarms = [r for r in config.resources if r.kind == "cloudwatch" and not r.is_data]
    has_instances = bool(_instances(config))
    if has_instances and not alarms:
        recs.append(
            Recommendation(
                key="cw-alarms",
                title="Configuration does not declare CloudWatch alarms for EC2",
                description=(
                    "The Terraform configuration includes EC2 instances but no CloudWatch "
                    "alarm resources. Without CPU, memory and status-check alarms declared, "
                    "degraded instances are discovered only when users complain."
                ),
                severity="high",
                category="observability",
                target=[r.id for r in _instances(config)],
                savings_monthly=0.0,
                risk="low",
                difficulty="easy",
                confidence="high",
                improvement="Alert on CPU > 85%, memory pressure, and status-check failures.",
                why="Alarms are the difference between proactive and reactive operations.",
                impact="~$0.10/mo per alarm.",
                cost_saved="Prevents revenue-impacting downtime.",
                performance_impact="None.",
                reliability_impact="Faster MTTR for capacity and availability issues.",
                security_impact="None.",
                evidence=[
                    f"Found {len(_instances(config))} EC2 instance(s) but no CloudWatch alarms",
                    "AWS provides basic monitoring free; detailed monitoring is $0.30/mo/instance",
                ],
                implementation=[
                    "Create alarms: CPUUtilization > 85% for 10 min; StatusCheckFailed.",
                    "Set alarm actions to an SNS topic that pages on-call.",
                    "Ship metrics to CloudWatch Agent for memory/disk.",
                ],
                modes={"max-availability", "enterprise", "balanced"},
            )
        )
    lambdas = [r for r in config.resources if r.kind == "lambda"]
    log_groups = [
        r for r in config.resources if r.kind == "cloudwatch" and r.label == "CloudWatch Log Group"
    ]
    if lambdas and not log_groups and not any(r.kind == "cloudwatch" for r in config.resources):
        recs.append(
            Recommendation(
                key="lambda-logging",
                title="Ensure Lambda logging and tracing are configured",
                description=(
                    "The Terraform configuration does not declare a CloudWatch Log Group "
                    "for your Lambda functions. Without logs and X-Ray tracing configured, "
                    "debugging serverless failures requires guesswork."
                ),
                severity="medium",
                category="observability",
                target=[r.id for r in lambdas],
                savings_monthly=0.0,
                risk="low",
                difficulty="easy",
                improvement="Structured logs + request tracing for every invocation.",
                why="Log groups are the foundation of serverless observability.",
                impact="Small log-storage cost (first 5 GB free).",
                cost_saved="Not applicable.",
                performance_impact="None.",
                reliability_impact="Faster root-cause analysis.",
                security_impact="Logs aid audit and forensics.",
                implementation=[
                    "Add ``aws_cloudwatch_log_group`` per function.",
                    "Enable X-Ray tracing on the function.",
                    "Set a log retention policy to control cost.",
                ],
                modes={"max-availability", "enterprise", "balanced"},
            )
        )
    return recs


def rule_missing_tags(config: TerraformConfig) -> list[Recommendation]:
    untagged = [
        r
        for r in config.resources
        if r.kind in ("ec2", "ebs", "s3", "rds") and not r.attributes.get("tags")
    ]
    if not untagged:
        return []
    return [
        Recommendation(
            key="missing-tags",
            title="Add cost-allocation tags to your resources",
            description=(
                f"{len(untagged)} billable resources have no ``tags`` block in their "
                "Terraform configuration. Without tags, Cost Explorer cannot segment "
                "spend by team/project/environment."
            ),
            severity="low",
            category="cost",
            target=[r.id for r in untagged[:5]],
            savings_monthly=0.0,
            risk="low",
            difficulty="easy",
            confidence="high",
            improvement="Enable granular cost allocation and ownership tracking.",
            why="Tags are the backbone of FinOps and are cheap to add now, painful to retrofit.",
            impact="None.",
            cost_saved="Enables cost visibility that typically surfaces 10–30% savings.",
            performance_impact="None.",
            reliability_impact="None.",
            security_impact="None.",
            evidence=[
                f"{len(untagged)} resource(s) missing tags block",
                "Without tags, Cost Explorer cannot segment spend by team or environment",
            ],
            implementation=[
                "Standardize on tags: ``owner``, ``environment``, ``project``, ``cost-center``.",
                "Add tags to each resource block.",
                "Enable cost allocation tags in Billing console.",
            ],
            modes={"lowest-cost", "startup-budget", "enterprise", "balanced"},
        )
    ]


def rule_compliance_retention(config: TerraformConfig) -> list[Recommendation]:
    log_groups = [
        r for r in config.resources if r.kind == "cloudwatch" and r.label == "CloudWatch Log Group"
    ]
    if not log_groups:
        return []
    return [
        Recommendation(
            key="log-retention",
            title="Set retention on CloudWatch Log Groups",
            description=(
                f"{len(log_groups)} log group(s) do not declare ``retention_in_days``. "
                "AWS default is to keep logs forever, silently growing your bill and "
                "expanding compliance scope."
            ),
            severity="medium",
            category="compliance",
            target=[r.id for r in log_groups],
            savings_monthly=savings_floor(2.0),
            risk="low",
            difficulty="easy",
            confidence="high",
            improvement="Predictable log storage cost with policy-aligned retention.",
            why="AWS default is to keep logs forever, growing storage cost indefinitely.",
            impact="None; old logs expire automatically.",
            cost_saved="~$2/mo typical for small fleets.",
            performance_impact="None.",
            reliability_impact="None.",
            security_impact="Aligns data lifecycle with compliance policy.",
            evidence=[
                f"{len(log_groups)} CloudWatch Log Group(s) missing retention_in_days",
                "AWS default is to keep logs forever, growing storage cost indefinitely",
            ],
            implementation=[
                "Set ``retention_in_days = 30`` (dev) / 90–365 (prod).",
                "Add an S3 export policy for logs you must archive.",
            ],
            modes={"enterprise", "balanced"},
        )
    ]


def rule_ecs_eks_scaling(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    services = [r for r in config.resources if r.kind == "ecs" and not r.is_data]
    for res in services:
        if res.resource_type == "aws_ecs_service":
            desired = res.attributes.get("desired_count")
            if desired in (1, None, "", "1") and not res.attributes.get("autoscaling"):
                recs.append(
                    Recommendation(
                        key="ecs-scaling",
                        title=f"Configuration for ECS service {res.name} does not declare autoscaling",
                        description=(
                            f"{res.name} is configured with a fixed desired_count. The "
                            "Terraform configuration does not declare an autoscaling block "
                            "with Application Auto Scaling."
                        ),
                        severity="medium",
                        category="scalability",
                        target=[res.id],
                        savings_monthly=0.0,
                        risk="medium",
                        difficulty="medium",
                        confidence="high",
                        improvement="Elastic capacity between min and max replicas.",
                        why="Fixed counts over-provision for peak and under-provision for growth.",
                        impact="Requires service CPU/memory reservations to be defined.",
                        cost_saved="Typically 15–40% of ECS spend with utilization-based scaling.",
                        performance_impact="Better latency at peak.",
                        reliability_impact="Handles load spikes gracefully.",
                        security_impact="None.",
                        evidence=[
                            f"ECS service {res.name} has desired_count={desired!r} (fixed)",
                            "No autoscaling block configured; capacity is static",
                        ],
                        implementation=[
                            "Define target tracking on CPU utilization (50–70%).",
                            "Set a scale-in cool-down to avoid thrash.",
                            "Verify deployment strategy with rolling updates.",
                        ],
                        modes={"max-availability", "balanced", "startup-budget"},
                    )
                )
    return recs


def rule_elasticache(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for res in config.resources:
        if (
            res.kind == "elasticache"
            and "replication_group" not in res.resource_type
            and not res.is_data
        ):
            recs.append(
                Recommendation(
                    key="elasticache-ha",
                    title=f"ElastiCache {res.name} configuration does not declare replicas",
                    description=(
                        f"{res.name} is configured as a single-node cache cluster with no "
                        "replica nodes declared. Without replicas, a node failure empties "
                        "the cache and can hammer your database."
                    ),
                    severity="medium",
                    category="reliability",
                    target=[res.id],
                    savings_monthly=0.0,
                    risk="low",
                    difficulty="easy",
                    confidence="high",
                    improvement="Automatic failover with a replica node.",
                    why="A single cache node is a soft single point of failure for your DB.",
                    impact="~2x cache compute cost.",
                    cost_saved="Prevents DB load spikes after cache loss.",
                    performance_impact="None.",
                    reliability_impact="High — auto-failover in seconds.",
                    security_impact="None.",
                    evidence=[
                        f"ElastiCache {res.name} is not part of a replication_group",
                        "Single-node clusters have no automatic failover",
                    ],
                    implementation=[
                        "Migrate to a replication group with one replica.",
                        "Enable automatic failover.",
                        "Add a backup window and snapshot retention.",
                    ],
                    modes={"max-availability", "enterprise", "balanced"},
                )
            )
    return recs


def rule_s3_encryption(config: TerraformConfig) -> list[Recommendation]:
    """Check for S3 buckets without server-side encryption.

    Checks both:
    1. Inline server_side_encryption_configuration block on the bucket
    2. Separate aws_s3_bucket_server_side_encryption_configuration resource

    This prevents false positives when encryption is configured via a separate resource.
    """
    recs: list[Recommendation] = []

    # Collect bucket names that have a separate encryption config resource
    encrypted_buckets: set[str] = set()
    for res in config.resources:
        if (
            res.resource_type == "aws_s3_bucket_server_side_encryption_configuration"
            and not res.is_data
        ):
            # The name of this resource matches the bucket name
            encrypted_buckets.add(res.name)

    for res in config.resources:
        if res.kind != "s3" or res.is_data:
            continue

        # Check if encrypted via separate resource
        if res.name in encrypted_buckets:
            continue

        # Check inline encryption configuration
        enc = res.attributes.get("server_side_encryption_configuration") or res.attributes.get(
            "encryption"
        )
        has_enc = enc not in (None, [], {}, "")
        if not has_enc:
            recs.append(
                Recommendation(
                    key="s3-encryption",
                    title=f"Enable server-side encryption on S3 bucket {res.name}",
                    description=(
                        f"Server-side encryption is not explicitly declared in the "
                        f"Terraform configuration for bucket ``{res.name}``. Without "
                        "an ``aws_s3_bucket_server_side_encryption_configuration`` "
                        "resource or inline ``server_side_encryption_configuration`` "
                        "block, encryption behavior depends on the bucket owner's "
                        "default settings. Explicitly declaring SSE ensures "
                        "compliance with most security standards."
                    ),
                    severity="high",
                    category="security",
                    target=[res.id],
                    savings_monthly=0.0,
                    risk="low",
                    difficulty="easy",
                    confidence="high",
                    improvement="All objects encrypted with SSE-S3 or SSE-KMS.",
                    why="SSE-S3 is free and may be the default, but explicit declaration "
                    "ensures encryption is enforced even if defaults change.",
                    impact="None.",
                    cost_saved="None.",
                    performance_impact="None.",
                    reliability_impact="None.",
                    security_impact="Ensures data-at-rest encryption is explicitly configured.",
                    evidence=[
                        f"No server_side_encryption_configuration found on bucket {res.name}",
                        "No separate aws_s3_bucket_server_side_encryption_configuration resource found",
                        "Encryption behavior depends on bucket owner default settings",
                    ],
                    implementation=[
                        "Add a dedicated ``aws_s3_bucket_server_side_encryption_configuration`` resource referencing the bucket.",
                        "Use SSE-KMS for compliance-grade key control.",
                    ],
                    modes={"balanced", "enterprise", "max-availability"},
                    generated_code={
                        "aws_s3_bucket_server_side_encryption_configuration": {
                            "name": res.name,
                            "config": {
                                "bucket": f"aws_s3_bucket.{res.name}.id",
                                "rule": {
                                    "apply_server_side_encryption_by_default": {
                                        "sse_algorithm": "AES256"
                                    }
                                },
                            },
                        }
                    },
                )
            )
    return recs


def rule_public_subnet_instances(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for res in _instances(config):
        attrs = res.attributes
        if (
            attrs.get("associate_public_ip_address") is True
            or attrs.get("associate_public_ip") is True
        ):
            recs.append(
                Recommendation(
                    key="public-ec2",
                    title=f"Configuration assigns a public IP to {res.name}",
                    description=(
                        f"{res.name} has ``associate_public_ip_address = true`` in its "
                        "Terraform configuration. Unless this is an explicit bastion, "
                        "instances belong in private subnets behind a load balancer or NAT."
                    ),
                    severity="medium",
                    category="security",
                    target=[res.id],
                    savings_monthly=0.0,
                    risk="medium",
                    difficulty="medium",
                    confidence="high",
                    improvement="Remove direct internet exposure from application instances.",
                    why="Direct public IPs widen the attack surface and complicate egress "
                    "control and WAF integration.",
                    impact="Requires ALB or tunnel for ingress.",
                    cost_saved="None directly.",
                    performance_impact="None.",
                    reliability_impact="None.",
                    security_impact="Reduces exposure; forces traffic through controlled paths.",
                    evidence=[
                        f"Instance {res.name} has associate_public_ip_address=True in Terraform config",
                        "Public IP means direct internet exposure without WAF or load balancer",
                    ],
                    implementation=[
                        "Move the instance to a private subnet.",
                        "Route ingress through the ALB/CloudFront.",
                        "Set ``associate_public_ip_address = false``.",
                    ],
                    modes={"balanced", "enterprise", "max-availability"},
                )
            )
    return recs


def rule_no_route53(config: TerraformConfig) -> list[Recommendation]:
    instances = _instances(config)
    if not instances:
        return []
    # DNS/CDN may be declared inside unexpanded modules — absence unproven.
    if config.has_unexpanded_modules:
        return []
    has_dns = any(r.kind in ("route53", "cloudfront") for r in config.resources if not r.is_data)
    if has_dns:
        return []
    return [
        Recommendation(
            key="no-dns",
            title="Route public traffic through Route53 + CloudFront",
            description=(
                "The Terraform configuration does not declare Route53 records or "
                "CloudFront distributions for your compute endpoints. Direct access "
                "bypasses caching, WAF and HTTP/2 + connection reuse, and makes "
                "blue/green cutovers harder."
            ),
            severity="low",
            category="networking",
            target=[r.id for r in instances],
            savings_monthly=savings_floor(5.0),
            risk="low",
            difficulty="medium",
            confidence="medium",
            improvement="Better latency, TLS management and cheaper data transfer via CloudFront.",
            why="CloudFront egress ($0.085/GB) is cheaper than direct internet egress ($0.09/GB) "
            "and adds a CDN layer for static assets.",
            impact="Requires DNS cutover; keep old A records during transition.",
            cost_saved="~$5/mo typical on egress.",
            performance_impact="Better TTFB with edge caching.",
            reliability_impact="CloudFront origin failover.",
            security_impact="WAF + Shield protection in front of origin.",
            evidence=[
                f"Found {len(instances)} compute instance(s) with no Route53 or CloudFront resources",
                "Direct IP/ALB access bypasses CDN, WAF, and DNS-based routing",
            ],
            implementation=[
                "Create a hosted zone for your domain.",
                "Point apex to CloudFront distribution (origin = ALB).",
                "Configure cache behaviors for static assets.",
                "Attach WAF ACL for rate limiting.",
            ],
            modes={"balanced", "lowest-latency", "enterprise", "lowest-cost"},
        )
    ]


def rule_rds_public_access(config: TerraformConfig) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for res in config.resources:
        if res.kind != "rds" or res.is_data:
            continue
        public = res.attributes.get("publicly_accessible")
        if public is True or str(public).lower() == "true":
            recs.append(
                Recommendation(
                    key="rds-public",
                    title=f"Configuration sets RDS {res.name} as publicly accessible",
                    description=(
                        f"{res.name} has ``publicly_accessible = true`` in its Terraform "
                        "configuration. Production databases should not be reachable from "
                        "the internet — this setting makes the endpoint reachable from any IP."
                    ),
                    severity="critical",
                    category="security",
                    target=[res.id],
                    savings_monthly=0.0,
                    risk="low",
                    difficulty="easy",
                    confidence="high",
                    improvement="Restrict database access to the VPC.",
                    why="Public databases are a leading cause of data exfiltration.",
                    impact="Requires app traffic via private endpoint/bastion.",
                    cost_saved="Prevents catastrophic breach costs.",
                    performance_impact="None.",
                    reliability_impact="None.",
                    security_impact="Major — removes internet-exposed DB surface.",
                    evidence=[
                        f"RDS instance {res.name} has publicly_accessible=True in Terraform config",
                        "This makes the database endpoint reachable from any IP on the internet",
                    ],
                    implementation=[
                        "Set ``publicly_accessible = false``.",
                        "Attach a security group restricted to app SG.",
                        "Connect through a private VPC endpoint or bastion.",
                    ],
                    modes={"balanced", "enterprise", "max-availability", "startup-budget"},
                    generated_code={
                        "aws_db_instance": {
                            "name": res.name,
                            "config": {"publicly_accessible": False},
                        }
                    },
                )
            )
    return recs


ALL_RULES: list[tuple[str, RuleFn]] = [
    ("Security groups open to the world", rule_sg_open_world),
    ("Security group overlaps", rule_sg_overlaps),
    ("RDS publicly accessible", rule_rds_public_access),
    ("RDS backups & resilience", rule_rds_backups),
    ("EBS encryption", rule_ebs_encryption),
    ("S3 encryption", rule_s3_encryption),
    ("S3 versioning", rule_s3_versioning),
    ("Public EC2 IPs", rule_public_subnet_instances),
    ("NAT gateway sprawl", rule_nat_gateway),
    ("Oversized EC2", rule_ec2_oversized),
    ("Spot instance opportunity", rule_spot_instances),
    ("Graviton migration", rule_graviton),
    ("gp2 to gp3", rule_ebs_gp2_to_gp3),
    ("Lambda tuning", rule_lambda_memory),
    ("ALB health checks", rule_alb_health_checks),
    ("Standalone EC2 -> ASG", rule_single_ec2_asg),
    ("Observability coverage", rule_observability),
    ("Cost tags", rule_missing_tags),
    ("Log retention", rule_compliance_retention),
    ("ECS autoscaling", rule_ecs_eks_scaling),
    ("ElastiCache HA", rule_elasticache),
    ("DNS / CDN", rule_no_route53),
]
