"""Stable numeric features shared by dataset construction, training, and inference.

Feature schema (all values are numeric and deterministic):
- resource_type_hash, provider_hash, service_hash, kind_hash: categorical hashes
  in [0, 1023], avoiding a fitted encoder at production inference time.
- attribute_count: number of top-level Terraform attributes.
- has_*_attribute: 0/1 presence flags for security, backup, logging, and network
  controls, including nested blocks represented by the parser.
- encryption_enabled, public_ip_enabled: 0/1 values when the source value is
  an explicit boolean; otherwise 0.
- ingress_rule_count, ingress_open_to_world: ingress block count and 0/1 if a
  CIDR block contains 0.0.0.0/0 or ::/0.
- has_reference: 0/1 when the resource references another resource.

The hash dimensions and column order are part of FEATURE_SCHEMA_VERSION. Never
change them without retraining the persisted model.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator, Mapping
from typing import Any

logger = logging.getLogger(__name__)
FEATURE_SCHEMA_VERSION = "resource-v2"
_HASH_BUCKETS = 1024

FEATURE_COLUMNS = (
    "resource_type_hash",
    "provider_hash",
    "service_hash",
    "kind_hash",
    "attribute_count",
    "nested_attribute_count",
    "max_nesting_depth",
    "has_encryption_attribute",
    "has_public_ip_attribute",
    "has_ingress_attribute",
    "has_cidr_attribute",
    "has_backup_attribute",
    "has_logging_attribute",
    "encryption_enabled",
    "public_ip_enabled",
    "ingress_rule_count",
    "ingress_open_to_world",
    "has_public_cidr",
    "has_sensitive_port",
    "has_wildcard_permission",
    "has_encryption_configuration",
    "has_versioning_configuration",
    "has_logging_configuration",
    "has_backup_configuration",
    "has_network_exposure",
    "has_reference",
)


def get_attributes(resource: Mapping[str, Any]) -> dict[str, Any]:
    attributes = resource.get("attributes")
    if isinstance(attributes, dict):
        return attributes
    attributes_json = resource.get("attributes_json")
    if attributes_json:
        try:
            parsed = json.loads(attributes_json)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(
                "Unable to decode attributes_json for %s: %s",
                resource.get("resource_type", "unknown"),
                exc,
            )
    return {}


def walk_attributes(value: Any, depth: int = 0) -> Iterator[tuple[Any, int]]:
    yield value, depth
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield key, depth + 1
            yield from walk_attributes(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            yield from walk_attributes(child, depth + 1)


def _hash(value: Any) -> int:
    digest = hashlib.sha256(str(value or "").encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % _HASH_BUCKETS


def _explicit_bool(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return int(value.strip().lower() == "true")
    return 0


def resource_to_features(resource: Any) -> dict[str, float]:
    """Convert a parser Resource or resource-like mapping into FEATURE_COLUMNS."""
    if isinstance(resource, Mapping):
        resource_type = resource.get("resource_type", "")
        provider = resource.get("provider", "")
        service = resource.get("service", "")
        kind = resource.get("kind", "")
        attributes = get_attributes(resource)
        references = resource.get("references", []) or []
    else:
        resource_type = resource.resource_type
        provider = resource.provider
        service = resource.service
        kind = resource.kind
        attributes = resource.attributes or {}
        references = resource.references or []

    names = {str(key).lower() for key in attributes}
    texts = [str(item).lower() for item, _ in walk_attributes(attributes)]
    all_text = " ".join(texts)
    nested_values = list(walk_attributes(attributes))
    ingress = attributes.get("ingress", [])
    if not isinstance(ingress, list):
        ingress = [ingress]
    public_cidr = "0.0.0.0/0" in all_text or "::/0" in all_text
    sensitive_ports = {"22", "23", "3306", "3389", "5432", "6379", "9200", "27017"}
    values = {
        "resource_type_hash": _hash(resource_type),
        "provider_hash": _hash(provider),
        "service_hash": _hash(service),
        "kind_hash": _hash(kind),
        "attribute_count": len(attributes),
        "nested_attribute_count": sum(1 for _, depth in nested_values if depth >= 2),
        "max_nesting_depth": max((depth for _, depth in nested_values), default=0),
        "has_encryption_attribute": int(any("encrypt" in text for text in texts)),
        "has_public_ip_attribute": int(any("public_ip" in text for text in texts)),
        "has_ingress_attribute": int(
            "ingress" in names or any("ingress" in text for text in texts)
        ),
        "has_cidr_attribute": int(any("cidr" in text for text in texts)),
        "has_backup_attribute": int(any("backup" in text or "snapshot" in text for text in texts)),
        "has_logging_attribute": int(any("log" in text for text in texts)),
        "encryption_enabled": _explicit_bool(
            attributes.get("encrypted", attributes.get("encryption"))
        ),
        "public_ip_enabled": _explicit_bool(attributes.get("associate_public_ip_address")),
        "ingress_rule_count": len(ingress),
        "ingress_open_to_world": int(public_cidr),
        "has_public_cidr": int(public_cidr),
        "has_sensitive_port": int(any(text in sensitive_ports for text in texts)),
        "has_wildcard_permission": int(
            ("policy" in names or "permission" in all_text) and "*" in all_text
        ),
        "has_encryption_configuration": int(
            any("encryption_configuration" in text for text in texts)
        ),
        "has_versioning_configuration": int(any("versioning" in text for text in texts)),
        "has_logging_configuration": int(any("logging" in text for text in texts)),
        "has_backup_configuration": int(any("backup" in text for text in texts)),
        "has_network_exposure": int(
            public_cidr or any("public_ip" in text for text in texts) or "ingress" in names
        ),
        "has_reference": int(bool(references)),
    }
    return {column: float(values[column]) for column in FEATURE_COLUMNS}


def rows_to_matrix(rows: list[Mapping[str, Any]]) -> tuple[list[list[float]], list[str]]:
    """Return a matrix and its explicit feature order for training."""
    return [
        [resource_to_features(row)[column] for column in FEATURE_COLUMNS] for row in rows
    ], list(FEATURE_COLUMNS)
