"""CRIM-v4.2 advisory ML classification service.

The model artifact is ``models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib``,
a joblib bundle containing a scikit-learn ``Pipeline`` (word TF-IDF + Logistic
Regression) whose ``model`` entry exposes ``predict``/``predict_proba``.

Responsibilities:

* load the trusted artifact exactly once (thread-safe lazy loading)
* validate the expected prediction interface and the exact CRIM-v4.2 class set
* build inference text using the same non-leakage feature path used in training
* abstain below the configured confidence threshold instead of forcing a class

CRIM is advisory only: it never modifies Checkov behavior or findings.
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Expected classes from the validated CRIM-v4.2 dataset/model.
EXPECTED_CLASSES = frozenset({"NETWORK_SECURITY", "DATA_SECURITY", "OBSERVABILITY"})

ABSTENTION_REASON = "ML classification uncertain"


class RiskIntelligenceError(RuntimeError):
    """Base error for the CRIM service."""


class RiskIntelligenceUnavailableError(RiskIntelligenceError):
    """The model artifact is missing, corrupt, or incompatible."""


class RiskIntelligencePredictionError(RiskIntelligenceError):
    """The model failed while producing a prediction."""


def build_feature_text(
    resource: str,
    resource_type: str,
    provider: str,
    code_snippet: str,
) -> str:
    """Build the exact non-leakage inference text used during CRIM-v4.2 training.

    Mirrors ``make_text`` in ``scripts/crim_v4_2_train.py`` and the validated
    ``feature_text`` builder: resource + resource_type + provider + file_path +
    code_snippet. ``file_path`` is intentionally empty because the API does not
    accept repository-derived provenance, matching the validated input schema.

    Forbidden training signals (checkov rule id/name, guideline, taxonomy,
    repository, target label) never reach the model.
    """
    return " ".join(
        [
            str(resource or ""),
            str(resource_type or ""),
            str(provider or ""),
            "",
            str(code_snippet or ""),
        ]
    )


class RiskIntelligenceService:
    """Thread-safe, load-once wrapper around the frozen CRIM-v4.2 pipeline."""

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float | None = None,
        name: str = "CRIM-v4.2",
        version: str = "v4.2",
        expected_classes: frozenset[str] = EXPECTED_CLASSES,
    ) -> None:
        self.model_path = Path(model_path)
        self.threshold = 0.70 if confidence_threshold is None else float(confidence_threshold)
        self.name = name
        self.version = version
        self._expected_classes = frozenset(expected_classes)
        self._model: Any = None
        self._model_version: str | None = None
        self._lock = threading.RLock()
        self._load_count = 0

    # ------------------------------------------------------------------
    # Loading / validation
    # ------------------------------------------------------------------
    def ensure_loaded(self) -> Any:
        """Load and validate the model once; return the pipeline.

        Raises :class:`RiskIntelligenceUnavailableError` if the artifact is
        missing, corrupt, or incompatible so callers fail clearly instead of
        pretending ML classification works.
        """
        with self._lock:
            if self._model is None:
                self._model = self._load_and_validate()
                self._load_count += 1
                logger.info(
                    "CRIM-v4.2 model loaded: version=%s classes=%s model_type=%s sklearn=%s python=%s",
                    self.version,
                    sorted(self._model.classes_),
                    self.model_type,
                    self.sklearn_version,
                    self.python_version,
                )
            return self._model

    def _load_and_validate(self) -> Any:
        import joblib

        path = self.model_path
        if not Path(path).exists():
            raise RiskIntelligenceUnavailableError(
                "CRIM model artifact not found at configured path"
            )
        try:
            bundle = joblib.load(path)
        except Exception as exc:
            raise RiskIntelligenceUnavailableError(
                "CRIM model artifact could not be loaded"
            ) from exc

        model = bundle.get("model") if isinstance(bundle, dict) else bundle
        if model is None or not callable(getattr(model, "predict", None)):
            raise RiskIntelligenceUnavailableError(
                "CRIM model does not expose the expected predict interface"
            )
        if not callable(getattr(model, "predict_proba", None)):
            raise RiskIntelligenceUnavailableError("CRIM model does not expose predict_proba")

        classes_raw = getattr(model, "classes_", None)
        classes = list(classes_raw) if classes_raw is not None else []
        if set(classes) != self._expected_classes:
            raise RiskIntelligenceUnavailableError(
                "CRIM model classes do not match the expected CRIM-v4.2 classes"
            )

        self._model_version = str(getattr(bundle, "get", lambda _k, d=None: d)("version", "") or "")
        return model

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    @property
    def load_count(self) -> int:
        """Number of times the artifact was (re)loaded from disk."""
        with self._lock:
            return self._load_count

    @property
    def model_type(self) -> str:
        model = self._model
        if model is None:
            return "not_loaded"
        steps = getattr(model, "steps", None)
        if steps:
            return "pipeline:" + "+".join(name for name, _ in steps)
        return type(model).__name__

    @property
    def sklearn_version(self) -> str:
        import sklearn

        return str(sklearn.__version__)

    @property
    def python_version(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    @property
    def classes(self) -> list[str]:
        model = self._model
        if model is None:
            return sorted(self._expected_classes)
        return sorted(model.classes_)

    def metadata(self) -> dict[str, Any]:
        """Runtime metadata (no internal filesystem paths)."""
        return {
            "name": self.name,
            "version": self.version,
            "threshold": self.threshold,
            "classes": self.classes,
            "model_type": self.model_type,
            "sklearn_version": self.sklearn_version,
            "python_version": self.python_version,
        }

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def predict(
        self,
        resource: str,
        resource_type: str,
        provider: str,
        code_snippet: str,
    ) -> dict[str, Any]:
        """Classify a resource; abstain below the confidence threshold.

        Returns a plain dict compatible with the API response schema:
        ``classification``, ``probabilities`` and ``model`` blocks.
        """
        import pandas as pd

        model = self.ensure_loaded()
        text = build_feature_text(resource, resource_type, provider, code_snippet)
        try:
            proba = model.predict_proba(pd.Series([text]))[0]
        except Exception as exc:
            raise RiskIntelligencePredictionError("CRIM prediction failed") from exc
        proba = [float(p) for p in proba]
        classes = list(model.classes_)
        confidence = max(proba)
        best_index = proba.index(confidence)
        abstained = confidence < self.threshold

        classification = {
            "category": classes[best_index] if not abstained else None,
            "confidence": round(confidence, 4),
            "abstained": abstained,
            "reason": ABSTENTION_REASON if abstained else None,
        }
        probabilities = {name: round(p, 4) for name, p in zip(classes, proba, strict=False)}
        return {
            "classification": classification,
            "probabilities": probabilities,
            "model": {
                "name": self.name,
                "version": self.version,
                "threshold": self.threshold,
            },
        }


# ----------------------------------------------------------------------
# Process-wide singleton (load once per configuration)
# ----------------------------------------------------------------------
_service_cache: dict[tuple[str, float], RiskIntelligenceService] = {}
_service_lock = threading.Lock()


def get_risk_intelligence_service() -> RiskIntelligenceService:
    """Return a cached, configured CRIM service instance.

    The model path and threshold come from application settings only — never
    from request input.
    """
    from app.core.config import get_settings

    settings = get_settings()
    key = (settings.crim_model_path, settings.crim_confidence_threshold)
    with _service_lock:
        service = _service_cache.get(key)
        if service is None:
            service = RiskIntelligenceService(
                model_path=settings.crim_model_path,
                confidence_threshold=settings.crim_confidence_threshold,
                name=settings.crim_model_name,
                version=settings.crim_model_version,
            )
            _service_cache[key] = service
        return service
