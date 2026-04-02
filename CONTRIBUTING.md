# Contributing to ETIP

Thank you for your interest in contributing to the Enterprise Talent Intelligence Platform. This document explains how to get involved, from reporting bugs to shipping new connectors.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Ways to Contribute](#ways-to-contribute)
- [Development Setup](#development-setup)
- [Workflow](#workflow)
- [Coding Standards](#coding-standards)
- [Writing Tests](#writing-tests)
- [Adding a Connector](#adding-a-connector)
- [Commit Messages](#commit-messages)
- [Pull Request Guidelines](#pull-request-guidelines)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold it. Please report unacceptable behavior to the maintainers.

---

## Ways to Contribute

- **Bug reports** — open an issue with a clear title, steps to reproduce, expected vs. actual behavior, and your environment.
- **Feature requests** — open an issue describing the problem you are solving, not just the solution.
- **Documentation** — fix typos, improve clarity, or add missing context.
- **New connectors** — add a data source plugin for GitHub, Jira, HRIS systems, or anything that follows the hookspec.
- **Core improvements** — matching quality, performance, security, or developer experience.

---

## Development Setup

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [uv](https://docs.astral.sh/uv/) for Python package management
- Node.js 20+ (for the frontend)

### 1. Clone and configure

```bash
git clone https://github.com/<your-org>/etip.git
cd etip
cp .env.example .env
# Fill in JWT_SECRET and GROQ_API_KEY (free tier at console.groq.com)
```

### 2. Start infrastructure

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis qdrant
```

### 3. Install dependencies and migrate

```bash
cd apps/api
uv sync
uv run alembic upgrade head
uv run python scripts/seed_tenant.py
```

### 4. Run the API and worker

```bash
# Terminal 1
uv run uvicorn etip_api.main:app --reload --port 8000

# Terminal 2
uv run celery -A etip_api.worker.celery_app worker --loglevel=info
```

### 5. Run the frontend

```bash
cd apps/web
npm install
npm run dev   # http://localhost:3000
```

---

## Workflow

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make your changes, write tests, and confirm everything passes.
3. Open a **pull request** against `main` with a clear description.
4. A maintainer will review within a few business days.

---

## Coding Standards

### Python

- Style: [Ruff](https://docs.astral.sh/ruff/) for linting and formatting (`ruff check .` and `ruff format .`).
- Type hints are required for all public functions and service-layer code.
- Use `async/await` consistently throughout the FastAPI layer; synchronous code belongs in the Celery worker.
- No bare `except:` clauses — always catch specific exceptions.

### TypeScript / React

- Strict mode is enabled; no `any` without justification.
- Components live in `apps/web/components/`; pages in `apps/web/app/(dashboard)/`.
- Use TanStack Query for all server state — no raw `fetch` in components.

### General

- Do not commit `.env` files, secrets, or credentials.
- Do not add `print()` / `console.log()` debug statements.
- Keep changes focused — one logical change per pull request.

---

## Writing Tests

```bash
# All unit tests
cd apps/api
uv run pytest tests/unit/

# Integration tests (requires running postgres + redis)
uv run pytest tests/integration/

# All tests with coverage
uv run pytest --cov=etip_api --cov-report=term-missing
```

- Unit tests must not hit the database or any external service.
- Use `pytest-mock` / `unittest.mock` for isolation.
- Integration tests use real PostgreSQL started by Docker Compose.
- Target ≥80% coverage on new code. The CI pipeline enforces this.

---

## Adding a Connector

Connectors are independent Python packages installed via entry points. To add a new data source:

1. Create `apps/api/connectors/<name>/` with the following layout:
   ```
   connectors/<name>/
   ├── pyproject.toml
   └── src/etip_connector_<name>/
       ├── __init__.py
       ├── client.py       # API client for the external service
       └── connector.py    # pluggy @hookimpl implementations
   ```

2. Implement the required hooks in `connector.py`:
   ```python
   from etip_core.hookspecs import hookimpl

   class MyConnector:
       @hookimpl
       def health_check(self, config: dict) -> dict: ...

       @hookimpl
       def sync_employees(self, tenant_id: str, config: dict) -> list[dict]: ...

       @hookimpl
       def sync_skills(self, tenant_id: str, employee_external_id: str, config: dict) -> list[dict]: ...

       @hookimpl
       def sync_projects(self, tenant_id: str, config: dict) -> list[dict]: ...
   ```

3. Register the entry point in `pyproject.toml`:
   ```toml
   [project.entry-points."etip"]
   myconnector = "etip_connector_myconnector:MyConnector"
   ```

4. Add the package to the root `pyproject.toml` workspace members.

5. Add connector metadata to `apps/web/app/(dashboard)/connectors/page.tsx` (`CONNECTOR_META`).

6. Write unit tests in `apps/api/tests/unit/connectors/test_<name>.py`.

---

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`

Examples:
```
feat(connector): add GitLab connector with language + MR skill inference
fix(matching): correct business-day calculation across month boundaries
docs(readme): add connector development guide
test(sync): add fuzzy name deduplication edge cases
```

---

## Pull Request Guidelines

- **Title** follows the same Conventional Commits format as commit messages.
- **Description** explains *why* the change is needed, not just *what* it does.
- Link the related issue with `Closes #<issue-number>` if applicable.
- All CI checks must pass before merge.
- At least one maintainer approval is required.
- Squash merge is preferred to keep `main` history clean.

---

Thank you for contributing to ETIP.
