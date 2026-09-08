"""CRIM-v4.2 advisory risk classification endpoints.

CRIM is advisory only: Checkov remains the authoritative rule-based detection
engine and is not invoked, modified, or replaced here. When the model is
unavailable the endpoint fails explicitly (HTTP 503) rather than fabricating a
classification; all other backend functionality keeps working.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.risk import (
    RiskClassification,
    RiskClassificationRequest,
    RiskClassificationResponse,
    RiskModelInfo,
)
from app.services.risk_intelligence.service import (
    RiskIntelligenceError,
    RiskIntelligenceService,
    get_risk_intelligence_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()

Service = Annotated[RiskIntelligenceService, Depends(get_risk_intelligence_service)]


@router.post(
    "/classify",
    response_model=RiskClassificationResponse,
    summary="Classify a Terraform resource with the CRIM-v4.2 advisory model",
    description=(
        "Advisory ML classification of a single Terraform resource block. "
        "Confidence below the configured threshold returns an abstention "
        "(category null, abstained true). CRIM does not replace Checkov."
    ),
)
def classify(payload: RiskClassificationRequest, service: Service) -> RiskClassificationResponse:
    """Return a CRIM-v4.2 classification (advisory, may abstain)."""
    try:
        result = service.predict(
            resource=payload.resource,
            resource_type=payload.resource_type,
            provider=payload.provider,
            code_snippet=payload.code_snippet,
        )
    except RiskIntelligenceError as exc:
        logger.warning("CRIM-v4.2 classification unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CRIM-v4.2 advisory classification service is currently unavailable.",
        ) from exc
    classification = result["classification"]
    return RiskClassificationResponse(
        classification=RiskClassification(**classification),
        probabilities=result["probabilities"],
        model=RiskModelInfo(**result["model"]),
    )
