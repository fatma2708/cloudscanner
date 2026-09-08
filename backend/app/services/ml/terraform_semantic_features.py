"""Deterministic semantic tokenization of Terraform resource configuration."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

PORT_NAMES = {
    22: "SSH",
    23: "PRIVILEGED",
    80: "HTTP",
    443: "HTTPS",
    3389: "RDP",
    3306: "DATABASE",
    5432: "DATABASE",
    6379: "DATABASE",
    27017: "DATABASE",
    9200: "DATABASE",
}


def _port(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "OTHER"
    return PORT_NAMES.get(number, "OTHER")


def _cidr(value: str) -> str:
    if value in {"0.0.0.0/0", "::/0"}:
        return "PUBLIC"
    if "/" in value:
        try:
            prefix = int(value.rsplit("/", 1)[1])
            return (
                "PRIVATE"
                if (":" not in value and prefix >= 16) or (":" in value and prefix >= 48)
                else "RESTRICTED"
            )
        except ValueError:
            pass
    return "RESTRICTED"


def semantic_tokens(resource_type: str, attributes_json: Any) -> list[str]:
    """Flatten resource configuration into sorted tokens; no rule metadata is read."""
    if isinstance(attributes_json, str):
        try:
            attributes = json.loads(attributes_json)
        except (json.JSONDecodeError, TypeError):
            attributes = {}
    else:
        attributes = attributes_json if isinstance(attributes_json, dict) else {}
    tokens = [f"RESOURCE_TYPE={resource_type}"]

    def walk(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key in sorted(value, key=str):
                child_path = f"{path}.{key}" if path else str(key)
                tokens.append(f"PATH={child_path}")
                walk(value[key], child_path)
        elif isinstance(value, list):
            for child in value:
                walk(child, path)
        elif isinstance(value, bool):
            tokens.append(f"VALUE_BOOL={path}:{str(value).lower()}")
        elif value is None:
            tokens.append(f"VALUE_NULL={path}")
        elif isinstance(value, (int, float)):
            tokens.append(
                f"VALUE_PORT={path}:{_port(value)}"
                if "port" in path.lower()
                else f"VALUE_NUMBER={path}:{value}"
            )
        elif isinstance(value, str):
            lower = value.lower()
            if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}|[0-9a-f:]+/\d{1,3}", lower):
                tokens.append(f"VALUE_CIDR={path}:{_cidr(lower)}")
            elif "port" in path.lower() and value.isdigit():
                tokens.append(f"VALUE_PORT={path}:{_port(value)}")
            elif value == "*" or "wildcard" in lower:
                tokens.append(f"VALUE_WILDCARD={path}:true")
            elif value:
                tokens.append(f"VALUE_PRESENT={path}:true")

    walk(attributes, "")
    return sorted(tokens)
