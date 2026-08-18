"""Normalize parsed HCL blocks into CloudPilot :class:`Resource` objects.

Responsibilities:

* walk top-level HCL blocks
* extract ``resource`` and ``data`` blocks with their labels
* extract attributes into a flat dict (with sensible defaults per service)
* discover references between resources from attribute raw text
* build an adjacency graph for the architecture diagram
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.terraform.hcl import HCLBlock, parse_hcl
from app.services.terraform.registry import classify, provider_of

_REFERENCE_RE = re.compile(
    r"(?<![\w.])"
    r"(?P<provider>aws|azurerm|google|digitalocean|hcloud|scaleway|ovh|oci|vultr|"
    r"linode|cloudflare|kubernetes|openstack)_[a-z0-9_]+"
    r"\.[a-zA-Z0-9_-]+"
    r"(?:\.[a-zA-Z0-9_]+)?"
)
_DATA_REF_RE = re.compile(r"data\.[a-z0-9_]+\.[a-zA-Z0-9_-]+")


@dataclass
class Resource:
    """A single normalized infrastructure resource."""

    resource_type: str
    name: str
    provider: str
    service: str
    kind: str
    label: str
    region: str = "global"
    attributes: dict = field(default_factory=dict)
    references: list[str] = field(default_factory=list)
    line: int = 0
    module: str = ""
    is_data: bool = False

    @property
    def id(self) -> str:
        """Stable unique id: ``provider_service_kind.hash``."""
        import hashlib

        digest = hashlib.md5(f"{self.resource_type}.{self.name}".encode()).hexdigest()[:8]
        return f"{self.provider}_{self.service}_{digest}"

    @property
    def address(self) -> str:
        """Terraform-style address: ``aws_instance.main`` or ``data.aws_ami.latest``."""
        if self.is_data:
            return f"data.{self.resource_type}.{self.name}"
        return f"{self.resource_type}.{self.name}"

    @property
    def source_file(self) -> str:
        """Alias for ``module`` — the .tf file this resource was declared in."""
        return self.module

    @property
    def type_name(self) -> str:
        return f"{self.resource_type}.{self.name}"

    @property
    def billable(self) -> bool:
        """Whether this resource represents separately billable infrastructure.

        Data sources, IAM policies, security groups, and other configuration
        objects are not independently billable.
        """
        if self.is_data:
            return False
        _NON_BILLABLE_KINDS = {
            "iam", "security_group", "route_table", "route", "nacl",
            "vpc_endpoint", "vpc_peering", "tgw", "igw", "listener",
            "target_group", "route53", "acm", "waf", "shield",
            "backup", "cloudwatch", "prometheus", "grafana", "events",
            "step_functions", "ssm", "secrets_manager", "kms",
            "ecr", "cognito", "glue", "sagemaker", "ses",
            "subnet", "az", "subnet_group", "parameter_group",
            "ecs_service", "ecs_task_definition",
            "resource",  # unknown resources
        }
        return self.kind not in _NON_BILLABLE_KINDS

    def attr(self, key: str, default=None):
        return self.attributes.get(key, default)

    def attr_any(self, *keys: str, default=None):
        for key in keys:
            if key in self.attributes:
                return self.attributes[key]
        return default

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "resource_type": self.resource_type,
            "name": self.name,
            "address": self.address,
            "provider": self.provider,
            "service": self.service,
            "kind": self.kind,
            "label": self.label,
            "region": self.region,
            "attributes": self.attributes,
            "references": self.references,
            "line": self.line,
            "source_file": self.source_file,
            "source_line": self.line,
            "module": self.module,
            "is_data": self.is_data,
            "billable": self.billable,
            "monthly_cost": 0.0,
        }


def _region_of(block: HCLBlock, default: str) -> str:
    attr = block.attr("region") or block.attr("availability_zone")
    if attr is not None and isinstance(attr.value, str) and attr.value:
        if attr.key == "availability_zone":
            # us-east-1a -> us-east-1
            parts = attr.value.rsplit("-", 1)
            return parts[0] if len(parts) == 2 else attr.value
        return attr.value
    return default


_LIST_LIKE_BLOCKS = {
    "ingress",
    "egress",
    "logging",
    "lifecycle",
    "provisioner",
    "dynamic",
    "health_check",
}


def _attributes_to_dict(block: HCLBlock) -> dict:
    """Flatten attributes, converting nested blocks like ``ingress`` on a SG."""
    out: dict = {}
    for a in block.attributes:
        if isinstance(a.value, list) and a.value and all(isinstance(x, dict) for x in a.value):
            out[a.key] = a.value
        elif isinstance(a.value, dict) and a.value:
            if a.key == "tags":
                out["tags"] = a.value
            else:
                out[a.key] = a.value
        else:
            out[a.key] = a.value
    for child in block.blocks:
        # HCL blocks map to either repeatable lists (ingress, egress, ...) or
        # object-style attributes (instance_market_options, root_block_device).
        attrs = {a.key: a.value for a in child.attributes}
        if child.type in _LIST_LIKE_BLOCKS:
            out.setdefault(child.type, []).append(attrs)
        else:
            if child.type in out:
                if isinstance(out[child.type], list):
                    out[child.type].append(attrs)
                else:
                    out[child.type] = [out[child.type], attrs]
            else:
                out[child.type] = attrs
    return out


def extract_references(raw_values: list[str]) -> list[str]:
    """Find resource references inside raw attribute text."""
    found: set[str] = set()
    for raw in raw_values:
        if not raw:
            continue
        for match in _REFERENCE_RE.finditer(raw):
            ref = match.group(0)
            segments = ref.split(".")
            if len(segments) >= 2:
                # normalize aws_instance.foo.id -> aws_instance.foo
                found.add(f"{segments[0]}.{segments[1]}")
        for match in _DATA_REF_RE.finditer(raw):
            segments = match.group(0).split(".")
            if len(segments) >= 3:
                found.add(f"{segments[1]}.{segments[2]}")
    return sorted(found)


def _normalize_region(region: str, provider: str) -> str:
    if region and region != "global":
        return region
    defaults = {
        "aws": "us-east-1",
        "azurerm": "East US",
        "google": "us-central1",
        "digitalocean": "nyc1",
        "hcloud": "fsn1",
        "scaleway": "fr-par",
        "ovh": "GRA9",
        "oci": "us-ashburn-1",
        "vultr": "ewr",
        "linode": "us-east",
    }
    return defaults.get(provider, "global")


class TerraformConfig:
    """Parsed, normalized configuration with a reference graph."""

    def __init__(
        self,
        files: dict[str, str],
        provider: str = "aws",
        default_region: str = "us-east-1",
    ) -> None:
        self.files = files
        self.provider = provider
        self.default_region = default_region
        self.blocks: list[HCLBlock] = []
        self.resources: list[Resource] = []
        self.variables: dict[str, dict] = {}
        self.modules: list[dict] = []
        self._parse()

    def _parse(self) -> None:
        for path, content in self.files.items():
            if not content:
                continue
            blocks = parse_hcl(content)
            for block in blocks:
                self._ingest_block(block, path)

    def _ingest_block(self, block: HCLBlock, path: str) -> None:
        block_type = block.type

        if block_type == "resource" and len(block.labels) >= 2:
            resource_type, name = block.labels[0], block.labels[1]
            kind = classify(resource_type)
            provider = provider_of(resource_type)
            attrs = _attributes_to_dict(block)
            raw_values = [a.raw for a in block.attributes]
            for child in block.blocks:
                raw_values.extend(a.raw for a in child.attributes)
            refs = extract_references(raw_values)
            res = Resource(
                resource_type=resource_type,
                name=name,
                provider=provider,
                service=kind.service,
                kind=kind.kind,
                label=kind.label,
                region=_normalize_region(_region_of(block, self.default_region), provider),
                attributes=attrs,
                references=refs,
                line=block.line,
                module=path,
            )
            self.resources.append(res)
            self.blocks.append(block)
            return

        if block_type == "data" and len(block.labels) >= 2:
            kind = classify(block.labels[0])
            provider = provider_of(block.labels[0])
            res = Resource(
                resource_type=f"data.{block.labels[0]}",
                name=block.labels[1],
                provider=provider,
                service=kind.service,
                kind=kind.kind,
                label=f"Data: {kind.label}",
                region=_normalize_region(_region_of(block, self.default_region), provider),
                attributes=_attributes_to_dict(block),
                line=block.line,
                module=path,
                is_data=True,
            )
            self.resources.append(res)
            return

        if block_type == "variable":
            if block.labels:
                self.variables[block.labels[0]] = _attributes_to_dict(block)
            return

        if block_type == "module":
            if block.labels:
                self.modules.append(
                    {
                        "name": block.labels[0],
                        "source": (block.attr("source").as_string if block.attr("source") else ""),
                    }
                )

    # ------------------------------------------------------------------ graph
    def resolve(self, name: str) -> Resource | None:
        """Resolve a ``type.name`` reference to a Resource, if present."""
        for res in self.resources:
            if res.type_name == name or res.resource_id == name:
                return res
        return None

    def adjacency(self) -> dict[str, list[str]]:
        """Build an adjacency list of resource ids."""
        by_type_name: dict[str, Resource] = {
            res.type_name: res for res in self.resources if not res.is_data
        }
        adjacency: dict[str, list[str]] = {res.id: [] for res in self.resources}
        for res in self.resources:
            for ref in res.references:
                target = by_type_name.get(ref)
                if target is not None and target.id != res.id:
                    adjacency.setdefault(res.id, []).append(target.id)
        return adjacency

    def graph_edges(self) -> list[dict]:
        """Return edges as ``{source, target}`` dicts for the diagram generator."""
        adjacency = self.adjacency()
        edges: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for source, targets in adjacency.items():
            for target in targets:
                if (source, target) in seen or (target, source) in seen:
                    continue
                seen.add((source, target))
                edges.append({"source": source, "target": target})
        return edges


def parse_terraform_files(files: dict[str, str], **kwargs) -> TerraformConfig:
    """Convenience constructor that only ingests ``*.tf`` files."""
    filtered = {path: content for path, content in files.items() if path.endswith(".tf")}
    return TerraformConfig(files=filtered, **kwargs)
