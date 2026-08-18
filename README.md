# CloudPilot AI

> **AI-powered cloud infrastructure optimization platform.** Point CloudPilot at your Terraform or OpenTofu code and it parses every resource, prices it across 10 cloud providers, gives you a production readiness score, and generates copy-paste-ready optimized infrastructure code.

---

## Table of contents

- [What CloudPilot does](#what-cloudpilot-does)
- [Architecture](#architecture)
- [Key features](#key-features)
- [Technology stack](#technology-stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
  - [Docker (recommended)](#option-1--docker-recommended)
  - [Local development](#option-2--local-development)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## What CloudPilot does

CloudPilot takes Terraform `.tf` files as input and answers three questions:

1. **What are you running?** — Parses every `resource`, `data`, `module`, `variable`, and `output` block. Extracts instance types, storage sizes, network configurations, and IAM policies. Maps them to real-world cloud services with per-resource cost estimates.

2. **How much does it cost?** — Prices every resource using current cloud provider pricing data. Shows cost breakdowns by service, by region, and by module. Compares costs across 10 cloud providers (AWS, Azure, GCP, DigitalOcean, Hetzner, Scaleway, OVHcloud, Oracle, Vultr, Linode).

3. **How can you improve it?** — Runs 21 recommendation rules across 8 scoring dimensions (cost, security, reliability, performance, compliance, observability, maintainability, sustainability). Generates specific, actionable fixes with ready-to-apply Terraform code.

---

## Architecture

```
                          ┌──────────────────────────────────────────────────┐
                          │                    FRONTEND                      │
                          │                 Next.js 16 + React 19            │
                          │                                                  │
                          │  Landing  │  Dashboard  │  Login  │  Settings   │
                          └──────────────────────┬───────────────────────────┘
                                                 │ REST API
                                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND  (FastAPI)                               │
│                                                                            │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐ │
│  │  Auth    │   │ Projects │   │ Analyses │   │  Demo    │   │ Reports │ │
│  │ (JWT)   │   │  (CRUD)  │   │ (trigger)│   │ (sample) │   │ (PDF)   │ │
│  └─────────┘   └──────────┘   └────┬─────┘   └──────────┘   └─────────┘ │
│                                    │                                       │
│              ┌─────────────────────▼──────────────────────┐                │
│              │           ANALYSIS PIPELINE                 │                │
│              │                                             │                │
│              │  ┌──────────┐  ┌────────┐  ┌────────────┐ │                │
│              │  │   HCL    │─▶│ Pricer │─▶│ Recommend  │ │                │
│              │  │  Parser  │  │(10     │  │ Engine     │ │                │
│              │  │ (custom) │  │clouds) │  │ (21 rules) │ │                │
│              │  └──────────┘  └────────┘  └─────┬──────┘ │                │
│              │                                  │        │                │
│              │  ┌──────────┐  ┌────────┐  ┌─────▼──────┐ │                │
│              │  │   LLM    │  │ Scorer │  │ Optimizer  │ │                │
│              │  │ Review   │  │ (8 dim)│  │ (7 modes)  │ │                │
│              │  │(optional)│  └────────┘  └────────────┘ │                │
│              │  └──────────┘                              │                │
│              └─────────────────────────────────────────────┘                │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        SUPPORTING SERVICES                          │  │
│  │  Architecture  │  FinOps  │  Sustainability  │  Comparison  │  LLM │  │
│  │  Graph Builder │  (cost)  │  (CO2e)          │  (multi-cloud)│(API)│  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└──────────────────────────────────────┬─────────────────────────────────────┘
                                       │
                                       ▼
                          ┌──────────────────────┐
                          │     PostgreSQL 16     │
                          │  (users, projects,   │
                          │   analysis history)   │
                          └──────────────────────┘
```

### Pipeline flow

| Step | What happens |
|------|-------------|
| **1. Upload** | User provides Terraform files via the web UI or API. |
| **2. Parse** | The custom HCL2 parser reads every block, extracts resource types, configurations, references, and line numbers. No Terraform binary required. |
| **3. Price** | Each resource is priced across 10 cloud providers. Costs are aggregated by service, region, and module. |
| **4. Analyze** | 21 recommendation rules evaluate the infrastructure across 8 dimensions. An optional LLM adds a narrative review. |
| **5. Score** | A weighted score (0-100) is computed. Grade maps from A+ (95+) to F (<50). |
| **6. Optimize** | The engine generates replacement Terraform code for each recommendation, based on the selected mode. |
| **7. Display** | Results are shown in an interactive dashboard with charts, tables, architecture maps, and copy-paste-ready code. |

---

## Key features

### Infrastructure analysis

CloudPilot includes a custom HCL2 parser (hand-rolled, no external Terraform binary required). It reads `.tf` files directly, extracts resource definitions with references and line numbers preserved, and resolves interpolation expressions. Every resource is tagged with its source file and line number so you can jump straight to the code.

### AI-powered review

When an LLM API key is configured (OpenAI, Anthropic, Gemini, or HuggingFace), CloudPilot sends the parsed architecture to the model for a narrative review. Without a key, it falls back to a built-in heuristic engine with 21 rules that still produces detailed, explainable findings. The system uses a hybrid approach — the LLM generates natural-language explanations while the rule engine provides structured, deterministic recommendations.

### Multi-cloud cost comparison

CloudPilot prices your infrastructure across 10 cloud providers simultaneously. The comparison page shows a side-by-side bar chart and a detailed table with per-service cost breakdowns, delta percentages, and provider-specific notes.

### 7 optimization modes

Each mode re-plans your stack with different priorities:

| Mode | What it optimizes for |
|------|----------------------|
| **Balanced** | Even mix of cost, reliability, and security |
| **Lowest Cost** | Absolute minimum monthly spend |
| **Startup Budget** | Cheapest viable production setup |
| **Lowest Carbon** | Smallest environmental footprint |
| **Lowest Latency** | Fastest network paths and response times |
| **Reliability** | Maximum uptime and fault tolerance |
| **Security** | Strongest security posture |

### Production readiness score

Your infrastructure gets a score from 0 to 100, broken down across 8 dimensions:

| Dimension | What it measures |
|-----------|-----------------|
| **Cost** | Over-provisioning, cheaper alternatives |
| **Security** | Exposed ports, open security groups, unencrypted storage |
| **Reliability** | Single points of failure, redundancy |
| **Performance** | Instance sizing for expected load |
| **Compliance** | Missing tags, non-standard configurations |
| **Observability** | Monitoring, logging, and alerting resources |
| **Maintainability** | Code modularity, variable reuse |
| **Sustainability** | Carbon footprint of the deployment |

### Architecture visualization

An auto-laid-out topology map shows all your resources as nodes with connections between them. VPCs and security groups are shown as grouping boundaries. Each node displays its type, cost, and status.

### FinOps dashboard

- Monthly spend by service (bar chart)
- Rightsizing candidates
- Spot instance opportunities
- 12-month cost outlook (current vs. optimized annual spend)
- Carbon footprint estimates

---

## Technology stack

| Layer | Component | Technology |
|-------|-----------|-----------|
| **Frontend** | Framework | Next.js 16 (React 19) |
| | Language | TypeScript |
| | Styling | Tailwind CSS v4 |
| | Components | shadcn/ui |
| | Charts | Recharts |
| | Animations | Motion (Framer Motion) |
| | Code highlighting | prism-react-renderer |
| **Backend** | Framework | FastAPI |
| | Database | PostgreSQL + SQLAlchemy |
| | Migrations | Alembic |
| | Auth | JWT + bcrypt |
| | Parser | Custom HCL2 parser |
| | Pricing | Built-in catalog (10 providers) |
| | Testing | pytest + httpx |
| | Linting | ruff |
| **Infra** | Containers | Docker + Docker Compose |
| | CI | GitHub Actions |

---

## Project structure

```
cloudscanner/
├── backend/                         # Python backend (FastAPI)
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point
│   │   ├── api/                     # Route handlers
│   │   │   ├── auth.py              # Login, register, OAuth
│   │   │   ├── projects.py          # CRUD for projects
│   │   │   ├── analyses.py          # Trigger and retrieve analyses
│   │   │   ├── demo.py              # Demo endpoint (no auth)
│   │   │   ├── optimization.py      # Optimization recommendations
│   │   │   ├── architecture.py      # Architecture graph data
│   │   │   ├── score.py             # Production readiness score
│   │   │   ├── finops.py            # FinOps cost analysis
│   │   │   ├── comparison.py        # Multi-cloud comparison
│   │   │   ├── sustainability.py    # Carbon footprint
│   │   │   └── reports.py           # PDF/CSV report generation
│   │   ├── core/                    # Config, database, security
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   ├── schemas/                 # Pydantic request/response models
│   │   └── services/                # Business logic
│   │       ├── orchestrator.py      # Analysis pipeline coordinator
│   │       ├── hcl_parser.py        # Custom HCL2 parser
│   │       ├── pricing.py           # Pricing catalog (10 providers)
│   │       ├── recommendations.py   # 21 recommendation rules
│   │       ├── scoring.py           # 8-dimension scoring engine
│   │       ├── optimization.py      # Code generation (7 modes)
│   │       ├── architecture.py      # Graph layout algorithm
│   │       ├── finops.py            # Cost analysis and rightsizing
│   │       ├── sustainability.py    # CO2e estimation
│   │       ├── comparison.py        # Multi-cloud cost comparison
│   │       └── llm.py              # LLM integration
│   ├── tests/                       # pytest test suite
│   ├── alembic/                     # Database migrations
│   ├── pyproject.toml               # Python project config
│   └── Dockerfile
│
├── frontend/                        # Next.js frontend
│   ├── src/
│   │   ├── app/                     # Pages and layouts
│   │   │   ├── page.tsx             # Landing page
│   │   │   ├── login/               # Login/register
│   │   │   └── dashboard/           # Dashboard pages
│   │   │       ├── optimization/    # Recommendations + code
│   │   │       ├── architecture/    # Architecture map
│   │   │       ├── score/           # Score breakdown
│   │   │       ├── finops/          # Cost management
│   │   │       └── comparison/      # Multi-cloud comparison
│   │   ├── components/
│   │   │   ├── dashboard/           # Dashboard components
│   │   │   ├── ui/                  # Reusable UI primitives
│   │   │   └── hcl/                 # Terraform code highlighter
│   │   └── lib/
│   │       ├── api.ts               # API client
│   │       ├── types.ts             # TypeScript types
│   │       └── format.ts            # Currency/number formatting
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml               # Full stack orchestration
├── Makefile                         # Common commands
├── .env.example                     # Environment variable template
└── README.md
```

---

## Getting started

### Option 1 — Docker (recommended)

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) with Docker Compose v2, at least 4 GB free RAM.

```bash
git clone <your-repo-url> cloudscanner
cd cloudscanner
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/v1/health |
| Demo analysis | http://localhost:8000/api/v1/demo/analyze |

### Option 2 — Local development

**Prerequisites:** Python 3.11+, Node.js 18+, PostgreSQL 14+ (or SQLite for quick testing).

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Configuration

All settings are configured via environment variables. Copy `.env.example` to `.env` and edit it.

### Core settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./cloudpilot.db` | Database connection string |
| `JWT_SECRET` | `dev-only-secret` | JWT signing key (**change in production**) |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend URLs |
| `STORAGE_ROOT` | `./storage` | Uploaded Terraform file storage |

### LLM settings (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `auto` | `auto`, `openai`, `anthropic`, `gemini`, `huggingface`, or `none` |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `GEMINI_API_KEY` | — | Google Gemini API key |

CloudPilot works without any LLM configuration using its built-in heuristic engine.

---

## API reference

Full interactive docs at http://localhost:8000/docs (Swagger UI).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Create account |
| `/api/v1/auth/login` | POST | Sign in, get JWT |
| `/api/v1/projects` | GET/POST | List or create projects |
| `/api/v1/projects/{id}` | GET/DELETE | Get or delete project |
| `/api/v1/analyses` | POST | Trigger analysis |
| `/api/v1/analyses/{id}` | GET | Get analysis results |
| `/api/v1/analyses/{id}/optimization` | GET | Optimization recommendations |
| `/api/v1/analyses/{id}/architecture` | GET | Architecture graph |
| `/api/v1/analyses/{id}/score` | GET | Production score |
| `/api/v1/analyses/{id}/finops` | GET | FinOps data |
| `/api/v1/analyses/{id}/comparison` | GET | Multi-cloud comparison |
| `/api/v1/analyses/{id}/sustainability` | GET | Carbon footprint |
| `/api/v1/demo/analyze` | GET | Demo analysis (no auth) |

---

## Testing

```bash
# Backend
cd backend
python -m pytest -v

# Frontend
cd frontend
npm run lint
npm run build

# Both
make lint
```

---

## Troubleshooting

**"Connection refused" on the frontend** — Ensure the backend is running on port 8000 and `NEXT_PUBLIC_API_URL` is set correctly.

**"Module not found" errors** — Run `rm -rf node_modules && npm install` in the frontend directory.

**Database errors on startup** — If using PostgreSQL, make sure it's running and run `alembic upgrade head`.

**LLM review not working** — Set `LLM_PROVIDER` and the corresponding API key. For local models, use Ollama (see Configuration section).

---

## License

Private project. See project owners for licensing information.
