"""CRIM-v4.2 advisory classification for the CloudPilot scan pipeline.

``classify_resources`` enriches every parsed Terraform resource with a semantic
``ml_classification`` block (category / confidence / abstained / model) computed
by the shared :class:`RiskIntelligenceService`.

CRIM is advisory only:

* it never decides whether a finding exists; the deterministic rules engine
  (the Checkov-equivalent detection surface) is untouched and passes through
  unchanged
* a model outage or a per-resource prediction failure must never break a scan:
  enrichment is best-effort and every failure is isolated to the affected
  resource, so findings are always returned
* only ``resource``, ``resource_type``, ``provider`` and the raw code snippet
  reach the model; check rule ids, rule names, guideline, taxonomy, repository
  and violation labels are never part of the feature text

Feature conventions mirror ``scripts/crim_v4_2_merge.py`` that built the frozen
training dataset: ``resource`` is the full Terraform address and ``resource_type``
is its first segment (``aws_s3_bucket.this`` -> ``aws_s3_bucket``,
``module.x.aws_s3_bucket.this`` -> ``module``), so inference runs on the same
distribution the model was trained on. ``code_snippet`` is the raw text of the
Terraform file that declared the resource (already parsed — never re-parsed, never
reconstructed) truncated the same way as training.

Data sources are not classified, matching the existing pipeline ML behavior.
"""

from __future__ import annotations

import logging

from app.services.risk_intelligence.service import (
    RiskIntelligenceService,
    RiskIntelligenceUnavailableError,
    get_risk_intelligence_service,
)
from app.services.terraform.parser import Resource, TerraformConfig

logger = logging.getLogger(__name__)

_CODE_SNIPPET_LIMIT = 2000


def _feature_args(resource: Resource, config: TerraformConfig) -> dict[str, str]:
    """Build the only feature inputs CRIM may see for a resource."""
    address = resource.address
    resource_type = address.split(".")[0] if "." in address else address
    return {
        "resource": address,
        "resource_type": resource_type,
        "provider": resource.provider,
        "code_snippet": (config.files.get(resource.module) or "")[:_CODE_SNIPPET_LIMIT],
    }


def _summary(
    settings,
    model_label: str,
    by_address: dict[str, object],
    ml_unavailable: bool,
    classified: int,
    abstained: int,
) -> dict:
    return {
        "name": model_label,
        "version": settings.crim_model_version,
        "threshold": settings.crim_confidence_threshold,
        "ml_unavailable": ml_unavailable,
        "classified": classified if not ml_unavailable else 0,
        "abstained": abstained if not ml_unavailable else 0,
        "unclassified": sum(1 for value in by_address.values() if value is None),
        "resources": len(by_address),
    }


def classify_resources(
    config: TerraformConfig,
    service: RiskIntelligenceService | None = None,
) -> tuple[dict[str, dict | None], dict]:
    """Classify each parsed resource; never raises and never affects findings.

    Returns ``(by_address, summary)`` where ``by_address`` maps every resource
    address to an ``ml_classification`` dict (``None`` when the resource was
    skipped or classification failed) and ``summary`` describes the run.
    """
    from app.core.config import get_settings

    settings = get_settings()
    if service is None:
        service = get_risk_intelligence_service()

    model_label = getattr(service, "name", None) or settings.crim_model_name
    by_address: dict[str, dict | None] = {}
    classified = 0
    abstained = 0
    failures = 0
    attempts = 0

    def _unavailable() -> tuple[dict[str, dict | None], dict]:
        empty = {r.address: None for r in config.resources}
        return empty, _summary(settings, model_label, empty, True, 0, 0)

    try:
        for resource in config.resources:
            if resource.is_data:
                by_address[resource.address] = None
                continue
            attempts += 1
            try:
                result = service.predict(**_feature_args(resource, config))
            except RiskIntelligenceUnavailableError as exc:
                logger.warning(
                    "CRIM semantic classification unavailable; findings unaffected (%s)",
                    type(exc).__name__,
                )
                return _unavailable()
            except Exception as exc:
                failures += 1
                logger.warning(
                    "CRIM prediction failed for %s; classification omitted (%s)",
                    resource.address,
                    type(exc).__name__,
                )
                by_address[resource.address] = None
                continue
            classification = result["classification"]
            by_address[resource.address] = {
                "category": classification["category"],
                "confidence": classification["confidence"],
                "abstained": classification["abstained"],
                "reason": classification["reason"],
                "model": model_label,
            }
            if classification["abstained"]:
                abstained += 1
            else:
                classified += 1
    except Exception as exc:
        logger.warning(
            "CRIM semantic classification unavailable; findings unaffected (%s)",
            type(exc).__name__,
        )
        return _unavailable()

    summary = _summary(settings, model_label, by_address, False, classified, abstained)
    if not summary["ml_unavailable"]:
        logger.info(
            "CRIM scan classification complete model=%s version=%s threshold=%s "
            "attempted=%d classified=%d abstained=%d failed=%d",
            summary["name"],
            summary["version"],
            summary["threshold"],
            attempts,
            classified,
            abstained,
            failures,
        )
    return by_address, summary
