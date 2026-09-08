"""Optional local ML enrichment for rule-based analysis."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib

from app.services.ml.features import FEATURE_COLUMNS, resource_to_features

MODEL_PATH = Path(__file__).resolve().parents[1] / "models_ml" / "model.joblib"
logger = logging.getLogger(__name__)


def predict(resource_features: Any, model_path: Path = MODEL_PATH) -> dict[str, Any]:
    """Return category scores and top contributing features; never raises for ML failures."""
    try:
        bundle = joblib.load(model_path)
        if bundle.get("schema_version") != "resource-v2" or bundle.get("columns") != list(
            FEATURE_COLUMNS
        ):
            logger.warning("ML model schema is incompatible; retrain before ML inference")
            return {"scores": {}, "explanations": {}, "ml_unavailable": True}
        features = resource_to_features(resource_features)
        vector = [[features[column] for column in FEATURE_COLUMNS]]
        scores: dict[str, float] = {}
        factors: dict[str, list[dict[str, float]]] = {}
        for category, entry in bundle["models"].items():
            model = entry["model"]
            scores[category] = float(model.predict_proba(vector)[0][1])
            importances = getattr(model, "feature_importances_", [0.0] * len(FEATURE_COLUMNS))
            ranked = sorted(
                zip(FEATURE_COLUMNS, importances, strict=False),
                key=lambda item: item[1],
                reverse=True,
            )[:5]
            factors[category] = [
                {"feature": name, "contribution": float(value)} for name, value in ranked
            ]
        return {"scores": scores, "explanations": factors, "ml_unavailable": False}
    except Exception:
        return {"scores": {}, "explanations": {}, "ml_unavailable": True}
