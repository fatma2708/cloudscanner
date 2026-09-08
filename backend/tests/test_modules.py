"""First-class Terraform module support.

Covers: module block parsing (source/version/config/location), local module
recursion with canonical addresses and cycle protection, registry modules
marked unexpanded, module references/dependencies, counting separation,
scoring scope honesty, recommendation suppression, and architecture graph
module nodes.
"""

from __future__ import annotations

from app.services.analysis.orchestrator import analyze
from app.services.architecture.service import build_graph
from app.services.recommendations.engine import run_recommendations
from app.services.scoring.service import compute_scores
from app.services.terraform.parser import parse_terraform_files

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BENCHMARK_FILES = {
    "main.tf": """
terraform {
  required_providers {
    aws = { source = "hashicorp/aws" }
  }
}

data "aws_availability_zones" "available" { state = "available" }

resource "random_string" "suffix" { length = 8 special = false }

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.7.0"
  name    = "my-vpc"
  cidr    = "10.0.0.0/16"
  private_subnets    = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets     = ["10.0.101.0/24"]
  enable_nat_gateway = true
  single_nat_gateway = true
}

module "eks" {
  source       = "terraform-aws-modules/eks/aws"
  version      = "20.8.4"
  cluster_name = "my-cluster"
  vpc_id       = module.vpc.vpc_id
  subnet_ids   = module.vpc.private_subnets
}
""",
}

NESTED_LOCAL_FILES = {
    "main.tf": """
module "network" {
  source = "./modules/network"
}
""",
    "modules/network/main.tf": """
module "security" {
  source = "./modules/security"
}
resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }
output "vpc_id" { value = aws_vpc.main.id }
""",
    "modules/network/modules/security/main.tf": """
resource "aws_security_group" "main" { vpc_id = var.vpc_id }
""",
}


def test_module_blocks_are_parsed_with_source_version_and_location():
    cfg = parse_terraform_files(files=BENCHMARK_FILES)
    assert len(cfg.modules) == 2

    by_addr = {m.address: m for m in cfg.modules}
    vpc = by_addr["module.vpc"]
    eks = by_addr["module.eks"]

    assert vpc.source == "terraform-aws-modules/vpc/aws"
    assert vpc.version == "5.7.0"
    assert vpc.source_type == "registry"
    assert vpc.source_file == "main.tf"
    assert vpc.source_line > 0
    # Known configuration is preserved; source/version are not duplicated.
    assert vpc.configuration.get("enable_nat_gateway") is True
    assert vpc.configuration.get("cidr") == "10.0.0.0/16"
    assert "source" not in vpc.configuration
    assert "version" not in vpc.configuration

    assert eks.version == "20.8.4"


def test_registry_modules_are_unexpanded_and_not_counted_as_resources():
    cfg = parse_terraform_files(files=BENCHMARK_FILES)

    # Only the root resources/data sources are resources — never module blocks.
    non_data = [r for r in cfg.resources if not r.is_data]
    data = [r for r in cfg.resources if r.is_data]
    assert [r.address for r in non_data] == ["random_string.suffix"]
    assert [r.address for r in data] == ["data.aws_availability_zones.available"]

    unexpanded = cfg.unexpanded_modules()
    assert {m.address for m in unexpanded} == {"module.vpc", "module.eks"}
    for m in unexpanded:
        assert m.expansion == "unexpanded"
        assert m.resource_count == 0
        assert "not included in upload" in m.note.lower()
        d = m.to_dict()
        assert d["cost_status"] == "not_quantified"


def test_local_modules_are_expanded_recursively_with_canonical_addresses():
    cfg = parse_terraform_files(files=NESTED_LOCAL_FILES)
    addresses = sorted(r.address for r in cfg.resources)

    assert "module.network.aws_vpc.main" in addresses
    assert "module.network.module.security.aws_security_group.main" in addresses

    by_addr = {m.address: m for m in cfg.modules}
    network = by_addr["module.network"]
    security = by_addr["module.network.module.security"]

    assert network.expansion == "expanded"
    assert security.expansion == "expanded"
    assert network.resource_count == 1  # aws_vpc.main
    assert security.resource_count == 1  # aws_security_group.main
    assert network.child_modules == ["module.network.module.security"]

    # No double counting: each resource appears exactly once.
    ids = [r.id for r in cfg.resources]
    assert len(ids) == len(set(ids))


def test_cyclic_local_modules_do_not_recurse_forever_or_double_count():
    files = {
        "main.tf": 'module "a" { source = "./mod_a" }',
        "mod_a/main.tf": 'module "b" { source = ".." }',
    }
    cfg = parse_terraform_files(files=files)  # must terminate
    assert len(cfg.modules) >= 1


def test_missing_local_path_is_reported_unexpanded():
    files = {"main.tf": 'module "ghost" { source = "./does/not/exist" }'}
    cfg = parse_terraform_files(files=files)
    ghost = cfg.modules[0]
    assert ghost.expansion == "unexpanded"
    assert "not found" in ghost.note.lower()


def test_module_references_and_dependency_graph():
    cfg = parse_terraform_files(files=BENCHMARK_FILES)
    deps = cfg.module_dependencies()
    assert deps["module.eks"] == ["module.vpc"]
    assert deps["module.vpc"] == []


def test_scoring_marks_root_configuration_only_scope():
    cfg = parse_terraform_files(files=BENCHMARK_FILES)
    recs = run_recommendations(cfg)
    scores = compute_scores(cfg, recs)

    assert scores["scope"] == "root_configuration_only"
    assert scores["scope_label"] == "Root configuration only"
    assert set(scores["modules_unexpanded"]) == {"module.vpc", "module.eks"}
    # Unexpanded modules must drag evidence coverage down from a perfect score.
    assert scores["evidence_coverage_pct"] < 100.0
    assert any("not expanded" in note.lower() for note in scores["coverage_notes"])

    dims = {d["name"]: d for d in scores["evidence_dimensions"]}
    assert dims["Module declarations"]["status"] == "available"
    assert dims["Module contents"]["status"] == "unavailable"

    # A near-perfect score must be impossible when most infra is uninspected.
    if scores["overall"] is not None:
        assert scores["overall"] <= 79.9


def test_scoring_full_scope_when_no_modules():
    files = {
        "main.tf": """
resource "aws_instance" "web" {
  instance_type = "t3.micro"
  root_block_device { volume_size = 20 encrypted = true }
}
""",
    }
    cfg = parse_terraform_files(files=files)
    recs = run_recommendations(cfg)
    scores = compute_scores(cfg, recs)
    assert scores["scope"] == "complete_configuration"
    assert scores["scope_label"] == "Full configuration"
    assert scores["modules_unexpanded"] == []


def test_absence_based_rules_are_suppressed_for_unexpanded_modules():
    files = {
        "main.tf": """
resource "aws_instance" "web" { instance_type = "t3.micro" }
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.8.4"
}
""",
    }
    cfg = parse_terraform_files(files=files)
    keys = {r.key for r in run_recommendations(cfg)}
    # Without modules this config would trigger cw-alarms ("no alarms found").
    # The EKS module may declare them — absence cannot be claimed.
    assert "cw-alarms" not in keys
    assert "no-dns" not in keys


def test_architecture_graph_represents_modules_explicitly():
    cfg = parse_terraform_files(files=BENCHMARK_FILES)
    graph = build_graph(cfg)

    module_nodes = [n for n in graph["nodes"] if n.get("is_module")]
    assert {n["resourceAddress"] for n in module_nodes} == {"module.vpc", "module.eks"}

    for node in module_nodes:
        assert node["expansion"] == "unexpanded"
        assert node["metrics"]["cost_status"] == "not_quantified"
        assert node["status"] == "unexpanded"

    # Module dependency edge eks -> vpc exists between module nodes.
    ids = {n["id"] for n in module_nodes}
    pairs = {(e["source"], e["target"]) for e in graph["edges"]}
    eks_id = next(n["id"] for n in module_nodes if n["resourceAddress"] == "module.eks")
    vpc_id = next(n["id"] for n in module_nodes if n["resourceAddress"] == "module.vpc")
    assert (eks_id, vpc_id) in pairs
    assert ids == {eks_id, vpc_id}


def test_architecture_graph_links_expanded_module_hub_to_children():
    cfg = parse_terraform_files(files=NESTED_LOCAL_FILES)
    graph = build_graph(cfg)

    hub = next(n for n in graph["nodes"] if n["resourceAddress"] == "module.network")
    child = next(n for n in graph["nodes"] if n["resourceAddress"].endswith("aws_vpc.main"))
    pairs = {(e["source"], e["target"]) for e in graph["edges"]}
    assert (hub["id"], child["id"]) in pairs


def test_orchestrator_reports_separate_counts_and_unquantified_costs():
    result = analyze(files=dict(BENCHMARK_FILES), mode="balanced")

    summary = result["summary"]
    assert summary["resource_count"] == 1
    assert summary["data_source_count"] == 1
    assert summary["module_count"] == 2
    assert summary["unexpanded_module_count"] == 2
    assert summary["total_block_count"] == 4
    assert summary["scope_label"] == "Root configuration only"

    # Modules exposed as first-class payloads.
    assert len(result["modules"]) == 2
    assert all(m["expansion"] == "unexpanded" for m in result["modules"])

    # Costs of unexpanded modules are explicitly not quantified — never $0.
    unquantified = result["costs"]["modules_unquantified"]
    assert {u["address"] for u in unquantified} == {"module.vpc", "module.eks"}
    assert all("not available" in u["reason"].lower() for u in unquantified)


def test_resource_to_dict_includes_module_address():
    cfg = parse_terraform_files(files=NESTED_LOCAL_FILES)
    sg = next(r for r in cfg.resources if r.kind == "security_group")
    d = sg.to_dict()
    assert d["module_address"] == "module.network.module.security"
    assert d["address"] == "module.network.module.security.aws_security_group.main"
