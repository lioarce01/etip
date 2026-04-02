# ETIP — Enterprise Talent Intelligence Platform

ETIP helps engineering organizations match the right people to the right projects. It aggregates employee data from multiple sources, infers skills from real work activity, and surfaces AI-ranked candidate recommendations with natural-language explanations.

---

## What it does

**Talent graph from real signals.** ETIP syncs your engineering org from GitHub (repositories, languages, pull request activity) and Jira (issue assignments, labels, components) into a unified employee–skill graph. Skills are inferred from actual work — not self-reported — and normalized against the ESCO taxonomy.

**Project staffing recommendations.** Define a project with required skills and ETIP returns a ranked list of candidates. Ranking combines vector similarity search (Qdrant + fastembed), skill overlap scoring, cross-encoder reranking (ms-marco-MiniLM via flashrank), and LLM-generated explanations (Groq / llama-3.3-70b or any LiteLLM-compatible provider).

**Availability-aware.** Employee availability is calculated from active allocations, accounting for business-day overlap with the project timeline. Over-allocated employees are filtered before recommendations are generated.

**Multi-tenant by design.** Every row in the database is scoped to a tenant via PostgreSQL Row-Level Security. A single deployment serves multiple organizations with complete data isolation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Next.js (web)                      │
│   Dashboard · Connectors · Employees · Projects · Recs  │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP (internal)
┌────────────────────────▼────────────────────────────────┐
│                    FastAPI (api)                         │
│  Auth · Tenants · Employees · Projects · Recommendations │
└──────┬──────────────────────────────────┬───────────────┘
       │ Celery tasks                     │ async queries
┌──────▼──────────┐              ┌────────▼───────────────┐
│  Celery Worker  │              │      PostgreSQL         │
│  Connector sync │              │  RLS · pgvector · JSONB │
│  Qdrant index   │              └────────────────────────┘
└──────┬──────────┘
       │
┌──────▼──────────┐   ┌──────────────┐   ┌──────────────┐
│     Qdrant      │   │    Redis     │   │  LLM Provider │
│  Vector search  │   │  Task queue  │   │  Groq / etc.  │
└─────────────────┘   └──────────────┘   └──────────────┘
```

### Packages

| Path | Description |
|---|---|
| `apps/api` | FastAPI application — routers, models, services, Alembic migrations |
| `apps/api/core` | `etip-core` — shared DTOs, hookspecs, plugin manager, settings |
| `apps/api/connectors/github` | GitHub connector plugin |
| `apps/api/connectors/jira` | Jira Cloud connector plugin |
| `apps/web` | Next.js 15 frontend — React, TanStack Query, Tailwind, shadcn/ui |

---

## Connector system

Connectors are independent Python packages that implement a [pluggy](https://pluggy.readthedocs.io/) hookspec. Adding a new data source means creating a package with `@hookimpl` methods — no changes to core required.

**Available hooks:**

```python
def health_check(config: dict) -> dict
def sync_employees(tenant_id: str, config: dict) -> list[dict]
def sync_skills(tenant_id: str, employee_external_id: str, config: dict) -> list[dict]
def sync_projects(tenant_id: str, config: dict) -> list[dict]
```

**Built-in connectors:**

| Connector | Employees | Skills | Projects |
|---|---|---|---|
| GitHub | Org members | Languages, repo topics | — |
| Jira Cloud | Active users | Issue labels, components | Jira Projects |

Connectors are registered as Python entry points under the `etip` group and discovered automatically at runtime.

---

## Recommendation pipeline

```
1. Qdrant ANN search      — retrieve candidate pool by skill embedding similarity
2. Skill overlap scoring  — weighted score per required skill (0.0 – 1.0)
3. Availability filter    — drop candidates below threshold (business-day weighted)
4. Cross-encoder rerank   — flashrank ms-marco-MiniLM-L-2-v2, CPU-only, ~25 MB
5. LLM explanation        — per-candidate natural language summary via LiteLLM
6. Persist & return       — upsert Recommendation rows, return top-K results
```

Employees with zero skill overlap are dropped before the LLM step. Feedback (accepted / rejected) is preserved across re-runs via `INSERT ... ON CONFLICT DO UPDATE`.

---

## Getting started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### 1. Clone and configure

```bash
git clone <repo-url> etip
cd etip
cp .env.example .env   # fill in GROQ_API_KEY and JWT_SECRET
```

Minimum `.env`:

```env
JWT_SECRET=change-me-in-production
GROQ_API_KEY=gsk_...          # from console.groq.com — free tier available
```

### 2. Start infrastructure

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis qdrant
```

### 3. Run migrations and seed

```bash
cd apps/api
uv run alembic upgrade head
uv run python scripts/seed_tenant.py   # creates demo company + admin user
```

### 4. Start the API and worker

```bash
# Terminal 1 — API
uv run uvicorn etip_api.main:app --reload --port 8000

# Terminal 2 — Celery worker
uv run celery -A etip_api.worker.celery_app worker --loglevel=info
```

### 5. Start the frontend

```bash
cd apps/web
npm install
npm run dev   # http://localhost:3000
```

### Full Docker stack

```bash
docker compose -f infra/docker-compose.yml up --build
```

---

## API overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register a new company + admin |
| `POST` | `/api/v1/auth/login` | Obtain JWT token |
| `GET` | `/api/v1/employees` | List employees with skills and availability |
| `POST` | `/api/v1/employees/import/csv` | Bulk import via CSV |
| `GET` | `/api/v1/projects` | List projects |
| `POST` | `/api/v1/projects` | Create project with required skills |
| `GET` | `/api/v1/projects/{id}/recommendations` | Run matching pipeline |
| `POST` | `/api/v1/projects/{id}/recommendations/{rec_id}/feedback` | Submit feedback |
| `GET` | `/api/v1/connectors/available` | List registered connector plugins |
| `POST` | `/api/v1/connectors` | Configure a connector |
| `POST` | `/api/v1/connectors/{id}/sync` | Trigger async sync |

Interactive docs available at `http://localhost:8000/docs`.

---

## Development

### Running tests

```bash
cd apps/api
uv run pytest                          # all tests
uv run pytest tests/unit/             # unit tests only
uv run pytest tests/integration/      # requires running postgres + redis
```

### Adding a connector

1. Create `apps/api/connectors/<name>/` with `pyproject.toml` and `src/etip_connector_<name>/`
2. Implement the hookspec methods using `@hookimpl` from `etip_core`
3. Register the entry point in `pyproject.toml`:
   ```toml
   [project.entry-points."etip"]
   name = "etip_connector_name:MyConnector"
   ```
4. Add the package to the root `pyproject.toml` workspace members
5. Add connector metadata (`icon`, `description`, `fields`) to the frontend `CONNECTOR_META` map

### Project structure

```
etip/
├── apps/
│   ├── api/
│   │   ├── src/etip_api/          # FastAPI app
│   │   │   ├── routers/           # HTTP endpoints
│   │   │   ├── models/            # SQLAlchemy ORM models
│   │   │   ├── schemas/           # Pydantic response schemas
│   │   │   ├── services/          # matching, embedding, LLM, ESCO
│   │   │   └── worker/            # Celery tasks + sync runner
│   │   ├── core/src/etip_core/    # Shared DTOs, hookspecs, settings
│   │   ├── connectors/
│   │   │   ├── github/            # GitHub connector plugin
│   │   │   └── jira/              # Jira Cloud connector plugin
│   │   ├── alembic/               # Database migrations
│   │   ├── tests/                 # Unit + integration tests
│   │   └── scripts/               # Seed scripts, exploration tools
│   └── web/
│       ├── app/(dashboard)/       # Next.js App Router pages
│       ├── components/            # Shared UI components
│       ├── lib/                   # API client, hooks, store
│       └── types/                 # TypeScript API types
└── infra/
    ├── docker-compose.yml
    ├── Dockerfile.api
    └── Dockerfile.web
```

---

## Tech stack

**Backend:** Python 3.12 · FastAPI · SQLAlchemy (async) · Alembic · Celery · Pydantic
**AI/ML:** fastembed (BAAI/bge-small-en-v1.5) · Qdrant · flashrank (ms-marco-MiniLM-L-2-v2) · LiteLLM
**Data:** PostgreSQL 16 + pgvector · Redis · JSONB
**Frontend:** Next.js 15 · React · TypeScript · TanStack Query · Tailwind CSS · shadcn/ui
**Infra:** Docker · uv · pluggy · Hatchling

---

## License

Private — all rights reserved.
