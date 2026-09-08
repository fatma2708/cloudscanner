"""Bug-fix regression tests.

BUG 1 — ML classification badge must NOT appear when the analysis provider
is ``none`` (rule-engine only).  The badge is derived from the CRIM risk
intelligence pipeline, but when no LLM is configured the UI header says
"AI Review: none / Provider: Rule engine only" and showing ML badges in
that context is misleading.

BUG 2 — The "Suggested Fix" HCL block shown for a given recommendation
must correspond strictly to the resource mentioned in that recommendation,
not to a concatenation of fixes for other resources.
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

LLM_CONFIG_ERROR = __import__("app.services.llm.router", fromlist=["LLMConfigError"]).LLMConfigError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_review() -> dict:
    """Deterministic review payload that mirrors generate_review output."""
    return {
        "provider": "fake-provider",
        "executive_summary": "Fake summary",
        "architecture_review": "Fake review",
        "top_severities": [],
        "guardrail_applied": True,
    }


@pytest.fixture(scope="module")
def analyze_payload() -> dict:
    """Run the demo analysis once and cache the payload for all tests."""
    from app.services.analysis.demo_data import load_sample_files
    from app.services.analysis.orchestrator import analyze

    with (
        patch(
            "app.services.analysis.orchestrator.generate_review",
            return_value=_fake_review(),
        ),
        patch("app.services.llm.router.get_provider"),
        patch("app.services.llm.service.get_provider"),
    ):
        return analyze(
            files=load_sample_files(),
            mode="balanced",
            provider="aws",
            default_region="us-east-1",
        )


@pytest.fixture(scope="module")
def rule_engine_only_payload() -> dict:
    """Run the demo analysis with NO LLM provider configured.

    Simulates the "AI Review: none / Provider: Rule engine only" state shown
    in the UI when no API key is present. ``get_provider`` raises
    ``LLMConfigError`` in both call sites so the provider name resolves to
    ``none`` and the narrative review falls back to the deterministic path.
    """
    from app.services.analysis.demo_data import load_sample_files
    from app.services.analysis.orchestrator import analyze

    with (
        patch(
            "app.services.llm.router.get_provider",
            side_effect=LLM_CONFIG_ERROR,
        ),
        patch(
            "app.services.llm.service.get_provider",
            side_effect=LLM_CONFIG_ERROR,
        ),
    ):
        return analyze(
            files=load_sample_files(),
            mode="balanced",
            provider="aws",
            default_region="us-east-1",
        )


# ---------------------------------------------------------------------------
# BUG 1 — No ML badge when provider is "rule engine only"
# ---------------------------------------------------------------------------


class TestBug1NoMlBadgeWhenRuleEngineOnly:
    """When provider == 'none', no resource or recommendation must carry
    an ``ml_classification`` value."""

    def test_metadata_reports_rule_engine_only(self, rule_engine_only_payload: dict):
        assert rule_engine_only_payload["analysis_metadata"]["llm_provider"] == "none"
        assert (
            rule_engine_only_payload["analysis_metadata"]["llm_provider_label"]
            == "Rule engine only"
        )

    def test_recommendations_have_no_ml_classification(self, rule_engine_only_payload: dict):
        recs = rule_engine_only_payload["recommendations"]
        assert recs, "Expected at least one recommendation from the demo project"
        for rec in recs:
            assert rec.get("ml_classification") is None, (
                f"Recommendation '{rec['key']}' unexpectedly carries "
                f"ml_classification={rec.get('ml_classification')!r} "
                "when provider is 'none'"
            )

    def test_resources_have_no_ml_classification(self, rule_engine_only_payload: dict):
        resources = rule_engine_only_payload["resources"]
        assert resources, "Expected at least one resource from the demo project"
        for resource in resources:
            assert resource.get("ml_classification") is None, (
                f"Resource '{resource.get('id')}' unexpectedly carries "
                f"ml_classification={resource.get('ml_classification')!r} "
                "when provider is 'none'"
            )


# ---------------------------------------------------------------------------
# BUG 2 — Suggested Fix must be scoped to the issue's resource
# ---------------------------------------------------------------------------


class TestBug2FixScopedToIssueResource:
    """Each recommendation's ``generated_code_hcl`` must reference the
    same Terraform resource that the recommendation targets."""

    @pytest.fixture(scope="class")
    def recs_with_fix(self, analyze_payload: dict) -> list[dict]:
        return [r for r in analyze_payload["recommendations"] if r.get("generated_code_hcl")]

    def test_recs_with_fixes_have_targets(self, recs_with_fix: list[dict]):
        assert recs_with_fix, "Expected at least one recommendation carrying a fix"
        for rec in recs_with_fix:
            assert rec["target"], f"Recommendation '{rec['key']}' has a fix but no targets"

    def test_fix_mentions_target_resource(self, analyze_payload: dict, recs_with_fix: list[dict]):
        """The rendered HCL fix must scope its generated blocks to the same
        service domain as the recommendation's target resource(s).

        This catches the reported aggregation bug where a single issue (e.g. an
        open security group) displayed a fix bloc containing RDS / S3 / EBS /
        ASG blocks — i.e. fixes for completely different resources of the repo.
        Consolidation rules (shared NAT, ASG wrapping) may create a brand-new
        resource, but it must still belong to the same service domain as the
        issue's target resources.
        """
        from app.services.terraform.registry import classify

        id_to_resource = {r["id"]: r for r in analyze_payload["resources"]}
        for rec in recs_with_fix:
            hcl = rec["generated_code_hcl"]
            targets = rec["target"]

            target_resources = [id_to_resource[t] for t in targets if t in id_to_resource]
            assert target_resources, (
                f"Recommendation '{rec['key']}' targets unknown resources {targets}"
            )
            target_services = {r["service"] for r in target_resources}

            fix_block_types = re.findall(r'resource\s+"([^"]+)"', hcl)
            assert fix_block_types, (
                f"Recommendation '{rec['key']}' fix HCL contains no resource blocks:\n{hcl}"
            )

            fix_services = {classify(t).service for t in fix_block_types}
            assert fix_services.issubset(target_services), (
                f"Recommendation '{rec['key']}' fix HCL generates blocks in "
                f"services {fix_services} but the issue targets services "
                f"{target_services} — the fix is not scoped to the issue:\n{hcl}"
            )

    def test_fix_does_not_contain_unrelated_resources(self, analyze_payload: dict):
        """The fix for a security-group issue must restrict the SG rule itself,
        and must not mention RDS/S3/EBS fixes for other resources."""
        from app.services.terraform.registry import classify

        id_to_resource = {r["id"]: r for r in analyze_payload["resources"]}
        sg_recs = [
            r for r in analyze_payload["recommendations"] if "sg-open-world" in r.get("key", "")
        ]
        if not sg_recs:
            return

        a_sg_rec = next((r for r in sg_recs if r.get("generated_code_hcl")), None)
        if a_sg_rec is None:
            return
        hcl = a_sg_rec["generated_code_hcl"]

        unrelated_patterns = [
            "aws_db_instance",
            "aws_s3_bucket",
            "aws_ebs_volume",
            "backup_retention",
            "multi_az",
            "publicly_accessible",
        ]
        for pattern in unrelated_patterns:
            assert pattern not in hcl, (
                f"Security group fix for '{a_sg_rec['key']}' unexpectedly contains "
                f"'{pattern}' — the fix is not scoped to the issue:\n{hcl}"
            )

        # The fix must be a security_group_rule (same domain as the SG target)
        # that restricts the world-open CIDR rather than a broad unrelated block.
        target = a_sg_rec["target"][0]
        target_resource = id_to_resource.get(target, {})
        assert target_resource, (
            f"Security group issue '{a_sg_rec['key']}' targets unknown resource {target}"
        )
        assert classify(target_resource["resource_type"]).service == "security"
        assert "aws_security_group" in hcl, (
            f"Security group fix must mention the security group resource:\n{hcl}"
        )
        assert "0.0.0.0/0" not in hcl, (
            f"Security group fix must NOT keep the world-open CIDR:\n{hcl}"
        )
        assert any(pat in hcl for pat in ("cidr_blocks", "ipv6_cidr_blocks")), (
            f"Security group fix must narrow the CIDR blocks:\n{hcl}"
        )

    def test_each_fix_is_non_empty_when_present(self, recs_with_fix: list[dict]):
        """If a recommendation has generated_code, the HCL must be non-empty."""
        for rec in recs_with_fix:
            assert len(str(rec["generated_code_hcl"]).strip()) > 0, (
                f"Recommendation '{rec['key']}' has generated_code but generated_code_hcl is empty"
            )
