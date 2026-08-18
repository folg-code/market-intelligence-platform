# moj-projekt

Market Intelligence Platform - evidence-backed market narrative intelligence.
See `docs/README.md` for the full documentation set.

## Quickstart

### 1. Toolchain (Python environment)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"
```

### 2. Environment configuration

```bash
cp .env.example .env
# then edit .env and set a real POSTGRES_PASSWORD
```

`.env` is git-ignored; `.env.example` is the only committed template. Typed
settings are loaded from it via `src/moj_projekt/config/settings.py`
(ADR-0013) - no `os.environ` read belongs anywhere else in the codebase.

### 3. Bring up the stack

```bash
docker compose up -d
```

This starts `db` (PostgreSQL + pgvector, `pgvector/pgvector:pg16`, exposed on
host port `5433` by default to avoid clashing with a locally installed
Postgres) and `app` (FastAPI, port `8000`).

### 4. Apply migrations

```bash
alembic upgrade head
```

Migrations are an explicit, separate step - they never run on application
startup (ADR-0013). Run this against the same `.env` values the compose
stack uses (`db` is reachable at `localhost:5433` from the host, or `db:5432`
from inside another container).

### 5. Verify

```bash
curl http://localhost:8000/health
```

A healthy response looks like:

```json
{"status": "ok", "database": "ok", "pgvector": "available"}
```

## Checks

One command runs lint, type-check, and tests:

```bash
python scripts/check.py
```

Runs `ruff check`, `mypy` (strict, over `src/`), then `pytest`. Integration
tests (marker `integration`) require a live database (`docker compose up -d`
+ `alembic upgrade head`) and are excluded from the default `pytest` run;
run them explicitly with `pytest -m integration`.

### Pre-commit hooks (one-time setup)

Right after `pip install -e ".[dev]"`, install the git hooks for both stages
used by `.pre-commit-config.yaml`:

```bash
pre-commit install --install-hooks
pre-commit install --hook-type pre-push
```

(equivalently, in one call: `pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push`)

Commits then automatically get the hygiene hooks, `ruff check`, and strict
`mypy` - the same checks `scripts/check.py` and CI run, so nothing that would
fail CI reaches a commit. Pushes additionally run the DB-free unit test
suite. Integration tests stay manual/CI-only, since they need a live database:
`docker compose up -d db` + `alembic upgrade head` + `pytest -m integration`.

Run everything on demand (e.g. first-time setup on an existing clone, or to
check CI parity) with:

```bash
pre-commit run --all-files
```

## Status

Sprint 001 ("Foundation to first real document") is in progress. See
`docs/planning/CURRENT_STATUS.md` for what is implemented today and
`docs/planning/sprints/SPRINT_001.md` for the full task breakdown.

## More

Full documentation: [docs/README.md](docs/README.md). There is no
`docs/reference/WORKFLOWS.md` yet - this README is the interim source of
truth for setup/run commands until Sprint 001 task S001-T014 delivers the
complete workflow guide (covering migrations, source seeding, and running one
processing cycle manually, none of which exist yet).
