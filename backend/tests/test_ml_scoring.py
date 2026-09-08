from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier

from app.services.ml.features import FEATURE_COLUMNS, resource_to_features
from app.services.ml_scoring import predict


def test_ml_scoring_returns_scores_and_explanations(tmp_path: Path):
    rows = [
        {
            "resource_type": "aws_s3_bucket",
            "provider": "aws",
            "service": "storage",
            "kind": "s3",
            "attributes": {"encrypted": False},
        },
        {
            "resource_type": "aws_s3_bucket",
            "provider": "aws",
            "service": "storage",
            "kind": "s3",
            "attributes": {"encrypted": True},
        },
    ]
    x = [[resource_to_features(row)[column] for column in FEATURE_COLUMNS] for row in rows]
    model = RandomForestClassifier(n_estimators=4, random_state=1).fit(x, [0, 1])
    path = tmp_path / "model.joblib"
    joblib.dump(
        {
            "schema_version": "resource-v2",
            "columns": list(FEATURE_COLUMNS),
            "models": {"security": {"model": model}},
        },
        path,
    )

    result = predict(rows[1], path)
    assert result["ml_unavailable"] is False
    assert "security" in result["scores"]
    assert len(result["explanations"]["security"]) == 5


def test_ml_scoring_falls_back_when_model_is_missing(tmp_path: Path):
    result = predict({}, tmp_path / "missing.joblib")
    assert result == {"scores": {}, "explanations": {}, "ml_unavailable": True}


def test_ml_scoring_rejects_v1_model(tmp_path: Path):
    path = tmp_path / "old.joblib"
    joblib.dump({"schema_version": "resource-v1", "columns": [], "models": {}}, path)
    assert predict({}, path)["ml_unavailable"] is True
