"""Normalize parsed HCL blocks into CloudPilot :class:`Resource` objects.

Responsibilities:

* walk top-level HCL blocks
* extract ``resource``, ``data``, ``variable``, ``output`` and ``module`` blocks
* extract attributes into a flat dict (with sensible defaults per service)
* discover references between resources from attribute raw text
* expand **local** modules recursively (with cycle/double-count protection)
* track **remote** modules (registry/git/github) as first-class entities marked
  ``unexpanded`` — their internals are unknown and must never be invented
* build an adjacency graph for the architecture diagram
"""

from __future__ import annotations

import hashlib
import posixpath
import re
from collections import deque
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
_MODULE_REF_RE = re.compile(r"(?<![\w.])module\.[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_]+)?")

# Maximum recursion depth when expanding nested local modules.
_MAX_MODULE_DEPTH = 8

# Module expansion states.
EXPANDED = "expanded"
PARTIALLY_EXPANDED = "partially_expanded"
UNEXPANDED = "unexpanded"

_EXPANSION_LABELS = {
    EXPANDED: "Expanded",
    PARTIALLY_EXPANDED: "Partially expanded",
    UNEXPANDED: "Not expanded",
}


def classify_module_source(source: str) -> str:
    """Classify a Terraform module ``source`` string.

    Returns one of: ``local``, ``registry``, ``github``, ``git``, ``url``,
    ``unknown``.
    """
    s = (source or "").strip()
    if not s:
        return "unknown"
    if s.startswith(("./", "../", ".\\", "..\\")) or s in (".", ".."):
        return "local"
    head = s.split("/", 1)[0]
    if "::" in head:
        scheme = head.split("::", 1)[0]
        return {"git": "git", "hg": "hg", "s3": "url", "gcs": "url"}.get(scheme, "url")
    if s.startswith("git@") or head == "github.com":
        return "github"
    if head == "bitbucket.org":
        return "git"
    if s.startswith(("http://", "https://")):
        return "github" if "github.com" in head else "url"
    parts = [p for p in s.split("/") if p]
    if len(parts) >= 3:
        # <namespace>/<name>/<provider> (public registry) or
        # <hostname>/<namespace>/<name>/<provider> (private registry)
        return "registry"
    return "unknown"


@dataclass
class Module:
    """A Terraform module declaration tracked as a first-class entity.

    ``expansion`` records what CloudPilot actually inspected:

    * ``expanded`` — module source was available and fully parsed
    * ``partially_expanded`` — some content inspected, but not everything
    * ``unexpanded`` — only the declaration/configuration is known
    """

    address: str
    name: str
    source: str = ""
    version: str = ""
    source_type: str = "unknown"
    configuration: dict = field(default_factory=dict)
    source_file: str = ""
    source_line: int = 0
    expansion: str = UNEXPANDED
    resource_count: int = 0
    data_source_count: int = 0
    child_modules: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def expanded(self) -> bool:
        return self.expansion == EXPANDED

    @property
    def expansion_label(self) -> str:
        return _EXPANSION_LABELS.get(self.expansion, self.expansion)

    @property
    def cost_status(self) -> str:
        """How module costs are reported.

        Expanded modules have their inner resources priced individually.
        Anything else is explicitly *not quantified* — never silently $0.
        """
        if self.expansion == EXPANDED:
            return "priced_via_resources"
        return "not_quantified"

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "name": self.name,
            "source": self.source,
            "version": self.version,
            "source_type": self.source_type,
            "configuration": self.configuration,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "expansion": self.expansion,
            "expansion_label": self.expansion_label,
            "resource_count": self.resource_count,
            "data_source_count": self.data_source_count,
            "child_modules": self.child_modules,
            "references": self.references,
            "note": self.note,
            "cost_status": self.cost_status,
        }


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
    module_address: str = ""
    is_data: bool = False

    @property
    def id(self) -> str:
        """Stable unique id: ``provider_service_kind.hash``."""
        digest = hashlib.md5(
            f"{self.module_address}|{self.resource_type}|{self.name}".encode()
        ).hexdigest()[:8]
        return f"{self.provider}_{self.service}_{digest}"

    @property
    def type_name(self) -> str:
        """Unqualified ``type.name`` (unique only within its module scope)."""
        return f"{self.resource_type}.{self.name}"

    @property
    def address(self) -> str:
        """Canonical Terraform-style address.

        Root resources: ``aws_instance.main`` or ``data.aws_ami.latest``.
        Resources inside modules carry the full module path:
        ``module.network.module.security.aws_security_group.main``.
        """
        if self.is_data:
            base = f"{self.resource_type}.{self.name}"
        else:
            base = self.type_name
        if self.module_address:
            return f"{self.module_address}.{base}"
        return base

    @property
    def source_file(self) -> str:
        """Alias for ``module`` — the .tf file this resource was declared in."""
        return self.module

    @property
    def billable(self) -> bool:
        """Whether this resource represents separately billable infrastructure.

        Data sources, IAM policies, security groups, and other configuration
        objects are not independently billable.
        """
        if self.is_data:
            return False
        _NON_BILLABLE_KINDS = {
            "iam",
            "security_group",
            "route_table",
            "route",
            "nacl",
            "vpc_endpoint",
            "vpc_peering",
            "tgw",
            "igw",
            "listener",
            "target_group",
            "route53",
            "acm",
            "waf",
            "shield",
            "backup",
            "cloudwatch",
            "prometheus",
            "grafana",
            "events",
            "step_functions",
            "ssm",
            "secrets_manager",
            "kms",
            "ecr",
            "cognito",
            "glue",
            "sagemaker",
            "ses",
            "subnet",
            "az",
            "subnet_group",
            "parameter_group",
            "ecs_service",
            "ecs_task_definition",
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
            "module_address": self.module_address,
            "is_data": self.is_data,
            "billable": self.billable,
            "monthly_cost": self.attributes.get("_monthly_cost", 0.0),
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


def extract_module_references(raw_values: list[str]) -> set[str]:
    """Find ``module.<name>`` references (e.g. ``module.vpc.vpc_id``)."""
    found: set[str] = set()
    for raw in raw_values:
        if not raw or "module." not in raw:
            continue
        for match in _MODULE_REF_RE.finditer(raw):
            segments = match.group(0).split(".")
            if len(segments) >= 2:
                found.add(f"module.{segments[1]}")
    return found


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


def _dir_of(path: str) -> str:
    """Directory part of a repo-relative posix path ('' for top-level)."""
    return _normalize_dir(posixpath.dirname(path.replace("\\", "/")))


def _normalize_dir(path: str) -> str:
    """Normalize a repo-relative posix dir path ('' for the root).

    Collapses ``./`` and ``a/b/../c`` segments; clamps escapes above the root.
    """
    p = path.replace("\\", "/")
    p = posixpath.normpath(p)
    while p.startswith("../"):
        p = p[3:]
    if p in (".", ""):
        return ""
    return p


def _join_rel(base: str, rel: str) -> str:
    joined = posixpath.join(base, rel.replace("\\", "/")) if base else rel.replace("\\", "/")
    return _normalize_dir(joined)


class TerraformConfig:
    """Parsed, normalized configuration with a reference graph."""

    def __init__(
        self,
        files: dict[str, str],
        provider: str = "aws",
        default_region: str = "us-east-1",
        strict: bool = False,
    ) -> None:
        self.files = files
        self.provider = provider
        self.default_region = default_region
        self.strict = strict
        self.blocks: list[HCLBlock] = []
        self.resources: list[Resource] = []
        self.variables: dict[str, dict] = {}
        self.modules: list[Module] = []
        self._parsed: dict[str, list[HCLBlock]] = {}
        self._file_module_refs: dict[tuple[str, str], set[str]] = {}
        self._scope_counts: dict[str, list[int]] = {}
        self._parse()

    # ------------------------------------------------------------------ parse
    def _parse(self) -> None:
        for path, content in self.files.items():
            if content and path.endswith((".tf", ".tofu")):
                self._parsed[path] = parse_hcl(content, strict=self.strict)

        assigned = self._plan_scopes()

        # Derive per-scope file lists and module declarations from assignment.
        scope_files: dict[str, list[str]] = {}
        for path in sorted(self._parsed):
            scope_files.setdefault(assigned.get(path, ""), []).append(path)

        module_decls: list[dict] = []
        for path in sorted(self._parsed):
            scope = assigned.get(path, "")
            for block in self._parsed[path]:
                if block.type == "module" and block.labels:
                    src_attr = block.attr("source")
                    source = src_attr.as_string if src_attr else ""
                    module_decls.append(
                        {
                            "scope": scope,
                            "name": block.labels[0],
                            "block": block,
                            "path": path,
                            "source": source,
                            "source_type": classify_module_source(source),
                        }
                    )

        # Resolve local module target dirs (relative to the declaring file's dir).
        for decl in module_decls:
            decl["target"] = None
            if decl["source_type"] == "local":
                base = _dir_of(decl["path"])
                decl["target"] = _join_rel(base, decl["source"])

        # Ingest every scope's files.
        for scope, paths in scope_files.items():
            for path in paths:
                self._ingest_file(path, self._parsed[path], module_address=scope)

        self._finalize_modules(module_decls, assigned)

    def _plan_scopes(self) -> dict[str, str]:
        """Assign every parsed file to a module scope via BFS over local modules.

        Returns ``{path: scope_address}`` where scope ``""`` is the root module.
        Local module directories are claimed exactly once (visited-set), which
        prevents infinite recursion and double-counting of shared modules.
        """
        assigned: dict[str, str] = {}
        visited_dirs: set[str] = set()
        queue: deque[tuple[str, str, int]] = deque([("", "", 0)])

        while queue:
            scope_addr, dir_prefix, depth = queue.popleft()
            for path in sorted(self._parsed):
                if path in assigned:
                    continue
                if _dir_of(path) != dir_prefix:
                    continue
                assigned[path] = scope_addr
            if depth >= _MAX_MODULE_DEPTH:
                continue
            for path in sorted(self._parsed):
                if assigned.get(path) != scope_addr:
                    continue
                for block in self._parsed[path]:
                    if block.type != "module" or not block.labels:
                        continue
                    src_attr = block.attr("source")
                    source = src_attr.as_string if src_attr else ""
                    if classify_module_source(source) != "local":
                        continue
                    target = _join_rel(dir_prefix, source)
                    if target in visited_dirs:
                        # Already claimed by another declaration — do not
                        # re-ingest (prevents cycles and double counting).
                        continue
                    visited_dirs.add(target)
                    child_scope = (
                        f"{scope_addr}.module.{block.labels[0]}"
                        if scope_addr
                        else f"module.{block.labels[0]}"
                    )
                    queue.append((child_scope, target, depth + 1))

        # Files in directories never claimed by a local module remain root
        # scope (backward-compatible with flat uploads).
        for path in self._parsed:
            assigned.setdefault(path, "")
        return assigned

    def _raw_values(self, block: HCLBlock) -> list[str]:
        raw_values = [a.raw for a in block.attributes]
        for child in block.blocks:
            raw_values.extend(a.raw for a in child.attributes)
        return raw_values

    def _ingest_file(self, path: str, blocks: list[HCLBlock], module_address: str = "") -> None:
        counts = self._scope_counts.setdefault(module_address, [0, 0])
        module_refs: set[str] = set()

        for block in blocks:
            block_type = block.type
            raw_values = self._raw_values(block)
            module_refs |= extract_module_references(raw_values)

            if block_type == "resource" and len(block.labels) >= 2:
                resource_type, name = block.labels[0], block.labels[1]
                kind = classify(resource_type)
                provider = provider_of(resource_type)
                refs = extract_references(raw_values)
                res = Resource(
                    resource_type=resource_type,
                    name=name,
                    provider=provider,
                    service=kind.service,
                    kind=kind.kind,
                    label=kind.label,
                    region=_normalize_region(_region_of(block, self.default_region), provider),
                    attributes=_attributes_to_dict(block),
                    references=refs,
                    line=block.line,
                    module=path,
                    module_address=module_address,
                )
                self.resources.append(res)
                self.blocks.append(block)
                counts[0] += 1
                continue

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
                    module_address=module_address,
                    is_data=True,
                )
                self.resources.append(res)
                counts[1] += 1
                continue

            if block_type == "variable":
                if block.labels:
                    self.variables[block.labels[0]] = _attributes_to_dict(block)

        self._file_module_refs[(module_address, path)] = module_refs

    def _finalize_modules(self, decls: list[dict], assigned: dict[str, str]) -> None:
        by_addr: dict[str, Module] = {}

        for decl in decls:
            address = (
                f"{decl['scope']}.module.{decl['name']}"
                if decl["scope"]
                else f"module.{decl['name']}"
            )
            if address in by_addr:
                continue
            block: HCLBlock = decl["block"]
            configuration = _attributes_to_dict(block)
            configuration.pop("source", None)
            configuration.pop("version", None)
            version_attr = block.attr("version")
            module = Module(
                address=address,
                name=decl["name"],
                source=decl["source"],
                version=version_attr.as_string if version_attr else "",
                source_type=decl["source_type"],
                configuration=configuration,
                source_file=decl["path"],
                source_line=block.line,
            )
            counts = self._scope_counts.get(address, [0, 0])
            module.resource_count = counts[0]
            module.data_source_count = counts[1]

            if decl["source_type"] == "local":
                target = decl.get("target")
                scope_files = [p for p, s in assigned.items() if s == address]
                if target is not None and target not in {_dir_of(p) for p in self._parsed}:
                    module.note = (
                        "Local module path not found in the uploaded project; contents unavailable."
                    )
                    module.expansion = UNEXPANDED
                elif not scope_files:
                    module.expansion = PARTIALLY_EXPANDED
                    module.note = (
                        "Local module directory exists but contains no parsable Terraform files."
                    )
                else:
                    module.expansion = EXPANDED
                    module.note = (
                        f"Expanded {module.resource_count} resource(s) and "
                        f"{module.data_source_count} data source(s) from local source."
                    )
            else:
                module.expansion = UNEXPANDED
                module.note = (
                    "Module source not included in upload. Detailed module "
                    "resource analysis unavailable."
                )

            by_addr[address] = module

        # Module-level dependency references (e.g. module.eks -> module.vpc).
        for (_scope, path), refs in self._file_module_refs.items():
            for module in by_addr.values():
                if module.source_file != path:
                    continue
                known = (set(refs) & set(by_addr)) - {module.address}
                module.references = sorted(known)

        # Direct child modules.
        for module in by_addr.values():
            prefix = f"{module.address}.module."
            for other in by_addr.values():
                if other.address.startswith(prefix):
                    remainder = other.address[len(prefix) :]
                    if ".module." not in remainder:
                        module.child_modules.append(other.address)
            module.child_modules.sort()

        self.modules = list(by_addr.values())

    # ------------------------------------------------------------------ graph
    def resolve(self, name: str) -> Resource | None:
        """Resolve a reference (``type.name`` or a full address) to a Resource."""
        for res in self.resources:
            if res.address == name or res.type_name == name:
                return res
        return None

    def adjacency(self) -> dict[str, list[str]]:
        """Build an adjacency list of resource ids."""
        global_by_type: dict[str, Resource] = {}
        scoped_by_type: dict[tuple[str, str], Resource] = {}
        for res in self.resources:
            if res.type_name not in global_by_type:
                global_by_type[res.type_name] = res
            scoped_by_type.setdefault((res.module_address, res.type_name), res)

        adjacency: dict[str, list[str]] = {res.id: [] for res in self.resources}
        for res in self.resources:
            for ref in res.references:
                # Prefer a reference scoped to the same module, fall back to
                # the first global match (root-scope references).
                target = scoped_by_type.get((res.module_address, ref)) or global_by_type.get(ref)
                if target is not None and target.id != res.id:
                    adjacency.setdefault(res.id, []).append(target.id)
        return adjacency

    def module_dependencies(self) -> dict[str, list[str]]:
        """Map each module address to the module addresses it depends on."""
        return {m.address: list(m.references) for m in self.modules}

    def unexpanded_modules(self) -> list[Module]:
        """Modules whose internals CloudPilot has NOT inspected."""
        return [m for m in self.modules if m.expansion != EXPANDED]

    @property
    def has_unexpanded_modules(self) -> bool:
        return any(m.expansion != EXPANDED for m in self.modules)

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
    filtered = {path: content for path, content in files.items() if path.endswith((".tf", ".tofu"))}
    return TerraformConfig(files=filtered, **kwargs)
