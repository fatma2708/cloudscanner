"""AWS pricing catalog.

Approximate list-price (on-demand) data for the most common services CloudPilot
analyzes. Prices are per-unit/hour or per-GB/month as noted, in USD. They are
intentionally approximate — real costs depend on region, commitment, and usage.
"""

from __future__ import annotations

from dataclasses import dataclass

MONTHLY_HOURS = 730.0


@dataclass(frozen=True)
class InstanceSpec:
    vcpu: int
    ram_gb: float
    hourly: float

    @property
    def monthly(self) -> float:
        return self.hourly * MONTHLY_HOURS


# EC2 on-demand hourly (us-east-1, approximate)
EC2 = {
    "t3.nano": InstanceSpec(2, 0.5, 0.0052),
    "t3.micro": InstanceSpec(2, 1, 0.0104),
    "t3.small": InstanceSpec(2, 2, 0.0208),
    "t3.medium": InstanceSpec(2, 4, 0.0416),
    "t3.large": InstanceSpec(2, 8, 0.0832),
    "t3.xlarge": InstanceSpec(4, 16, 0.1664),
    "t3.2xlarge": InstanceSpec(8, 32, 0.3328),
    "t4g.nano": InstanceSpec(2, 0.5, 0.0042),
    "t4g.micro": InstanceSpec(2, 1, 0.0084),
    "t4g.small": InstanceSpec(2, 2, 0.0168),
    "t4g.medium": InstanceSpec(2, 4, 0.0336),
    "t4g.large": InstanceSpec(2, 8, 0.0672),
    "t4g.xlarge": InstanceSpec(4, 16, 0.1344),
    "t4g.2xlarge": InstanceSpec(8, 32, 0.2688),
    "m5.large": InstanceSpec(2, 8, 0.096),
    "m5.xlarge": InstanceSpec(4, 16, 0.192),
    "m5.2xlarge": InstanceSpec(8, 32, 0.384),
    "m5.4xlarge": InstanceSpec(16, 64, 0.768),
    "m5.8xlarge": InstanceSpec(32, 128, 1.536),
    "m5.12xlarge": InstanceSpec(48, 192, 2.304),
    "m6i.large": InstanceSpec(2, 8, 0.096),
    "m6i.xlarge": InstanceSpec(4, 16, 0.192),
    "m6i.2xlarge": InstanceSpec(8, 32, 0.384),
    "m6i.4xlarge": InstanceSpec(16, 64, 0.768),
    "m6i.8xlarge": InstanceSpec(32, 128, 1.536),
    "c5.large": InstanceSpec(2, 4, 0.085),
    "c5.xlarge": InstanceSpec(4, 8, 0.17),
    "c5.2xlarge": InstanceSpec(8, 16, 0.34),
    "c5.4xlarge": InstanceSpec(16, 32, 0.68),
    "c5.9xlarge": InstanceSpec(36, 72, 1.53),
    "c6i.large": InstanceSpec(2, 4, 0.085),
    "c6i.xlarge": InstanceSpec(4, 8, 0.17),
    "c6i.2xlarge": InstanceSpec(8, 16, 0.34),
    "c6i.4xlarge": InstanceSpec(16, 32, 0.68),
    "r5.large": InstanceSpec(2, 16, 0.126),
    "r5.xlarge": InstanceSpec(4, 32, 0.252),
    "r5.2xlarge": InstanceSpec(8, 64, 0.504),
    "r5.4xlarge": InstanceSpec(16, 128, 1.008),
    "r6i.large": InstanceSpec(2, 16, 0.126),
    "r6i.xlarge": InstanceSpec(4, 32, 0.252),
    "r6i.2xlarge": InstanceSpec(8, 64, 0.504),
    "i3.large": InstanceSpec(2, 15.25, 0.156),
    "i3.xlarge": InstanceSpec(4, 30.5, 0.312),
    "i3.2xlarge": InstanceSpec(8, 61, 0.624),
    "g4dn.xlarge": InstanceSpec(4, 16, 0.526),
    "g4dn.2xlarge": InstanceSpec(8, 32, 0.752),
    "g4dn.4xlarge": InstanceSpec(16, 64, 1.204),
    "g5.xlarge": InstanceSpec(4, 16, 1.006),
    "g5.2xlarge": InstanceSpec(8, 32, 1.848),
    "p3.2xlarge": InstanceSpec(8, 61, 3.06),
    "p4d.24xlarge": InstanceSpec(96, 1152, 32.77),
    "a1.medium": InstanceSpec(1, 2, 0.0255),
    "a1.large": InstanceSpec(2, 4, 0.051),
}

# RDS on-demand hourly (single-AZ, approximate)
RDS = {
    "db.t3.micro": InstanceSpec(2, 1, 0.016),
    "db.t3.small": InstanceSpec(2, 2, 0.034),
    "db.t3.medium": InstanceSpec(2, 4, 0.068),
    "db.t3.large": InstanceSpec(2, 8, 0.136),
    "db.t4g.micro": InstanceSpec(2, 1, 0.016),
    "db.t4g.small": InstanceSpec(2, 2, 0.034),
    "db.t4g.medium": InstanceSpec(2, 4, 0.068),
    "db.t4g.large": InstanceSpec(2, 8, 0.136),
    "db.m5.large": InstanceSpec(2, 8, 0.155),
    "db.m5.xlarge": InstanceSpec(4, 16, 0.31),
    "db.m5.2xlarge": InstanceSpec(8, 32, 0.62),
    "db.m5.4xlarge": InstanceSpec(16, 64, 1.24),
    "db.m6i.large": InstanceSpec(2, 8, 0.155),
    "db.m6i.xlarge": InstanceSpec(4, 16, 0.31),
    "db.m6i.2xlarge": InstanceSpec(8, 32, 0.62),
    "db.m6i.4xlarge": InstanceSpec(16, 64, 1.24),
    "db.r5.large": InstanceSpec(2, 16, 0.19),
    "db.r5.xlarge": InstanceSpec(4, 32, 0.38),
    "db.r5.2xlarge": InstanceSpec(8, 64, 0.76),
    "db.r5.4xlarge": InstanceSpec(16, 128, 1.52),
    "db.r6i.large": InstanceSpec(2, 16, 0.19),
    "db.r6i.xlarge": InstanceSpec(4, 32, 0.38),
    "db.r6i.2xlarge": InstanceSpec(8, 64, 0.76),
    "db.r6i.4xlarge": InstanceSpec(16, 128, 1.52),
}

# Storage monthly per GB
STORAGE_GB = {
    "ebs_gp3": 0.08,
    "ebs_gp2": 0.10,
    "ebs_io1": 0.125,
    "ebs_standard": 0.05,
    "s3_standard": 0.023,
    "efs_standard": 0.30,
    "ebs_snapshot": 0.05,
    "dynamodb_standard": 0.25,
}

# Flat monthly prices for shared services
FLAT_MONTHLY = {
    "nat_gateway": 32.22,
    "eip": 3.60,
    "alb": 16.43,
    "nlb": 16.43,
    "elb": 18.25,
    "cloudwatch_alarm": 0.10,
    "eks_cluster": 73.0,
    "route53_zone": 0.50,
    "waf": 10.0,
    "backup_vault": 0.05,
    "kms_key": 1.0,
}

# Per-unit prices
PER_UNIT = {
    "lambda_gbs": 0.0000166667,  # per GB-second
    "lambda_request": 0.20e-6,  # per request
    "nat_gb_processing": 0.045,  # per GB
    "data_transfer_egress": 0.09,  # per GB out
    "cloudfront_data_transfer": 0.085,  # per GB out
    "dynamodb_request": 0.25e-6,  # per request (on-demand, mixed R/W)
    "route53_query": 0.40e-6,  # per 1M queries -> $0.40 per 1M
}

# Egress allowance per workload type (GB/month) used to estimate data transfer
DEFAULT_EGRESS_GB = 100.0

DEFAULT_EC2 = "t3.medium"
DEFAULT_RDS = "db.t3.medium"
DEFAULT_EBS_GB = 30.0
DEFAULT_S3_GB = 100.0
DEFAULT_EFS_GB = 20.0

# Spot discount vs on-demand
SPOT_DISCOUNT = 0.30  # pay ~30% of on-demand
RESERVED_1Y_DISCOUNT = 0.40  # pay ~60% of on-demand with 1y all-upfront

# Carbon intensity per region, gCO2eq / kWh (approximate 2024 public grid data)
GRID_INTENSITY = {
    "us-east-1": 485,
    "us-east-2": 533,
    "us-west-1": 405,
    "us-west-2": 376,
    "us-gov-west-1": 405,
    "eu-west-1": 280,
    "eu-west-2": 215,
    "eu-west-3": 110,
    "eu-central-1": 350,
    "eu-north-1": 60,
    "eu-south-1": 340,
    "ap-south-1": 716,
    "ap-northeast-1": 532,
    "ap-northeast-2": 547,
    "ap-northeast-3": 547,
    "ap-southeast-1": 559,
    "ap-southeast-2": 790,
    "ap-southeast-3": 730,
    "ap-east-1": 600,
    "sa-east-1": 478,
    "ca-central-1": 120,
    "me-south-1": 700,
    "af-south-1": 900,
}
DEFAULT_GRID_INTENSITY = 485


def grid_intensity(region: str) -> float:
    """Return grid carbon intensity for an AWS region, gCO2eq/kWh."""
    return GRID_INTENSITY.get(region, DEFAULT_GRID_INTENSITY)


def get_ec2(instance_type: str) -> InstanceSpec | None:
    """Return an EC2 instance spec by type name (case-insensitive)."""
    return EC2.get(instance_type.lower())


def get_rds(instance_class: str) -> InstanceSpec | None:
    return RDS.get(instance_class.lower())


def nearest_ec2(vcpu: int, ram_gb: float) -> InstanceSpec:
    """Pick the cheapest catalog instance that meets vcpu & ram requirements."""
    candidates = [
        spec for spec in EC2.values() if spec.vcpu >= vcpu and spec.ram_gb >= ram_gb - 0.01
    ]
    if not candidates:
        return InstanceSpec(vcpu=vcpu, ram_gb=ram_gb, hourly=max(4.0, vcpu * 0.05))
    return min(candidates, key=lambda s: s.hourly)
