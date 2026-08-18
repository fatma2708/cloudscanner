"""Provider and service registry for Terraform resource types.

Maps a resource type string (``aws_instance``) to a canonical CloudPilot
service and display kind. This is the single source of truth used by the
parser, the pricing engine, the recommendation engine and the architecture
diagram generator.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceKind:
    service: str
    kind: str
    label: str
    icon: str = "box"


_PROVIDER_PREFIXES = {
    "aws": "AWS",
    "azurerm": "Azure",
    "google": "GCP",
    "digitalocean": "DigitalOcean",
    "hcloud": "Hetzner",
    "scaleway": "Scaleway",
    "ovh": "OVHCloud",
    "oci": "Oracle",
    "vultr": "Vultr",
    "linode": "Linode",
    "cloudflare": "Cloudflare",
    "kubernetes": "Kubernetes",
}


def provider_of(resource_type: str) -> str:
    """Extract the canonical provider key from a resource type (e.g. ``aws``)."""
    head = resource_type.split("_", 1)[0]
    return head


def provider_label(provider: str) -> str:
    """Human readable provider label."""
    return _PROVIDER_PREFIXES.get(provider, provider.title())


# type-prefix -> canonical service
_SERVICE_PREFIXES: dict[str, tuple[str, str, str]] = {
    # Compute
    "aws_instance": ("compute", "ec2", "EC2 Instance"),
    "aws_launch_template": ("compute", "ec2", "Launch Template"),
    "aws_launch_configuration": ("compute", "ec2", "Launch Configuration"),
    "aws_autoscaling_group": ("compute", "asg", "Auto Scaling Group"),
    "aws_spot_fleet_request": ("compute", "ec2", "Spot Fleet"),
    "aws_ecs_cluster": ("compute", "ecs", "ECS Cluster"),
    "aws_ecs_service": ("compute", "ecs_service", "ECS Service"),
    "aws_ecs_task_definition": ("compute", "ecs_task_definition", "ECS Task Definition"),
    "aws_eks_cluster": ("compute", "eks", "EKS Cluster"),
    "aws_eks_node_group": ("compute", "eks", "EKS Node Group"),
    "aws_lambda_function": ("compute", "lambda", "Lambda Function"),
    "aws_lambda_alias": ("compute", "lambda", "Lambda Alias"),
    "aws_lambda_event_source_mapping": ("compute", "lambda", "Lambda Event Source"),
    "aws_elastic_beanstalk_environment": ("compute", "ec2", "Elastic Beanstalk"),
    # Network
    "aws_vpc": ("network", "vpc", "VPC"),
    "aws_subnet": ("network", "subnet", "Subnet"),
    "aws_nat_gateway": ("network", "nat", "NAT Gateway"),
    "aws_eip": ("network", "eip", "Elastic IP"),
    "aws_internet_gateway": ("network", "igw", "Internet Gateway"),
    "aws_route_table": ("network", "route_table", "Route Table"),
    "aws_route": ("network", "route", "Route"),
    "aws_network_acl": ("network", "nacl", "Network ACL"),
    "aws_vpc_endpoint": ("network", "vpc_endpoint", "VPC Endpoint"),
    "aws_vpc_peering_connection": ("network", "vpc_peering", "VPC Peering"),
    "aws_transit_gateway": ("network", "tgw", "Transit Gateway"),
    # Load balancing
    "aws_lb": ("network", "alb", "Application Load Balancer"),
    "aws_alb": ("network", "alb", "Application Load Balancer"),
    "aws_alb_listener": ("network", "listener", "ALB Listener"),
    "aws_alb_target_group": ("network", "target_group", "ALB Target Group"),
    "aws_alb_listener_rule": ("network", "listener", "ALB Listener Rule"),
    "aws_alb_target_group_attachment": ("network", "target_group", "ALB Target Group Attachment"),
    "aws_elb": ("network", "elb", "Classic Load Balancer"),
    "aws_lb_target_group": ("network", "target_group", "Target Group"),
    "aws_lb_listener": ("network", "listener", "Listener"),
    "aws_lb_listener_rule": ("network", "listener", "Listener Rule"),
    "aws_lb_target_group_attachment": ("network", "target_group", "Target Group Attachment"),
    # DNS / CDN
    "aws_route53_record": ("dns", "route53", "Route53 Record"),
    "aws_route53_zone": ("dns", "route53", "Route53 Zone"),
    "aws_cloudfront_distribution": ("dns", "cloudfront", "CloudFront Distribution"),
    "aws_cloudfront_origin_access_identity": ("dns", "cloudfront", "OAI"),
    "aws_cloudfront_cache_policy": ("dns", "cloudfront", "Cache Policy"),
    "aws_acm_certificate": ("security", "acm", "ACM Certificate"),
    # Storage
    "aws_s3_bucket": ("storage", "s3", "S3 Bucket"),
    "aws_s3_bucket_policy": ("storage", "s3", "S3 Bucket Policy"),
    "aws_s3_bucket_versioning": ("storage", "s3", "S3 Versioning"),
    "aws_s3_bucket_server_side_encryption_configuration": ("storage", "s3", "S3 Encryption"),
    "aws_ebs_volume": ("storage", "ebs", "EBS Volume"),
    "aws_efs_file_system": ("storage", "efs", "EFS File System"),
    "aws_efs_mount_target": ("storage", "efs", "EFS Mount Target"),
    "aws_elasticache_cluster": ("storage", "elasticache", "ElastiCache Cluster"),
    "aws_dynamodb_table": ("storage", "dynamodb", "DynamoDB Table"),
    # Databases
    "aws_db_instance": ("database", "rds", "RDS Instance"),
    "aws_rds_cluster": ("database", "rds", "RDS Cluster"),
    "aws_rds_cluster_instance": ("database", "rds", "RDS Cluster Instance"),
    "aws_db_subnet_group": ("database", "subnet_group", "DB Subnet Group"),
    "aws_db_parameter_group": ("database", "parameter_group", "DB Parameter Group"),
    "aws_neptune_cluster": ("database", "rds", "Neptune Cluster"),
    "aws_docdb_cluster": ("database", "rds", "DocDB Cluster"),
    # Messaging
    "aws_sqs_queue": ("messaging", "sqs", "SQS Queue"),
    "aws_sns_topic": ("messaging", "sns", "SNS Topic"),
    "aws_sns_topic_subscription": ("messaging", "sns", "SNS Subscription"),
    "aws_kinesis_stream": ("messaging", "kinesis", "Kinesis Stream"),
    "aws_mq_broker": ("messaging", "mq", "Amazon MQ"),
    # Security / IAM
    "aws_iam_role": ("security", "iam", "IAM Role"),
    "aws_iam_policy": ("security", "iam", "IAM Policy"),
    "aws_iam_role_policy": ("security", "iam", "IAM Role Policy"),
    "aws_iam_role_policy_attachment": ("security", "iam", "IAM Attachment"),
    "aws_iam_user": ("security", "iam", "IAM User"),
    "aws_iam_group": ("security", "iam", "IAM Group"),
    "aws_iam_policy_document": ("security", "iam", "IAM Policy Document"),
    "aws_iam_instance_profile": ("security", "iam", "IAM Instance Profile"),
    "aws_iam_openid_connect_provider": ("security", "iam", "IAM OIDC Provider"),
    "aws_security_group": ("security", "security_group", "Security Group"),
    "aws_security_group_rule": ("security", "security_group", "Security Group Rule"),
    "aws_kms_key": ("security", "kms", "KMS Key"),
    "aws_kms_alias": ("security", "kms", "KMS Alias"),
    "aws_wafv2_web_acl": ("security", "waf", "WAF Web ACL"),
    "aws_shield_protection": ("security", "shield", "Shield Protection"),
    # Observability
    "aws_cloudwatch_metric_alarm": ("observability", "cloudwatch", "CloudWatch Alarm"),
    "aws_cloudwatch_log_group": ("observability", "cloudwatch", "CloudWatch Log Group"),
    "aws_cloudwatch_log_stream": ("observability", "cloudwatch", "Log Stream"),
    "aws_cloudwatch_dashboard": ("observability", "cloudwatch", "CloudWatch Dashboard"),
    "aws_prometheus_workspace": ("observability", "prometheus", "AMP Workspace"),
    "aws_grafana_workspace": ("observability", "grafana", "Grafana Workspace"),
    "aws_xray_samling_rule": ("observability", "xray", "X-Ray Sampling Rule"),
    # Backup / DR
    "aws_backup_plan": ("reliability", "backup", "Backup Plan"),
    "aws_backup_vault": ("reliability", "backup", "Backup Vault"),
    "aws_backup_selection": ("reliability", "backup", "Backup Selection"),
    "aws_db_snapshot": ("reliability", "backup", "DB Snapshot"),
    # Cache
    "aws_elasticache_replication_group": ("storage", "elasticache", "ElastiCache Replication"),
    "aws_elasticache_subnet_group": ("storage", "subnet_group", "ElastiCache Subnet Group"),
    # Misc AWS
    "aws_default_vpc": ("network", "vpc", "Default VPC"),
    "aws_default_subnet": ("network", "subnet", "Default Subnet"),
    "aws_availability_zone": ("network", "az", "Availability Zone"),
    "aws_ami": ("compute", "ec2", "AMI"),
    "aws_cloudwatch_event_rule": ("observability", "events", "EventBridge Rule"),
    "aws_stepfunctions_state_machine": ("observability", "step_functions", "Step Functions"),
    "aws_api_gateway_rest_api": ("compute", "apigateway", "API Gateway"),
    "aws_apigatewayv2_api": ("compute", "apigateway", "API Gateway V2"),
    "aws_cognito_user_pool": ("security", "cognito", "Cognito User Pool"),
    "aws_glue_catalog_database": ("data", "glue", "Glue Catalog"),
    "aws_emr_cluster": ("data", "emr", "EMR Cluster"),
    "aws_redshift_cluster": ("database", "redshift", "Redshift Cluster"),
    "aws_sagemaker_notebook_instance": ("data", "sagemaker", "SageMaker Notebook"),
    "aws_elasticsearch_domain": ("database", "elasticsearch", "Elasticsearch Domain"),
    "aws_opensearch_domain": ("database", "opensearch", "OpenSearch Domain"),
    "aws_ses_domain_identity": ("messaging", "ses", "SES Identity"),
    "aws_secretsmanager_secret": ("security", "secrets_manager", "Secrets Manager"),
    "aws_ssm_parameter": ("security", "ssm", "SSM Parameter"),
    "aws_ecr_repository": ("compute", "ecr", "ECR Repository"),
    "aws_ecr_lifecycle_policy": ("compute", "ecr", "ECR Lifecycle Policy"),
}

# Canonical services with their category ordering (used across the app)
SERVICE_CATEGORIES = {
    "compute": "Compute",
    "network": "Networking",
    "storage": "Storage",
    "database": "Databases",
    "messaging": "Messaging",
    "dns": "DNS & CDN",
    "security": "Security & IAM",
    "observability": "Observability",
    "reliability": "Backup & DR",
    "data": "Analytics",
}

DEFAULT_KIND = ("compute", "resource", "Resource")


def classify(resource_type: str) -> ServiceKind:
    """Classify a resource type into a CloudPilot service/kind."""
    for prefix, mapping in sorted(
        _SERVICE_PREFIXES.items(), key=lambda kv: len(kv[0]), reverse=True
    ):
        if resource_type == prefix or resource_type.startswith(prefix + "_"):
            service, kind, label = mapping
            return ServiceKind(service=service, kind=kind, label=label)
    # fall back on provider prefix — do NOT default to "ec2"
    if resource_type.startswith("aws_"):
        return ServiceKind(service="compute", kind="resource", label="AWS Resource")
    return ServiceKind(service="compute", kind="resource", label="Resource")


def known_resource_type(resource_type: str) -> bool:
    """Whether the resource type is understood by the classification table."""
    return resource_type in _SERVICE_PREFIXES


def resource_icon(kind: str) -> str:
    """Return a Lucide-compatible icon name hint for a resource kind."""
    icons = {
        "vpc": "Boxes",
        "subnet": "GitBranch",
        "ec2": "Server",
        "asg": "Layers",
        "ecs": "Container",
        "ecs_service": "Container",
        "ecs_task_definition": "Container",
        "eks": "Boxes",
        "lambda": "Zap",
        "alb": "Split",
        "elb": "Split",
        "nat": "Network",
        "igw": "ArrowLeftRight",
        "eip": "Globe",
        "route_table": "Route",
        "s3": "Archive",
        "ebs": "HardDrive",
        "efs": "FolderOpen",
        "rds": "Database",
        "elasticache": "DatabaseZap",
        "dynamodb": "Database",
        "sqs": "MessageSquare",
        "sns": "Bell",
        "security_group": "Shield",
        "iam": "KeyRound",
        "kms": "Lock",
        "cloudwatch": "Activity",
        "cloudfront": "Globe",
        "route53": "Waypoints",
        "backup": "DatabaseBackup",
        "secrets_manager": "LockKeyhole",
        "waf": "ShieldCheck",
        "subnet_group": "Network",
        "parameter_group": "Settings",
    }
    return icons.get(kind, "Box")
