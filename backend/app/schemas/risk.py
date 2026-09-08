"""CRIM-v4.2 risk classification API schemas.

The ML layer is advisory: the category is never forced below the configured
confidence threshold, and clients cannot influence which model is loaded.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.risk_intelligence.service import (
    ABSTENTION_REASON,
    EXPECTED_CLASSES,
)

RiskCategory = Literal["NETWORK_SECURITY", "DATA_SECURITY", "OBSERVABILITY"]

MAX_RESOURCE_LENGTH = 512
MAX_RESOURCE_TYPE_LENGTH = 200
MAX_PROVIDER_LENGTH = 64
MAX_CODE_SNIPPET_LENGTH = 200_000


class RiskClassificationRequest(BaseModel):
    """Input accepted by ``POST /risk/classify``.

    Only fields that were part of the validated CRIM-v4.2 inference feature
    representation are accepted. Checkov rule id/name, guideline, taxonomy,
    repository, labels and model paths are rejected.
    """

    model_config = ConfigDict(extra="forbid")

    resource: str = Field(
        min_length=1,
        max_length=MAX_RESOURCE_LENGTH,
        description="Terraform resource identifier/address, e.g. aws_security_group.web",
    )
    resource_type: str = Field(
        default="",
        max_length=MAX_RESOURCE_TYPE_LENGTH,
        description="Terraform resource type, e.g. aws_security_group",
    )
    provider: str = Field(
        default="",
        max_length=MAX_PROVIDER_LENGTH,
        description="Provider, e.g. aws, azurerm, google",
    )
    code_snippet: str = Field(
        min_length=1,
        max_length=MAX_CODE_SNIPPET_LENGTH,
        description="Terraform resource block (HCL) to classify",
    )


class RiskClassification(BaseModel):
    category: RiskCategory | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    abstained: bool = False
    reason: str | None = None


class RiskModelInfo(BaseModel):
    name: str
    version: str
    threshold: float


class RiskClassificationResponse(BaseModel):
    classification: RiskClassification
    probabilities: dict[RiskCategory, float] = Field(
        default_factory=dict,
        description="Class probabilities (advisory signal, rounded for serialization).",
    )
    model: RiskModelInfo


__all__ = [
    "ABSTENTION_REASON",
    "EXPECTED_CLASSES",
    "RiskCategory",
    "RiskClassificationRequest",
    "RiskClassification",
    "RiskModelInfo",
    "RiskClassificationResponse",
]
