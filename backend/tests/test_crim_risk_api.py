"""CRIM-v4.2 risk classification integration tests.

Covers model loading, three-class classification, abstention, validation,
security, determinism, API schema, service-unavailable behavior, and metadata.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.risk_intelligence.service import (
    ABSTENTION_REASON,
    EXPECTED_CLASSES,
    RiskIntelligenceService,
    RiskIntelligenceUnavailableError,
    build_feature_text,
)

# ---------------------------------------------------------------------------
# Fixtures: representative Terraform resources verified against the frozen
# CRIM-v4.2 model using the exact API feature construction path (no file_path).
# ---------------------------------------------------------------------------

NET_SUBNETWORK = {
    "resource": "google_compute_subnetwork.main",
    "resource_type": "google_compute_subnetwork",
    "provider": "GCP",
    "code_snippet": (
        'resource "google_compute_subnetwork" "main" {\n'
        "  project       = var.project_id\n"
        '  name          = "cft-gke-test"\n'
        '  ip_cidr_range = "10.0.0.0/17"\n'
        "  region        = var.region\n"
        "  network       = google_compute_network.main.self_link\n"
        "}"
    ),
}

DATA_KMS = {
    "resource": "aws_kms_key.this",
    "resource_type": "aws_kms_key",
    "provider": "AWS",
    "code_snippet": 'resource "aws_kms_key" "this" {\n  description = "fixtures-${random_pet.this.id}"\n}\n',
}

OBS_S3_BUCKET = {
    "resource": "module.wrapper.aws_s3_bucket.this",
    "resource_type": "module",
    "provider": "AWS",
    "code_snippet": (
        'resource "aws_s3_bucket" "this" {\n'
        "  count   = 1\n"
        "  region  = var.region\n"
        "  bucket  = var.bucket\n"
        "  tags    = var.tags\n"
        "}"
    ),
}

LOW_CONF_ABSTAIN = {
    "resource": "aws_cloudwatch_log_group.api",
    "resource_type": "aws_cloudwatch_log_group",
    "provider": "AWS",
    "code_snippet": 'resource "aws_cloudwatch_log_group" "api" {\n  name = "/aws/lambda/api"\n}\n',
}

HIGH_CONF_NET = NET_SUBNETWORK
EXPECTED_CLASSES_SORTED = sorted(EXPECTED_CLASSES)

# ---------------------------------------------------------------------------
# Unit: model loading
# ---------------------------------------------------------------------------


class TestModelLoading:
    def test_model_loads_successfully(self):
        svc = RiskIntelligenceService(
            model_path="models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib",
            confidence_threshold=0.70,
        )
        model = svc.ensure_loaded()
        assert model is not None

    def test_expected_classes_are_present(self):
        svc = RiskIntelligenceService(
            model_path="models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib",
        )
        svc.ensure_loaded()
        assert svc.classes == EXPECTED_CLASSES_SORTED

    def test_invalid_model_path_fails_clearly(self):
        svc = RiskIntelligenceService(model_path="models/does-not-exist.joblib")
        with pytest.raises(RiskIntelligenceUnavailableError):
            svc.ensure_loaded()
        # predict also raises
        with pytest.raises(RiskIntelligenceUnavailableError):
            svc.predict("res", "rt", "prov", "code")

    def test_model_is_not_reloaded_per_request(self):
        svc = RiskIntelligenceService(
            model_path="models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib",
        )
        assert svc.load_count == 0
        svc.ensure_loaded()
        assert svc.load_count == 1
        svc.predict("res", "rt", "prov", "code")
        svc.predict("res", "rt", "prov", "code")
        assert svc.load_count == 1  # singleton, not reloaded


# ---------------------------------------------------------------------------
# Unit: classification (one representative case per class)
# ---------------------------------------------------------------------------


class TestClassification:
    def test_network_security(self):
        result = RiskIntelligenceService(
            model_path="models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib",
            confidence_threshold=0.0,
        ).predict(**NET_SUBNETWORK)
        cls = result["classification"]
        assert cls["category"] in EXPECTED_CLASSES_SORTED
        assert 0.0 <= cls["confidence"] <= 1.0
        assert isinstance(result["probabilities"], dict)
        assert set(result["probabilities"].keys()) == set(EXPECTED_CLASSES)

    def test_data_security(self):
        result = RiskIntelligenceService(
            model_path="models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib",
            confidence_threshold=0.0,
        ).predict(**DATA_KMS)
        cls = result["classification"]
        assert cls["category"] in EXPECTED_CLASSES_SORTED
        assert 0.0 <= cls["confidence"] <= 1.0

    def test_observability(self):
        result = RiskIntelligenceService(
            model_path="models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib",
            confidence_threshold=0.0,
        ).predict(**OBS_S3_BUCKET)
        cls = result["classification"]
        assert cls["category"] in EXPECTED_CLASSES_SORTED
        assert 0.0 <= cls["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Unit: abstention
# ---------------------------------------------------------------------------


class TestAbstention:
    def test_low_confidence_abstains(self):
        result = RiskIntelligenceService(
            model_path="models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib",
            confidence_threshold=0.99,  # force abstention
        ).predict(**NET_SUBNETWORK)
        cls = result["classification"]
        assert cls["category"] is None
        assert cls["abstained"] is True
        assert cls["reason"] == ABSTENTION_REASON

    def test_high_confidence_does_not_abstain(self):
        result = RiskIntelligenceService(
            model_path="models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib",
            confidence_threshold=0.50,
        ).predict(**NET_SUBNETWORK)
        cls = result["classification"]
        assert cls["abstained"] is False
        assert cls["reason"] is None


# ---------------------------------------------------------------------------
# Unit: validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_empty_request_rejected(self, client: TestClient):
        resp = client.post("/api/v1/risk/classify", json={})
        assert resp.status_code == 422

    def test_missing_required_fields_rejected(self, client: TestClient):
        resp = client.post("/api/v1/risk/classify", json={"provider": "aws"})
        assert resp.status_code == 422

    def test_malformed_payload_rejected(self, client: TestClient):
        resp = client.post(
            "/api/v1/risk/classify",
            json={"resource": "", "code_snippet": "x"},
        )
        assert resp.status_code == 422

    def test_extra_fields_rejected(self, client: TestClient):
        resp = client.post(
            "/api/v1/risk/classify",
            json={
                "resource": "r",
                "code_snippet": "c",
                "model_path": "/etc/evil",
                "check_id": "CKV_AWS_1",
                "risk_category": "DATA_SECURITY",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Unit: security — no client-controlled model paths
# ---------------------------------------------------------------------------


class TestSecurity:
    def test_client_cannot_specify_model_path(self, client: TestClient):
        for field in ("model_path", "model", "path", "artifact"):
            resp = client.post(
                "/api/v1/risk/classify",
                json={
                    "resource": "r",
                    "code_snippet": "c",
                    field: "/etc/passwd",
                },
            )
            # Forbidden field → 422, never 200
            assert resp.status_code == 422, f"{field} should be rejected"

    def test_endpoint_metadata_exposes_no_filesystem_path(self, client: TestClient):
        resp = client.post("/api/v1/risk/classify", json=NET_SUBNETWORK)
        assert resp.status_code == 200
        body = resp.json()
        for key in ("path", "model_path", "model_path_absolute", "filesystem_path"):
            assert key not in body, f"Internal key {key!r} should not be exposed"


# ---------------------------------------------------------------------------
# Unit: determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_input_produces_same_classification(self):
        svc = RiskIntelligenceService(
            model_path="models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib",
        )
        first = svc.predict(**NET_SUBNETWORK)
        second = svc.predict(**NET_SUBNETWORK)
        assert first == second

    def test_feature_text_is_deterministic(self):
        t1 = build_feature_text("r", "rt", "p", "c")
        t2 = build_feature_text("r", "rt", "p", "c")
        assert t1 == t2


# ---------------------------------------------------------------------------
# API-level tests
# ---------------------------------------------------------------------------


class TestAPI:
    def test_post_risk_classify_success(self, client: TestClient):
        resp = client.post("/api/v1/risk/classify", json=NET_SUBNETWORK)
        assert resp.status_code == 200
        body = resp.json()

        # classification
        cls = body["classification"]
        assert cls["category"] in EXPECTED_CLASSES_SORTED
        assert 0.0 <= cls["confidence"] <= 1.0
        assert isinstance(cls["abstained"], bool)

        # model metadata
        model = body["model"]
        assert model["name"] == "CRIM-v4.2"
        assert model["version"] == "v4.2"
        assert model["threshold"] == 0.7

        # probabilities
        probs = body["probabilities"]
        assert set(probs.keys()) == set(EXPECTED_CLASSES)
        assert 0.0 <= sum(probs.values()) <= 1.5  # allow rounding

    def test_post_risk_classify_abstention(self, client: TestClient):
        """The high-confidence NET subnetwork should be non-abstained with default 0.7."""
        resp = client.post("/api/v1/risk/classify", json=HIGH_CONF_NET)
        assert resp.status_code == 200
        body = resp.json()
        cls = body["classification"]
        assert cls["abstained"] is False
        assert cls["category"] == "NETWORK_SECURITY"
        assert cls["confidence"] >= 0.70

    def test_post_risk_classify_service_unavailable(self, client: TestClient):
        """Override the dependency with a failing model → 503, no stack trace."""
        import app.api.v1.risk as risk_module
        from app.main import app

        original = risk_module.get_risk_intelligence_service

        def _failing():
            return RiskIntelligenceService(model_path="models/does-not-exist.joblib")

        app.dependency_overrides[original] = _failing
        try:
            resp = client.post("/api/v1/risk/classify", json=NET_SUBNETWORK)
            assert resp.status_code == 503
            body = resp.json()
            assert "detail" in body
            assert "CRIM" in body["detail"] or "unavailable" in body["detail"].lower()
        finally:
            app.dependency_overrides.pop(original, None)


# ---------------------------------------------------------------------------
# Unit: metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_metadata_contains_expected_keys(self):
        svc = RiskIntelligenceService(
            model_path="models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib",
        )
        svc.ensure_loaded()
        meta = svc.metadata()
        assert set(meta.keys()) == {
            "name",
            "version",
            "threshold",
            "classes",
            "model_type",
            "sklearn_version",
            "python_version",
        }
        assert meta["name"] == "CRIM-v4.2"
        assert meta["classes"] == EXPECTED_CLASSES_SORTED

    def test_metadata_exposes_no_filesystem_path(self):
        svc = RiskIntelligenceService(
            model_path="models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib",
        )
        svc.ensure_loaded()
        meta = svc.metadata()
        for key in meta:
            assert "path" not in key.lower(), (
                f"Metadata key {key!r} should not expose filesystem info"
            )


# ---------------------------------------------------------------------------
# Checkov isolation — CRIM integration does not break existing functionality
# ---------------------------------------------------------------------------


class TestCheckovIsolation:
    def test_health_endpoint_still_works(self, client: TestClient):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_demo_endpoint_still_works(self, client: TestClient):
        resp = client.get("/api/v1/demo/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scores"]["overall"] > 0
