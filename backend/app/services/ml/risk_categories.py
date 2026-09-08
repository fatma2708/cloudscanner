"""Deterministic Checkov rule-semantic taxonomy for CRIM labels."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)
FINAL_CATEGORIES = (
    "NETWORK_EXPOSURE",
    "ACCESS_CONTROL",
    "ENCRYPTION",
    "DATA_PROTECTION",
    "OTHER_SECURITY",
)

_RULE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "NETWORK_EXPOSURE",
        (
            "network",
            "public",
            "unrestrict",
            "ingress",
            "egress",
            "cidr",
            "firewall",
            "securitygroup",
            "security_group",
            "networkacl",
            "securitylist",
            "internet",
            "expos",
            "port",
            "accessible",
            "external",
            "webacl",
            "subnet",
            "ip",
        ),
    ),
    ("ENCRYPTION", ("encrypt", "encryption", "cmk", "kms", "ssl", "tls", "securetransport")),
    (
        "ACCESS_CONTROL",
        (
            "iam",
            "permission",
            "policy",
            "role",
            "principal",
            "password",
            "auth",
            "credential",
            "oidc",
            "privilege",
            "access",
            "admin",
            "wildcard",
        ),
    ),
    (
        "DATA_PROTECTION",
        ("data", "database", "storage", "bucket", "secret", "retention", "versioning"),
    ),
    (
        "OTHER_SECURITY",
        (
            "log",
            "audit",
            "monitor",
            "trace",
            "metric",
            "debug",
            "backup",
            "snapshot",
            "recovery",
            "restore",
            "redundan",
            "failover",
            "replica",
        ),
    ),
)


def map_rule_metadata(metadata: Mapping[str, Any]) -> dict[str, str]:
    """Map rule metadata only; Terraform configuration and labels are forbidden inputs."""
    rule_text = " ".join(
        str(metadata.get(key, ""))
        for key in ("rule_id", "rule_name", "check_description", "check_category")
    ).lower()
    matches = [
        (category, keyword)
        for category, keywords in _RULE_KEYWORDS
        for keyword in keywords
        if keyword in rule_text
    ]
    categories = {category for category, _ in matches}
    if len(categories) == 1:
        category = next(iter(categories))
        keyword = next(keyword for candidate, keyword in matches if candidate == category)
        return {
            "category": category,
            "reason": f"rule metadata contains semantic keyword '{keyword}'",
        }
    if len(categories) > 1:
        logger.warning(
            "Ambiguous risk rule metadata: %s",
            metadata.get("rule_name", metadata.get("rule_id", "unknown")),
        )
        return {
            "category": "OTHER_SECURITY",
            "reason": "ambiguous rule metadata matched multiple semantic categories; assigned OTHER_SECURITY",
        }
    logger.warning(
        "Unmapped risk rule metadata: %s",
        metadata.get("rule_name", metadata.get("rule_id", "unknown")),
    )
    return {
        "category": "OTHER_SECURITY",
        "reason": "no specific semantic rule keyword; assigned OTHER_SECURITY",
    }
