"""CRIM-v4.2 scan-pipeline integration tests.

Verifies that the scan/orchestration pipeline enriches parsed resources with an
advisory ``ml_classification`` block while leaving the deterministic findings
surface (recommendations/rules engine) byte-identical, and that a CRIM failure
never affects scan results.

Scenario coverage:
1. existing scan behavior unchanged (same findings, severities, counts, resources)
2. confident CRIM classification for each of the three classes
3. abstention (category null, abstained true) with findings still present
4. CRIM unavailable -> scan succeeds, findings returned, ML null, no 500
5. multiple findings on the same resource -> one consistent classification
6. no forbidden ML inputs reach the model
"""

from __future__ import annotations

import contextlib

from fastapi.testclient import TestClient

import app.services.risk_intelligence.pipeline as crim_pipeline
from app.services.analysis.demo_data import load_sample_files
from app.services.analysis.orchestrator import analyze
from app.services.recommendations.engine import run_recommendations
from app.services.risk_intelligence.service import RiskIntelligenceService
from app.services.terraform.parser import parse_terraform_files
from tests.fixtures.terraform_fixtures import INSECURE_SG

MODEL_LABEL = "CRIM-v4.2"
THRESHOLD = 0.70


class _FakeProvider:
    """Minimal LLM provider stub: only ``name`` is read by the orchestrator."""

    name = "huggingface"


def _fake_review() -> dict:
    return {
        "provider": "mock",
        "executive_summary": "mock",
        "architecture_review": "mock",
        "top_severities": [],
        "guardrail_applied": True,
    }


@contextlib.contextmanager
def _llm_enabled():
    """Simulate a configured LLM provider so the analysis metadata does NOT
    resolve to 'rule engine only'.

    The CRIM classification block is only surfaced to the API when an LLM
    provider is configured (ml_classification is stripped otherwise), so the
    CRIM pipeline tests enable a provider to exercise the enrichment path.
    """
    from unittest.mock import patch

    with (
        patch(
            "app.services.analysis.orchestrator.generate_review",
            return_value=_fake_review(),
        ),
        patch(
            "app.services.llm.router.get_provider",
            return_value=_FakeProvider(),
        ),
        patch(
            "app.services.llm.service.get_provider",
            return_value=_FakeProvider(),
        ),
    ):
        yield


# Verified against the frozen CRIM-v4.2 model through the exact API feature path.
NET_FILES = {
    "subnetworks.tf": (
        'resource "google_compute_subnetwork" "main" {\n'
        "  project       = var.project_id\n"
        '  name          = "cft-gke-test"\n'
        '  ip_cidr_range = "10.0.0.0/17"\n'
        "  region        = var.region\n"
        "  network       = google_compute_network.main.self_link\n"
        "}\n"
    ),
}

DATA_FILES = {
    "kms.tf": 'resource "aws_kms_key" "this" {\n  description = "fixtures-${random_pet.this.id}"\n}\n'
}

OBS_FILES = {
    "main.tf": 'module "wrapper" {\n  source = "./modules/wrapper"\n}\n',
    "modules/wrapper/main.tf": (
        'resource "aws_s3_bucket" "this" {\n'
        "  count = local.create_bucket && !var.is_directory_bucket ? 1 : 0\n"
        "\n"
        "  region = var.region\n"
        "\n"
        "  bucket           = var.bucket\n"
        "  bucket_prefix    = var.bucket_prefix\n"
        "  bucket_namespace = var.bucket_namespace\n"
        "\n"
        "  force_destroy       = var.force_destroy\n"
        "  object_lock_enabled = var.object_lock_enabled\n"
        "  tags                = var.tags\n"
        "}\n"
        "\n"
    ),
}

ABSTAIN_FILES = {
    "cloudwatch.tf": 'resource "aws_cloudwatch_log_group" "api" {\n  name = "/aws/lambda/api"\n}\n'
}

COMBINED_FILES = {
    "main.tf": INSECURE_SG["main.tf"]
    + '\nresource "aws_cloudwatch_log_group" "api" {\n  name = "/aws/lambda/api"\n}\n'
}

FORBIDDEN_FEATURE_KEYS = {
    "check_id",
    "check_name",
    "rule_id",
    "rule_name",
    "guideline",
    "taxonomy",
    "risk_category",
    "violation",
    "check_result",
    "attributes",
    "fingerprint",
    "repository",
    "file_path",
    "target",
}


def _classify(files: dict[str, str]):
    config = parse_terraform_files(files=files, provider="aws", default_region="us-east-1")
    by_address, summary = crim_pipeline.classify_resources(config)
    return config, by_address, summary


# ---------------------------------------------------------------------------
# Test 1 — existing scan behavior unchanged
# ---------------------------------------------------------------------------


def test_scan_findings_and_resources_contract_unchanged():
    result = analyze(files=INSECURE_SG, provider="aws", default_region="us-east-1")
    config = parse_terraform_files(files=INSECURE_SG, provider="aws", default_region="us-east-1")

    pure = [r.to_dict() for r in run_recommendations(config)]
    stripped_recs = [
        {k: v for k, v in r.items() if k not in ("ml_classification", "generated_code_hcl")}
        for r in result["recommendations"]
    ]
    assert stripped_recs == pure

    by_id = {r["id"]: r for r in result["resources"]}
    assert len(by_id) == len(config.resources)
    for resource in config.resources:
        entry = by_id[resource.id]
        stripped = {k: v for k, v in entry.items() if k != "ml_classification"}
        expected = resource.to_dict()
        for key in stripped:
            if key != "attributes":
                assert stripped[key] == expected[key], f"Field {key} changed on {resource.address}"
        stripped_attrs = {k: v for k, v in stripped["attributes"].items() if not k.startswith("_")}
        expected_attrs = {k: v for k, v in expected["attributes"].items() if not k.startswith("_")}
        assert stripped_attrs == expected_attrs

    expected_top_level = {
        "resources",
        "modules",
        "graph",
        "recommendations",
        "scores",
        "costs",
        "comparison",
        "carbon",
        "finops",
        "optimization",
        "review",
        "ml",
        "crim",
        "analysis_metadata",
        "summary",
    }
    assert set(result) == expected_top_level
    assert "predictions" in result["ml"]
    assert "ml_unavailable" in result["ml"]


# ---------------------------------------------------------------------------
# Test 2 — confident CRIM classification (one case per class)
# ---------------------------------------------------------------------------


class TestConfidentClassification:
    def test_network_security(self):
        config, by_address, summary = _classify(NET_FILES)
        entry = by_address[config.resources[0].address]
        assert entry == {
            "category": "NETWORK_SECURITY",
            "confidence": entry["confidence"],
            "abstained": False,
            "reason": None,
            "model": MODEL_LABEL,
        }
        assert entry["confidence"] >= THRESHOLD
        assert set(entry) == {"category", "confidence", "abstained", "reason", "model"}
        assert summary["classified"] == 1
        assert summary["abstained"] == 0
        assert summary["ml_unavailable"] is False

    def test_data_security(self):
        config, by_address, summary = _classify(DATA_FILES)
        entry = by_address[config.resources[0].address]
        assert entry["category"] == "DATA_SECURITY"
        assert entry["confidence"] >= THRESHOLD
        assert entry["abstained"] is False

    def test_observability(self):
        config, by_address, summary = _classify(OBS_FILES)
        assert config.resources[0].address == "module.wrapper.aws_s3_bucket.this"
        entry = by_address[config.resources[0].address]
        assert entry["category"] == "OBSERVABILITY"
        assert entry["confidence"] >= THRESHOLD
        assert entry["abstained"] is False


# ---------------------------------------------------------------------------
# Test 3 — abstention keeps findings intact
# ---------------------------------------------------------------------------


def test_abstention_keeps_findings():
    with _llm_enabled():
        result = analyze(files=COMBINED_FILES, provider="aws", default_region="us-east-1")

    sg = [r for r in result["recommendations"] if r["key"] == "sg-open-world"]
    assert sg, "Open-world security group finding must still exist"
    assert sg[0]["severity"] in ("critical", "high", "medium", "low")
    assert "ml_classification" in sg[0]

    cloudwatch = next(
        r for r in result["resources"] if r["resource_type"] == "aws_cloudwatch_log_group"
    )
    mc = cloudwatch["ml_classification"]
    assert mc is not None
    assert mc["category"] is None
    assert mc["abstained"] is True
    assert mc["confidence"] < THRESHOLD
    assert mc["model"] == MODEL_LABEL

    sg_rec_mc = sg[0]["ml_classification"]
    assert sg_rec_mc is None or sg_rec_mc["abstained"] is True

    assert result["crim"]["abstained"] >= 1
    assert result["crim"]["ml_unavailable"] is False


# ---------------------------------------------------------------------------
# Test 4 — CRIM unavailable never breaks a scan
# ---------------------------------------------------------------------------


def _fail_crim(monkeypatch):
    def _failing():
        return RiskIntelligenceService(model_path="models/does-not-exist.joblib")

    monkeypatch.setattr(crim_pipeline, "get_risk_intelligence_service", _failing)


def test_crim_unavailable_scan_still_succeeds(monkeypatch):
    _fail_crim(monkeypatch)
    result = analyze(files=INSECURE_SG, provider="aws", default_region="us-east-1")

    assert result["recommendations"], "Findings must still be returned"
    assert result["crim"]["ml_unavailable"] is True
    assert result["crim"]["classified"] == 0
    for resource in result["resources"]:
        assert resource["ml_classification"] is None
    for rec in result["recommendations"]:
        assert rec["ml_classification"] is None
    assert "predictions" in result["ml"]


def test_crim_unavailable_via_demo_endpoint(monkeypatch, client: TestClient):
    _fail_crim(monkeypatch)
    resp = client.get("/api/v1/demo/analyze")
    assert resp.status_code == 200
    data = resp.json()

    assert data["recommendations"], "Findings must still be returned"
    assert data["scores"]["overall"] >= 0
    assert data["crim"]["ml_unavailable"] is True
    assert all(r["ml_classification"] is None for r in data["resources"])


# ---------------------------------------------------------------------------
# Test 5 — multiple findings on one resource share one classification
# ---------------------------------------------------------------------------


def test_multiple_findings_share_consistent_resource_classification():
    result = analyze(files=load_sample_files(), provider="aws", default_region="us-east-1")

    resources = result["resources"]
    ids = [r["id"] for r in resources]
    assert len(ids) == len(set(ids)), "Duplicate resource ids in scan output"

    by_id = {r["id"]: r for r in resources}
    for rec in result["recommendations"]:
        for target in rec["target"]:
            assert target in by_id, f"Finding target {target} missing from scan resources"

    for resource in resources:
        assert "ml_classification" in resource
        mc = resource["ml_classification"]
        assert mc is None or set(mc) == {
            "category",
            "confidence",
            "abstained",
            "reason",
            "model",
        }

    for rec in result["recommendations"]:
        assert "ml_classification" in rec
        rec_mc = rec["ml_classification"]
        if rec_mc is not None:
            first_target_id = rec["target"][0]
            assert rec_mc == by_id[first_target_id]["ml_classification"]

    keys = {r["key"] for r in result["recommendations"]}
    assert {"sg-open-world", "nat-consolidation", "ec2-rightsize"} <= keys
    assert result["crim"]["ml_unavailable"] is False


# ---------------------------------------------------------------------------
# Test 6 — only allowed inputs reach the model
# ---------------------------------------------------------------------------


class _RecordingService:
    name = MODEL_LABEL

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def predict(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {
            "classification": {
                "category": "NETWORK_SECURITY",
                "confidence": 0.9,
                "abstained": False,
                "reason": None,
            },
            "probabilities": {},
            "model": {"name": self.name},
        }


def test_only_allowed_features_reach_model():
    config = parse_terraform_files(files=INSECURE_SG, provider="aws", default_region="us-east-1")
    service = _RecordingService()
    by_address, _summary = crim_pipeline.classify_resources(config, service=service)

    assert service.calls
    assert by_address == {config.resources[0].address: by_address[config.resources[0].address]}
    for call in service.calls:
        assert set(call) == {"resource", "resource_type", "provider", "code_snippet"}
        assert not (set(call) & FORBIDDEN_FEATURE_KEYS)
        address = call["resource"]
        assert call["resource_type"] == address.split(".")[0]
        assert call["provider"] == "aws"
        assert call["code_snippet"] == INSECURE_SG["main.tf"]


def test_computed_resource_type_matches_training_convention():
    config, by_address, _summary = _classify(OBS_FILES)
    assert config.resources[0].address == "module.wrapper.aws_s3_bucket.this"
    assert by_address[config.resources[0].address] is not None


# ---------------------------------------------------------------------------
# Test 7 (H) — determinism: same input + same model → same result
# ---------------------------------------------------------------------------


def test_classification_is_deterministic():
    _, by_a, summary_a = _classify(NET_FILES)
    _, by_b, summary_b = _classify(NET_FILES)
    assert by_a == by_b
    assert summary_a == summary_b
    _, by_c, _ = _classify(DATA_FILES)
    _, by_d, _ = _classify(DATA_FILES)
    assert by_c == by_d


# ---------------------------------------------------------------------------
# Test 8 — checkov isolation: recommendations unchanged before/after CRIM
# ---------------------------------------------------------------------------


def test_checkov_recommendations_unaffected_by_crim(monkeypatch):
    config = parse_terraform_files(files=INSECURE_SG, provider="aws", default_region="us-east-1")
    pure_recs = [r.to_dict() for r in run_recommendations(config)]

    with _llm_enabled():
        result_real = analyze(files=INSECURE_SG, provider="aws", default_region="us-east-1")
    _fail_crim(monkeypatch)
    with _llm_enabled():
        result_unavail = analyze(files=INSECURE_SG, provider="aws", default_region="us-east-1")

    for stripped in (
        [
            {k: v for k, v in r.items() if k not in ("ml_classification", "generated_code_hcl")}
            for r in result_real["recommendations"]
        ],
        [
            {k: v for k, v in r.items() if k not in ("ml_classification", "generated_code_hcl")}
            for r in result_unavail["recommendations"]
        ],
    ):
        assert stripped == pure_recs

    real_mc = [r["ml_classification"] for r in result_real["recommendations"]]
    unavail_mc = [r["ml_classification"] for r in result_unavail["recommendations"]]
    assert unavail_mc == [None] * len(unavail_mc)
    assert any(m is not None for m in real_mc)


# ---------------------------------------------------------------------------
# Test 9 — standalone endpoint is unaffected by the scan pipeline
# ---------------------------------------------------------------------------


def test_standalone_endpoint_uses_own_service(monkeypatch, client: TestClient):
    resp = client.post(
        "/api/v1/risk/classify",
        json={
            "resource": "aws_security_group.open",
            "resource_type": "aws_security_group",
            "provider": "aws",
            "code_snippet": 'resource "aws_security_group" "open" {}\n',
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "classification" in body
    assert body["classification"]["abstained"] in (True, False)
    assert "scan_pipeline" not in body
