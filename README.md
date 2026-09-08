<div align="center">

# CloudPilot AI

**Analyze, score, and optimize your Terraform infrastructure across 10 cloud providers.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](backend/pyproject.toml)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](backend/pyproject.toml)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](backend)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2016-000000.svg)](frontend)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6.svg)](frontend)

Point CloudPilot at any Terraform or OpenTofu repository and it parses every
resource, prices it across 10 cloud providers, produces a production-readiness
score, explains exactly what evidence it used — and flags what it could not
inspect.

</div>

---

## Table of contents

- [What it does](#what-it-does)
- [Key features](#key-features)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
  - [Option 1 — Docker (recommended)](#option-1--docker-recommended)
  - [Option 2 — Local development](#option-2--local-development)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## What it does

CloudPilot turns a Terraform codebase into answers:

1. **What are you running?** — A hand-rolled HCL2 parser extracts every
   `resource`, `data`, `module`, `variable`, and `output` block — instance
   types, storage sizes, network rules, IAM references — all with source file
   and line-number provenance. No Terraform binary required.

2. **How much does it cost?** — Every resource is priced against a built-in
   catalog spanning **AWS, Azure, GCP, DigitalOcean, Hetzner, Scaleway,
   OVHcloud, Oracle, Vultr, and Linode**, with per-service, per-region, and
   per-module breakdowns.

3. **How healthy is it?** — A weighted **production-readiness score (0–100)**
   across 8 dimensions, driven by 20+ deterministic rules and — when the repo is
   not fully inspected (for example, local modules that weren't uploaded) — an
   explicit evidence-coverage warning instead of a silent guess.

4. **How do I improve it?** — Actionable, severity-ranked recommendations with
   ready-to-apply Terraform fixes, multi-cloud comparison, and a FinOps view of
   your spend.

---

## Key features

### Custom HCL2 parser
Hand-rolled Terraform parser with full interpolation handling. Resources keep
their source file and line numbers from parse to presentation, so every finding
links back to code.

### Multi-cloud cost engine
A normalized pricing catalog prices the same architecture on 10 providers.
The comparison view shows per-service breakdowns, cost deltas, and
provider-specific caveats side by side.

### Production readiness score
A weighted 0–100 score across **Cost, Security, Reliability, Performance,
Compliance, Observability, Maintainability, and Sustainability**. The scorer
publishes its evidence: a per-dimension breakdown, coverage percentage, and the
specific dimensions that couldn't be assessed.

### Evidence coverage honesty
When modules could not be expanded or inspected, CloudPilot says so. The
Overview and Score cards show a visible **"Incomplete — N modules not
inspected"** badge whenever evidence coverage drops below the completeness
threshold, so a low score is never mistaken for a full audit.

### Architecture visualization
Auto-laid-out topology graph of every resource, grouped by VPCs and security
groups. Drag to pan, scroll or pinch to zoom, double-click to fit, and hover or
click any node for detail.

### FinOps dashboard
Service-level spend breakdown, rightsizing candidates, spot-instance
opportunities, a 12-month cost outlook, and carbon-footprint estimates.

### AI-assisted analysis
- A deterministic **rule engine** (20+ rules) — fast, repeatable, explainable.
- An optional **LLM narrative review** (HuggingFace by default; OpenAI,
  Anthropic, and Gemini supported).
- A bundled **local risk-intelligence model (CRIM-v4.2)** that classifies
  findings and recommendations at inference time — no cloud round-trip needed.

---

## Architecture

```
             ┌────────────────────────────────────────────────┐
             │                    FRONTEND                     │
             │         Next.js 16 + React 19 + TypeScript      │
             │  Landing · Login · Overview · Architecture ·   │
             │  Score · FinOps · Comparison · Settings          │
             └───────────────────────┬────────────────────────┘
                                     │  REST API  (FastAPI)
                                     ▼
┌───────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                     │
│                                                               │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────┐  │
│  │ Auth/JWT│  │Projects │  │Analyses │  │  Demo   │  │Risk │  │
│  └─────────┘  └─────────┘  └────┬────┘  └─────────┘  └──┬──┘  │
│                                 │                        │     │
│            ┌────────────────────▼───────┐   ┌────────────▼──┐ │
│            │       ANALYSIS PIPELINE      │   │  ML / CRIM    │ │
│            │ ┌─────────┐ ┌───────┐ ┌─────┐│   │  features      │ │
│            │ │   HCL   │▶│Pricing│▶│Rules││   │  + classifier  │ │
│            │ │  Parser │ │(10    │ │(20+ ││   └───────────────┘ │
│            │ │(custom) │ │clouds)│ │rules)││                     │
│            │ └─────────┘ └───────┘ └──┬──┘│                     │
│            │  ┌─────────┐  ┌──────────▼─┐│  ┌───────────────┐  │
│            │  │  LLM    │  │   Scorer    ││  │  Supporting   │  │
│            │  │ Review  │  │ (8 dims +   ││  │  services:    │  │
│            │  │(optional)│ │  evidence)  ││  │  architecture,│  │
│            │  └─────────┘  └────────────┘│  │  finops,       │  │
│            │                              │  │  comparison,   │  │
│            │                              │  │  sustainability│  │
│            │                              │  └───────────────┘  │
│            └──────────────────────────────┘                     │
└───────────────────────────────┬────────────────────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │   PostgreSQL 16       │
                    │  users · projects ·   │
                    │  analysis history     │
                    └───────────────────────┘
```

### Analysis pipeline

| Step | What happens |
|------|-------------|
| **1. Upload** | Point the web app at a public GitHub repo, or upload Terraform files directly. |
| **2. Parse** | The built-in HCL2 parser reads every block and preserves references and line numbers. |
| **3. Price** | Each resource is priced on 10 cloud providers; totals are aggregated by service, region, and module. |
| **4. Analyze** | 20+ rules evaluate the stack across 8 dimensions. A local CRIM-v4.2 model classifies findings; an optional LLM adds a narrative review. |
| **5. Score** | Weighted 0–100 score with a per-dimension breakdown and explicit evidence-coverage accounting. |
| **6. Present** | Results surface in an interactive dashboard — cards, charts, an explorable architecture map, and copy-able fixes — including warnings when parts of the repo were not inspected. |

---

## Technology stack

| Layer | Component | Technology |
|-------|-----------|------------|
| **Frontend** | Framework | Next.js 16 (React 19, TypeScript) |
| | Styling | Tailwind CSS v4 + Material Design 3 tokens |
| | Components | shadcn/ui components with Material icon set |
| | Charts | Recharts |
| | Code rendering | prism-react-renderer |
| **Backend** | Framework | FastAPI |
| | Database | PostgreSQL 16 + SQLAlchemy + Alembic |
| | Auth | JWT + bcrypt, optional Google/GitHub OAuth |
| | Parsing | Custom HCL2 parser (no Terraform binary) |
| | Pricing | Built-in catalog for 10 providers |
| | ML | scikit-learn + joblib (local CRIM-v4.2 classifier) |
| | Testing | pytest + httpx / ruff |
| **Infra** | Containers | Docker + Docker Compose |
| | CI | GitHub Actions (`.github/workflows/ci.yml`) |

---

## Project structure

```
cloudscanner/
├── backend/                        # Python / FastAPI backend
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── api/
│   │   │   ├── router.py           # Aggregates all v1 routers
│   │   │   └── v1/                 # health, auth, projects, analyses,
│   │   │                           #   score, comparison, architecture,
│   │   │                           #   finops, sustainability, reports,
│   │   │                           #   scenario, demo, risk
│   │   ├── core/                   # config, database, security, deps
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── models_ml/              # ML model loading / wrappers
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   └── services/
│   │       ├── analysis/           # pipeline orchestrator + demo data
│   │       ├── terraform/          # HCL parser + registry resolution
│   │       ├── pricing/            # catalog, engine, comparison
│   │       ├── recommendations/    # 20+ deterministic rules + engine
│   │       ├── scoring/            # 8-dimension score + evidence coverage
│   │       ├── optimization/       # fix/code rendering helpers
│   │       ├── architecture/       # topology graph builder
│   │       ├── finops/             # cost analysis, rightsizing, trends
│   │       ├── sustainability/     # carbon estimates
│   │       ├── llm/                # provider router (HF, OpenAI, …)
│   │       ├── ml/                 # CRIM feature engineering
│   │       └── risk_intelligence/  # CRIM-v4.2 classifier service
│   ├── docs/                       # design docs (CRIM_V4_2.md)
│   ├── models/                     # pre-trained model artifacts
│   ├── tests/                      # pytest suite
│   ├── scripts/                    # seed_demo.py + sample project
│   ├── alembic/                    # database migrations
│   ├── pyproject.toml
│   └── Dockerfile
│
├── frontend/                       # Next.js 16 frontend
│   ├── src/
│   │   ├── app/                    # landing, login, and dashboard routes
│   │   │   └── dashboard/          # Overview, Architecture, Score,
│   │   │                           #   FinOps, Comparison, Settings
│   │   ├── components/
│   │   │   ├── dashboard/          # cards, evidence badges, CRIM chips
│   │   │   ├── architecture/       # interactive SVG canvas
│   │   │   ├── charts/             # recharts wrappers
│   │   │   └── ui/                 # shadcn/ui primitives
│   │   └── lib/                    # API client, types, formatting
│   ├── public/
│   ├── package.json
│   └── Dockerfile
│
├── scripts/sample_project/         # sample Terraform for quick smoke tests
├── docker-compose.yml              # full-stack orchestration
├── Makefile                        # common commands
├── .env.example                    # environment variable template
└── README.md
```

---

## Getting started

### Option 1 — Docker (recommended)

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) with Docker
Compose v2, at least 4 GB of free RAM.

```bash
git clone https://github.com/<your-org>/cloudscanner.git
cd cloudscanner
cp .env.example .env                 # then fill in JWT_SECRET / LLM keys
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/v1/health |
| Demo analysis | http://localhost:8000/api/v1/demo/analyze |

### Option 2 — Local development

**Prerequisites:** Python 3.11+, Node.js 18+, PostgreSQL 14+ (or SQLite for a
quick look).

```bash
# 1. Backend
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# 2. Frontend (separate terminal)
cd frontend
npm install
npm run dev                          # http://localhost:3000
```

When the dashboard opens, click **"Or explore the demo project"** to see a full
analysis without configuring a repository.

---

## Configuration

All settings are environment variables. Copy `.env.example` to `.env` and edit.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./cloudpilot.db` | Database connection string |
| `JWT_SECRET` | `change-me-in-production` | JWT signing key (**change in production**) |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origins (comma-separated) |
| `STORAGE_ROOT` | `./storage` | Uploaded artifact storage location |

### LLM (optional)

CloudPilot works without an LLM — the deterministic rule engine is
self-contained. Set a provider to add narrative reviews.

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `huggingface` | `huggingface`, `openai`, `anthropic`, or `gemini` |
| `HF_API_KEY` | — | HuggingFace API key |
| `HF_BASE_URL` | `https://router.huggingface.co/v1` | HuggingFace OpenAI-compatible endpoint |
| `HF_MODEL` | `Qwen/Qwen3-Coder-30B-A3B-Instruct` | Model to use |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | — | API keys for alternative providers |

### OAuth (optional)

Set `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` and/or
`GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET` to enable social login.

---

## API reference

Interactive docs are available at http://localhost:8000/docs (Swagger UI).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Service health |
| `/api/v1/auth/register` | POST | Create account |
| `/api/v1/auth/login` | POST | Sign in, get JWT |
| `/api/v1/projects` | GET/POST | List or create projects |
| `/api/v1/projects/{project_id}` | GET/DELETE | Get or delete a project |
| `/api/v1/analyses` | GET | List saved analyses |
| `/api/v1/analyses/{analysis_id}` | GET | Analysis results |
| `/api/v1/analyses/{project_id}/analyze-zip` | POST | Analyze an uploaded archive for a project |
| `/api/v1/analyses/{project_id}/analyze-github` | POST | Analyze a GitHub repo for a project |
| `/api/v1/score` | POST | Production-readiness score (Terraform payload) |
| `/api/v1/architecture` | POST | Architecture graph |
| `/api/v1/finops` | POST | FinOps breakdown |
| `/api/v1/comparison` | POST | Multi-cloud comparison |
| `/api/v1/comparison/providers` | GET | Supported provider catalog |
| `/api/v1/sustainability` | POST | Carbon estimates |
| `/api/v1/scenario` | POST | What-if scenarios |
| `/api/v1/reports/{analysis_id}` | GET | Generated reports |
| `/api/v1/risk/classify` | POST | CRIM-v4.2 finding classification |
| `/api/v1/demo/analyze` | GET | Demo analysis (no auth) |
| `/api/v1/demo/analyze/{mode}` | GET | Demo analysis with a specific mode |
| `/api/v1/demo/analyze-github` | GET | Demo analysis from a public GitHub repo |

> All `/api/v1/*` routes are prefixed by the API gateway. Analysis endpoints
> accept Terraform files via JSON payload (see `backend/app/schemas/analysis.py`
> and the Swagger docs at http://localhost:8000/docs).

---

## Testing

```bash
# Backend (lint + format + tests)
cd backend
python -m ruff check app tests scripts
python -m ruff format --check app tests scripts
python -m pytest -q

# Frontend (lint + unit tests + production build)
cd frontend
npm run lint
npx vitest run
npm run build

# Or use the Makefile from the repo root
make test      # backend tests
make lint      # ruff + eslint
```

The CI pipeline (`.github/workflows/ci.yml`) runs all of these on every push
and pull request.

---

## Troubleshooting

**Frontend can't reach the backend** — Make sure the backend runs on port 8000
and `NEXT_PUBLIC_API_URL` points at it (`http://localhost:8000` for local dev).

**Module not found errors** — Reinstall dependencies:
`rm -rf node_modules && npm install` (frontend), or
`pip install -e ".[dev]"` (backend).

**Database errors on startup** — For PostgreSQL, confirm the server is running
and execute `make migrate` (or `alembic upgrade head`) to apply migrations.

**No narrative LLM review** — The app is fully functional without one; to enable
it, set `LLM_PROVIDER` and the matching API key in `.env`.

**Findings say modules weren't inspected** — Local modules need their source
uploaded with the repo. The evidence-coverage badge tells you exactly how many
modules were not inspected and why.

---

## License

MIT — see the project owners for details. The bundled CRIM-v4.2 risk-intelligence
model is described in [`backend/docs/CRIM_V4_2.md`](backend/docs/CRIM_V4_2.md).