"""Recommendation + scoring + comparison tests against the sample project."""

from fastapi.testclient import TestClient

from app.services.analysis.demo_data import load_sample_files
from app.services.optimization.engine import optimize
from app.services.pricing.comparison import compare_providers
from app.services.pricing.engine import estimate_all
from app.services.recommendations.engine import run_recommendations
from app.services.scoring.service import compute_scores
from app.services.terraform.parser import parse_terraform_files


def _config():
    return parse_terraform_files(files=load_sample_files(), default_region="us-east-1")


def test_recommendations_fire():
    config = _config()
    recs = run_recommendations(config)
    keys = {r.key for r in recs}
    # The sample config has an open SSH rule and an open DB rule
    assert "sg-open-world" in keys
    assert "nat-consolidation" in keys
    assert "ec2-rightsize" in keys


def test_demo_has_no_duplicate_resource_addresses():
    config = _config()
    addresses = [resource.address for resource in config.resources]
    assert len(addresses) == len(set(addresses))


def test_recommendation_explainability():
    config = _config()
    recs = run_recommendations(config)
    for rec in recs:
        d = rec.to_dict()
        assert d["explanation"]["why"]
        assert d["title"]
        assert d["severity"] in ("critical", "high", "medium", "low")
        assert d["difficulty"] in ("easy", "medium", "hard")
        assert d["risk"] in ("low", "medium", "high")


def test_scores():
    config = _config()
    recs = run_recommendations(config)
    scores = compute_scores(config, recs)
    assert 0 <= scores["overall"] <= 100
    assert len(scores["categories"]) == 8
    assert scores["grade"]


def test_comparison():
    config = _config()
    comparison = compare_providers(config, baseline_provider="aws")
    assert comparison["baseline_provider"] == "aws"
    providers = comparison["providers"]
    assert len(providers) == 10
    cheapest = min(providers, key=lambda p: p.get("estimated_monthly_cost") or float("inf"))
    assert (cheapest.get("estimated_monthly_cost") or 0) > 0
    # AWS should be one of the providers
    assert any(p["provider"] == "aws" for p in providers)


def test_optimization_plan():
    config = _config()
    costs = estimate_all(config.resources)
    current = sum(costs.values())
    recs = run_recommendations(config, mode="lowest-cost")
    plan = optimize(config, recs, current_monthly=current, mode="lowest-cost")
    assert plan.monthly_savings > 0
    assert plan.optimized_monthly < plan.current_monthly
    assert plan.summary["code"]


def test_mode_filtering():
    config = _config()
    enterprise = run_recommendations(config, mode="enterprise")
    cost = run_recommendations(config, mode="lowest-cost")
    # enterprise surfaces security/DR; lowest-cost surfaces cost levers
    assert any(r.category in ("security", "disaster-recovery") for r in enterprise)
    assert any(r.category == "cost" for r in cost)


def test_architecture_graph_structure(client: TestClient):
    """Verify the architecture graph returns structured JSON with no corrupted labels."""
    resp = client.get("/api/v1/demo/analyze")
    assert resp.status_code == 200
    data = resp.json()

    graph = data["graph"]
    assert "nodes" in graph
    assert "edges" in graph
    assert "groups" in graph

    # All nodes must be dicts with required fields
    assert len(graph["nodes"]) > 0
    for node in graph["nodes"]:
        assert isinstance(node, dict)
        assert "id" in node
        assert "label" in node
        assert "displayName" in node
        assert "name" in node
        assert "type" in node
        assert "resourceAddress" in node
        assert "category" in node
        assert "kind" in node
        assert "layer" in node
        assert isinstance(node["label"], str)
        assert isinstance(node["displayName"], str)
        assert isinstance(node["name"], str)
        assert isinstance(node["type"], str)

    # All edges must be dicts with source/target/relationship
    for edge in graph["edges"]:
        assert isinstance(edge, dict)
        assert "source" in edge
        assert "target" in edge
        assert "relationship" in edge
        assert isinstance(edge["relationship"], str)

    # All groups must be dicts
    for group in graph["groups"]:
        assert isinstance(group, dict)
        assert "id" in group
        assert "label" in group

    # No corrupted labels: no $ artifacts anywhere in any string field
    corrupted_patterns = ["$25", "$37", "$9", "$3", "$4", "$17", "$12"]
    for node in graph["nodes"]:
        for field in ["label", "displayName", "name", "type", "resourceAddress"]:
            value = node.get(field, "")
            for pattern in corrupted_patterns:
                assert pattern not in value, (
                    f"Corrupted pattern {pattern!r} found in {field}={value!r}"
                )
        assert "$" not in node["label"], f"Corrupted $ in label: {node['label']!r}"

    # No duplicate node IDs
    node_ids = [n["id"] for n in graph["nodes"]]
    assert len(node_ids) == len(set(node_ids)), (
        f"Duplicate node IDs found: {[nid for nid in node_ids if node_ids.count(nid) > 1]}"
    )

    # Each display name must be a single, standalone label — not concatenated with other labels
    all_display_names = [n["displayName"] for n in graph["nodes"]]
    for dn in all_display_names:
        assert len(dn) < 50, f"Display name too long (possible concatenation): {dn!r}"
        assert "$" not in dn, f"Cost artifact in display name: {dn!r}"

    # Group labels must not contain $ artifacts or concatenated display names
    for group in graph["groups"]:
        assert "$" not in group.get("label", ""), (
            f"Cost artifact in group label: {group['label']!r}"
        )
        assert len(group.get("label", "")) < 80, (
            f"Group label too long (possible concatenation): {group['label']!r}"
        )


def test_cost_reconciliation(client: TestClient):
    """Verify Overview, FinOps, and Cloud Compare all use the same canonical baseline."""
    resp = client.get("/api/v1/demo/analyze")
    assert resp.status_code == 200
    data = resp.json()

    # All three must show the same baseline
    overview_cost = data["costs"]["current_monthly"]
    finops_cost = data["finops"]["current_monthly"]
    comparison_cost = data["comparison"]["baseline_monthly"]

    assert abs(overview_cost - finops_cost) < 0.01, (
        f"Overview ${overview_cost} != FinOps ${finops_cost}"
    )
    assert abs(overview_cost - comparison_cost) < 0.01, (
        f"Overview ${overview_cost} != Comparison ${comparison_cost}"
    )

    # FinOps categories must sum to baseline
    finops_cats = data["finops"]["by_service"]
    finops_sum = round(sum(s["monthly"] for s in finops_cats), 2)
    assert abs(finops_sum - overview_cost) < 0.10, (
        f"FinOps categories sum ${finops_sum} != baseline ${overview_cost}"
    )

    # Cloud Compare AWS breakdown must sum to baseline
    aws_provider = next(
        (p for p in data["comparison"]["providers"] if p["provider"] == "aws"), None
    )
    if aws_provider and aws_provider.get("breakdown"):
        cc_sum = round(sum(aws_provider["breakdown"].values()), 2)
        assert abs(cc_sum - overview_cost) < 0.10, (
            f"Cloud Compare AWS breakdown sum ${cc_sum} != baseline ${overview_cost}"
        )

    # Usage-dependent must NOT be included in baseline
    assert data["costs"]["usage_available"] is False, "Usage should not be included in baseline"
    assert data["costs"]["usage_monthly"] == 0, "No default usage estimates in normal analysis"

    # Known monthly must equal current monthly (canonical model)
    assert abs(data["costs"]["known_monthly"] - data["costs"]["current_monthly"]) < 0.01


def test_score_partial_assessment(client: TestClient):
    """Verify scoring handles partial evidence correctly — no fake overall score."""
    resp = client.get("/api/v1/demo/analyze")
    assert resp.status_code == 200
    data = resp.json()

    scores = data["scores"]

    # Count assessed vs total dimensions
    assessed = sum(1 for c in scores["categories"] if c.get("evidence_status") == "available")
    total = len(scores["categories"])

    # If not all dimensions have evidence, overall must be weighted or N/A
    if assessed < total:
        # Overall should either be null (N/A) or computed only from assessed dims
        if scores["overall"] is not None:
            # If scored, the grade must not imply all dimensions were assessed
            assert scores.get("unassessed_categories") is not None, (
                "unassessed_categories must be present when not all dimensions scored"
            )

    # Every category with insufficient evidence must have score=None
    for c in scores["categories"]:
        if c.get("evidence_status") == "insufficient_evidence":
            assert c["score"] is None, (
                f"Category {c['key']} has insufficient evidence but score={c['score']}"
            )

    # Every category with available evidence must have a numeric score
    for c in scores["categories"]:
        if c.get("evidence_status") == "available":
            assert c["score"] is not None, (
                f"Category {c['key']} has available evidence but score is None"
            )


def test_hcl_s3_encryption_versioning(client: TestClient):
    """Verify S3 encryption + versioning HCL is self-consistent and validates."""
    from app.services.optimization.render import validate_generated_code

    resp = client.get("/api/v1/demo/analyze")
    assert resp.status_code == 200
    data = resp.json()

    # Find S3-related recommendations
    s3_recs = [r for r in data["recommendations"] if "s3" in r.get("key", "").lower()]
    assert len(s3_recs) > 0, "Expected at least one S3 recommendation"

    # Verify each has generated_code with proper bucket reference
    for rec in s3_recs:
        gc = rec.get("generated_code", {})
        assert gc, f"Recommendation {rec['id']} has no generated_code"

        # Extract the HCL block info
        for provider_type, block in gc.items():
            if isinstance(block, dict):
                assert "config" in block, f"Missing config in {provider_type}"
                config = block["config"]
                # Bucket references must use interpolation syntax
                if "bucket" in config:
                    bucket_ref = config["bucket"]
                    assert "aws_s3_bucket." in str(bucket_ref), (
                        f"Bucket reference doesn't use interpolation: {bucket_ref}"
                    )

    # Verify validation returns valid for the generated code
    for rec in s3_recs:
        gc = rec.get("generated_code", {})
        if gc:
            # Transform {provider_type: {name, config}} to [{resource_type, name, config}]
            blocks = [
                {
                    "resource_type": ptype,
                    "name": block.get("name", ""),
                    "config": block.get("config", {}),
                }
                for ptype, block in gc.items()
                if isinstance(block, dict)
            ]
            result = validate_generated_code(blocks)
            assert result["valid"] is True, f"HCL validation failed: {result['errors']}"
            assert result["hcl_syntax_valid"] is True, "HCL syntax validation failed"
            assert result["validation_status"] == "copy_paste_ready", (
                f"Expected copy_paste_ready, got {result['validation_status']}"
            )
