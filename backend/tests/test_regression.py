"""Regression and integration tests using representative Terraform fixtures.

Tests the full pipeline: parse -> cost -> recommend -> score.

Key principle: PRECISION > RECALL. We test that we do NOT produce false positives
as much as we test that we DO catch real issues.
"""

from __future__ import annotations

from app.services.architecture.service import build_graph
from app.services.pricing.engine import estimate_all
from app.services.recommendations.engine import run_recommendations
from app.services.scoring.service import compute_scores
from app.services.terraform.parser import parse_terraform_files
from tests.fixtures.terraform_fixtures import (
    ALB_NO_HC,
    ALB_WITH_HC,
    DATA_SOURCES_ONLY,
    EC2_WITH_ASG,
    ECS_ONLY,
    INSECURE_S3,
    INSECURE_SG,
    SECURE_S3,
    STANDALONE_EC2,
)


def _config_from_fixture(fixture: dict[str, str]) -> object:
    """Parse a fixture dict directly (filename -> content mapping)."""
    return parse_terraform_files(fixture)


# ---------------------------------------------------------------------------
# ECS-only: no EC2 false positives
# ---------------------------------------------------------------------------

class TestECSOnlyNoFalsePositives:
    """ECS Fargate architecture should not trigger EC2/ASG/ALB health check findings."""

    def test_no_asg_recommendation(self):
        config = _config_from_fixture(ECS_ONLY)
        recs = run_recommendations(config)
        asg_recs = [r for r in recs if "autoscal" in r.title.lower() or "auto scaling" in r.title.lower()]
        assert len(asg_recs) == 0, f"False positive ASG recommendation: {[r.title for r in asg_recs]}"

    def test_no_single_instance_recommendation(self):
        config = _config_from_fixture(ECS_ONLY)
        recs = run_recommendations(config)
        single_recs = [r for r in recs if "single instance" in r.title.lower()]
        assert len(single_recs) == 0, f"False positive single instance: {[r.title for r in single_recs]}"

    def test_s3_encryption_not_flagged(self):
        config = _config_from_fixture(ECS_ONLY)
        recs = run_recommendations(config)
        s3_enc = [r for r in recs if r.key == "s3-encryption"]
        assert len(s3_enc) == 0, f"False positive S3 encryption: {[r.title for r in s3_enc]}"

    def test_s3_versioning_not_flagged(self):
        config = _config_from_fixture(ECS_ONLY)
        recs = run_recommendations(config)
        s3_ver = [r for r in recs if r.key == "s3-versioning"]
        assert len(s3_ver) == 0, f"False positive S3 versioning: {[r.title for r in s3_ver]}"

    def test_no_pricing_for_data_sources(self):
        config = _config_from_fixture(ECS_ONLY)
        costs = estimate_all(config.resources)
        for res in config.resources:
            if res.is_data:
                assert res.id not in costs, f"Data source {res.id} in cost estimates"

    def test_rec_has_confidence_field(self):
        config = _config_from_fixture(ECS_ONLY)
        recs = run_recommendations(config)
        for rec in recs:
            assert hasattr(rec, "confidence"), f"Recommendation {rec.key} missing confidence"
            assert rec.confidence in ("high", "medium", "low", "unknown"), f"Invalid confidence: {rec.confidence}"

    def test_rec_has_evidence_field(self):
        config = _config_from_fixture(ECS_ONLY)
        recs = run_recommendations(config)
        for rec in recs:
            assert hasattr(rec, "evidence"), f"Recommendation {rec.key} missing evidence"
            assert isinstance(rec.evidence, list), f"evidence should be list: {type(rec.evidence)}"

    def test_architecture_graph_has_nodes(self):
        config = _config_from_fixture(ECS_ONLY)
        graph = build_graph(config)
        assert len(graph["nodes"]) > 0, "Architecture graph has no nodes"
        assert len(graph["edges"]) > 0, "Architecture graph has no edges"


# ---------------------------------------------------------------------------
# S3 security checks
# ---------------------------------------------------------------------------

class TestS3SecurityChecks:

    def test_secure_s3_no_findings(self):
        config = _config_from_fixture(SECURE_S3)
        recs = run_recommendations(config)
        s3_recs = [r for r in recs if r.key in ("s3-encryption", "s3-versioning")]
        assert len(s3_recs) == 0, f"False positive on secure S3: {[r.title for r in s3_recs]}"

    def test_insecure_s3_flags_both(self):
        config = _config_from_fixture(INSECURE_S3)
        recs = run_recommendations(config)
        s3_enc = [r for r in recs if r.key == "s3-encryption"]
        s3_ver = [r for r in recs if r.key == "s3-versioning"]
        assert len(s3_enc) == 1, f"Expected 1 encryption finding, got {len(s3_enc)}"
        assert len(s3_ver) == 1, f"Expected 1 versioning finding, got {len(s3_ver)}"
        assert s3_enc[0].confidence == "high"


# ---------------------------------------------------------------------------
# Security group checks
# ---------------------------------------------------------------------------

class TestSecurityGroupChecks:

    def test_open_sg_flagged(self):
        config = _config_from_fixture(INSECURE_SG)
        recs = run_recommendations(config)
        sg_recs = [r for r in recs if "security group" in r.title.lower()]
        assert len(sg_recs) >= 1, "Open security group not detected"


# ---------------------------------------------------------------------------
# Data sources only
# ---------------------------------------------------------------------------

class TestDataSourcesOnly:

    def test_no_recommendations_for_data_only(self):
        config = _config_from_fixture(DATA_SOURCES_ONLY)
        for res in config.resources:
            assert res.is_data, f"Resource {res.id} should be data source"
        costs = estimate_all(config.resources)
        assert len(costs) == 0, f"Unexpected costs for data sources: {costs}"


# ---------------------------------------------------------------------------
# EC2 / ASG combinations
# ---------------------------------------------------------------------------

class TestEC2ASGCombinations:

    def test_standalone_ec2_gets_asg_rec(self):
        config = _config_from_fixture(STANDALONE_EC2)
        recs = run_recommendations(config)
        asg_recs = [r for r in recs if "autoscal" in r.title.lower() or "auto scaling" in r.title.lower()]
        assert len(asg_recs) >= 1, "Standalone EC2 should get ASG recommendation"

    def test_ec2_with_asg_no_asg_rec(self):
        config = _config_from_fixture(EC2_WITH_ASG)
        recs = run_recommendations(config)
        asg_recs = [r for r in recs if "autoscal" in r.title.lower() or "auto scaling" in r.title.lower()]
        assert len(asg_recs) == 0, f"False positive ASG rec: {[r.title for r in asg_recs]}"


# ---------------------------------------------------------------------------
# ALB health check combinations
# ---------------------------------------------------------------------------

class TestALBHealthCheck:

    def test_alb_with_hc_no_finding(self):
        config = _config_from_fixture(ALB_WITH_HC)
        recs = run_recommendations(config)
        hc_recs = [r for r in recs if "health check" in r.title.lower()]
        assert len(hc_recs) == 0, f"False positive health check: {[r.title for r in hc_recs]}"

    def test_alb_without_hc_gets_finding(self):
        config = _config_from_fixture(ALB_NO_HC)
        recs = run_recommendations(config)
        hc_recs = [r for r in recs if "health check" in r.title.lower()]
        assert len(hc_recs) >= 1, "ALB without health check should get finding"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class TestScoring:

    def test_ecs_architecture_high_score(self):
        config = _config_from_fixture(ECS_ONLY)
        recs = run_recommendations(config)
        scores = compute_scores(config, recs)
        assert scores["overall"] >= 65, f"ECS architecture score too low: {scores['overall']}"
        assert scores["grade"] in ("A+", "A", "A-", "B+", "B", "B-", "C+", "C"), f"Grade too low: {scores['grade']}"

    def test_scores_have_deductions(self):
        config = _config_from_fixture(ECS_ONLY)
        recs = run_recommendations(config)
        scores = compute_scores(config, recs)
        for cat in scores["categories"]:
            assert "deductions" in cat, f"Category {cat['key']} missing deductions"
            assert isinstance(cat["deductions"], (int, float)), "Invalid deductions type"
