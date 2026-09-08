# CRIM-v4.2 — Advisory Risk Classification

CRIM-v4.2 is a lightweight, advisory machine-learning layer that classifies a
Terraform resource into one of three risk-relevant categories. It is **not** a
detection engine.

> **CRIM-v4.2 does not replace Checkov. Checkov remains the authoritative
> rule-based detection engine.**

## What CRIM-v4.2 does

Given a Terraform resource block, CRIM-v4.2 returns an advisory category based
on a frozen, validated pipeline (word TF-IDF + Logistic Regression):

* `NETWORK_SECURITY`
* `DATA_SECURITY`
* `OBSERVABILITY`

It is only useful as a triage/summarization signal on top of Checkov findings.
The two outputs may later be combined by an orchestrator, but CRIM never
suppresses, edits, or re-runs Checkov.

## Confidence threshold and abstention

The model reports a confidence equal to the maximum class probability. Default
threshold is **0.70**:

* `confidence >= 0.70` → a category is returned.
* `confidence < 0.70` → the model **abstains**: `category = null`,
  `abstained = true`, `reason = "ML classification uncertain"`.

A category is never forced below the threshold.

## Endpoint

```
POST /api/v1/risk/classify
```

Request:

```json
{
  "resource": "aws_security_group.web",
  "resource_type": "aws_security_group",
  "provider": "aws",
  "code_snippet": "resource \"aws_security_group\" \"web\" { ... }"
}
```

High-confidence response:

```json
{
  "classification": {
    "category": "NETWORK_SECURITY",
    "confidence": 0.84,
    "abstained": false,
    "reason": null
  },
  "probabilities": {
    "NETWORK_SECURITY": 0.84,
    "DATA_SECURITY": 0.10,
    "OBSERVABILITY": 0.06
  },
  "model": {
    "name": "CRIM-v4.2",
    "version": "v4.2",
    "threshold": 0.7
  }
}
```

Abstained response sets `category = null`, `abstained = true`, and
`reason = "ML classification uncertain"` in the `classification` object.

## Scan pipeline integration

The CloudPilot scan/orchestration pipeline (`POST /api/v1/analyses/{id}/analyze-zip`,
`POST /api/v1/analyses/{id}/analyze-github`, and `/api/v1/demo/analyze`) enriches
**every parsed non-data Terraform resource** with an advisory `ml_classification`
block. CRIM is invoked in-process through `RiskIntelligenceService` via
`app/services/risk_intelligence/pipeline.py` — the HTTP endpoint is never called
from inside the backend.

Each resource in the `resources` payload gains:

```json
{
  "ml_classification": {
    "category": "NETWORK_SECURITY",
    "confidence": 0.83,
    "abstained": false,
    "reason": null,
    "model": "CRIM-v4.2"
  }
}
```

On abstention:

```json
{
  "ml_classification": {
    "category": null,
    "confidence": 0.63,
    "abstained": true,
    "reason": "ML classification uncertain",
    "model": "CRIM-v4.2"
  }
}
```

Each **finding** in the `recommendations` payload also gains the resolved
`ml_classification` of its target resource(s). When a finding targets a single
resource (the common case) the finding carries that classification directly.
When a finding targets several resources whose classifications disagree, the
finding carries `null` to avoid attributing a single category; the individual
resource classifications remain authoritative in `resources`. Similarly, targets
that map to a data source (never classified) yield `null`. Checkov-derived
finding fields are never changed — `ml_classification` is purely additive.

A run-level `crim` summary is added at the top of the analysis payload:

```json
{
  "crim": {
    "name": "CRIM-v4.2",
    "version": "v4.2",
    "threshold": 0.7,
    "ml_unavailable": false,
    "classified": 5,
    "abstained": 2,
    "unclassified": 1,
    "resources": 8
  }
}
```

Scan-time feature construction mirrors the training distribution exactly:
`resource` is the full Terraform address, `resource_type` is its first segment
(`module.x.aws_s3_bucket.this` -> `module`), `provider` is the parsed provider,
and `code_snippet` is the raw text of the Terraform file that declared the
resource (already parsed — never re-parsed or reconstructed), truncated to the
same 2000-character limit used in training. Data sources are not classified,
matching the existing pipeline ML behavior.

### Guarantees

* A CRIM outage — missing/corrupt artifact or a prediction failure — **never
  breaks a scan**. Findings are always returned; affected resources and findings
  carry `ml_classification = null` and `crim.ml_unavailable` is set to `true`.
* CRIM **never decides whether a finding exists**. The deterministic rules
  engine (the Checkov-equivalent detection surface in this backend) is untouched
  and passes through byte-identical. Original finding fields are never changed.
* One classification per resource is computed and shared across all findings
  that target it. When a finding targets multiple resources whose classifications
  disagree, the finding carries `null`; no per-rule classifications are invented.

## Model artifact

The loaded artifact lives at:

```
models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib
```

It is loaded once at startup (and lazily on first request) by
`app/services/risk_intelligence/service.py`
(`RiskIntelligenceService`). The path and threshold come from configuration:

| Env var | Default |
|---|---|
| `CRIM_MODEL_PATH` | `models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib` |
| `CRIM_CONFIDENCE_THRESHOLD` | `0.70` |

The model path is never supplied by API clients.

## Features

Only the following are fed to the model: `resource`, `resource_type`,
`provider`, and `code_snippet`. Checkov rule id/name, guideline, taxonomy,
repository, and labels are **never** used as features.

## Availability

If the artifact is missing, corrupt, or incompatible, the endpoint returns
**HTTP 503** and never fabricates a classification. This is advisory and
decoupled: the rest of the API — including all Checkov-backed analysis —
continues to work normally.

## Relationship to Checkov

```
Terraform
   |
   +--> Checkov engine  --> authoritative findings
   |
   +--> CRIM-v4.2       --> advisory classification
```

Checkov is the authoritative detection engine and is not modified or invoked by
this integration.

## Final integration report

| Item | Value |
|---|---|
| **Endpoint** | `POST /api/v1/analyses/{id}/analyze-zip` and `analyze-github` (plus `/api/v1/demo/analyze`). All resources gain `ml_classification`; all findings carry the classification of their target resource; the payload gains a `crim` summary. |
| **Service** | `app/services/risk_intelligence/pipeline.py::classify_resources` in-process via `RiskIntelligenceService` (`app/services/risk_intelligence/service.py`). HTTP is never called inside the backend. |
| **Model** | `CRIM-v4.2` (`v4.2`), frozen TF-IDF + Logistic Regression, `models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib`. |
| **Threshold** | 0.70 with abstention; `confidence < 0.70` → `category = null`, `abstained = true`, `reason = "ML classification uncertain"`. |
| **Architecture** | Checkov remains the authoritative detection layer. CRIM is a **single advisory pass** over already-parsed resources — no second pipeline, no re-parse, no blocking. One resource-level classification is computed and shared across all findings that target it; rule identity never influences the ML input. |
| **Does CRIM failure affect Checkov?** | **No.** A CRIM outage/failure only sets `ml_classification = null` on resources and findings, and `ml_unavailable = true`; findings and the rest of the analysis are always returned. |
| **Was Checkov modified?** | **No.** No engine, rules scanner, package, or Checkov-invoking code was touched. |
| **Was the model retrained?** | **No.** The frozen `v4.2` artifact and its dataset are untouched. |
| **Was the frontend modified?** | **No.** Additive optional keys only; existing consumers are unaffected. |
| **Existing API contract preserved?** | **Yes.** Every pre-existing field is returned unchanged (verified by `test_scan_findings_and_resources_contract_unchanged`, which strips `ml_classification` and confirms exact equality with a pure CRIM-off run). |
| **Tests** | `python -m pytest -q`: **237 passed, 1 failed** — the failure is the known pre-existing `test_crim_v3_pipeline.py::test_crim_v3_preflight_rejects_unsupported_classes_without_legacy_changes` (stale v3 artifact contradiction, out of scope). **0 new failures.** New coverage: `tests/test_crim_scan_pipeline.py` (13 tests: contract, 3 classes, abstention, unavailable × 2, dedup, forbidden features, resource-type convention, determinism, Checkov isolation, standalone endpoint). |
| **Lint/format** | `ruff check` and `ruff format --check` clean on all changed files (line-length 100, E501 ignored, select E,F,W,I,UP,B). |
| **Changed files** | New: `app/services/risk_intelligence/pipeline.py`, `tests/test_crim_scan_pipeline.py`. Modified: `app/services/analysis/orchestrator.py`, `docs/CRIM_V4_2.md`. |

### Worked example (real output taken from the pipeline run)

A rule finding fires on an open security group, and CRIM attaches its advisory
block to the same resource. Below the threshold, CRIM abstains — the finding
still stands, CRIM simply declines to label it:

```json
{
  "key": "sg-open-world",
  "title": "Security Group open exposes SSH/RDP (22/3389) to the internet",
  "severity": "critical",
  "category": "security",
  "target": ["aws_security_7b3dccfa"],
  "ml_classification": {
    "category": null,
    "confidence": 0.4998,
    "abstained": true,
    "reason": "ML classification uncertain",
    "model": "CRIM-v4.2"
  }
}
```

The same payload's `resources` section carries confident classifications too —
on the same run, `google_compute_subnetwork.main` classified at
`NETWORK_SECURITY` with confidence `0.827` (no rule fires on the subnetwork
kind; classification is per-resource and independent of whether a finding
exists).

### Product positioning

CloudPilot uses Checkov for deterministic infrastructure misconfiguration
detection and CRIM-v4.2 as a supervised ML layer for semantic security-domain
classification with confidence-based abstention.
