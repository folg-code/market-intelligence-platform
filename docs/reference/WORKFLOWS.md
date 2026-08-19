# Engineering Workflows

How to set up and run this repo. This is the single source for setup,
compose, migrations, seeding, running one cycle, and running checks. Do not
duplicate those commands in `README.md` or root `CLAUDE.md`.

Commands below were executed on Windows PowerShell against this checkout.
Where PowerShell and bash differ, both forms are shown.

## 1. Prerequisites

- Python 3.11 or newer (`python --version`)
- Docker Desktop (or equivalent) with Compose v2
- Git

No Anthropic API key is needed yet: Sprint 001 does not call an LLM.

## 2. Clone to a stored Document

From a clone, this path produces at least one `documents` row. Later
sections repeat the same commands with more context.

### 2.1 Toolchain

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

One-time git hooks (hygiene + `ruff check` + strict `mypy` on commit;
DB-free unit tests on push):

```text
pre-commit install --install-hooks
pre-commit install --hook-type pre-push
```

### 2.2 Environment file

```powershell
Copy-Item .env.example .env
```

```bash
cp .env.example .env
```

Edit `.env` and set a real `POSTGRES_PASSWORD` if this is not a throwaway
local database. Host-side commands (migrations, seed, cycle, tests) use
`POSTGRES_HOST=localhost` and `POSTGRES_PORT=5433` from that file. The
`app` container still talks to `db:5432` because `compose.yaml` overrides
those two values.

### 2.3 Compose, migrate, seed

The app image does not contain `migrations/` or `alembic.ini`, so Alembic
and the Python entrypoints run on the host against the published db port.

```text
docker compose up -d
alembic upgrade head
python -m moj_projekt.persistence.seed_sources
```

`docker compose up -d` builds the `app` image on first run. Wait until
`docker compose ps` shows `db` healthy and `app` running before the next
steps.

### 2.4 Health

```powershell
Invoke-RestMethod http://localhost:8000/health
```

```bash
curl http://localhost:8000/health
```

A healthy response is `status=ok`, `database=ok`, `pgvector=available`.

### 2.5 One cycle, then a Document row

```text
python -m moj_projekt.cycle.run_once
```

Only `source_type=rss` has an adapter this sprint. Bloomberg Markets is
the live public feed; Reuters and AP seed URLs are not live public feeds
and are recorded as per-source failures without failing the cycle. Tier 1
official sources (Fed/FOMC, BLS, SEC) are skipped until their adapters
exist. Expect `bloomberg_markets: ok` and at least one `documents` row:

```text
docker compose exec db psql -U moj_projekt -d moj_projekt -c "SELECT source_key, count(*) FROM documents GROUP BY source_key;"
```

Re-running `run_once` is safe: Document dedupe is `ON CONFLICT DO NOTHING`,
and seed is idempotent.

## 3. What each command is for

| Command | What it does |
|---|---|
| `python -m venv .venv` then activate | Isolated interpreter |
| `pip install -e ".[dev]"` | Runtime + ruff/mypy/pytest/pre-commit |
| `pre-commit install --install-hooks` | Commit-stage hooks |
| `pre-commit install --hook-type pre-push` | Push-stage unit tests |
| `Copy-Item` / `cp` `.env.example` `.env` | Local secrets file (git-ignored) |
| `docker compose up -d` | `db` (PostgreSQL + pgvector on host port 5433) and `app` (FastAPI on 8000) |
| `alembic upgrade head` | Schema, including the `vector` extension. Never runs on app startup. |
| `python -m moj_projekt.persistence.seed_sources` | Idempotent MVP Source registry (six sources) |
| `Invoke-RestMethod` / `curl` `http://localhost:8000/health` | DB connectivity + pgvector availability |
| `python -m moj_projekt.cycle.run_once` | One processing cycle without waiting for APScheduler |
| `python scripts/check.py` | `ruff check`, strict `mypy` over `src/`, then unit tests |
| `python -m pytest` | Unit tests only (`addopts` excludes `integration`) |
| `python -m pytest -m "integration and not network"` | Integration tests; needs compose `db` + migrations |
| `python -m pytest -m network` | Live RSS feed; needs compose `db` + outbound HTTP |

The in-process scheduler also fires the same `run_once` path every 5 minutes
once `app` is up. Use the module entrypoint when you want one cycle now.

## 4. Checks and tests

Lint + type-check + unit tests (no database):

```text
python scripts/check.py
```

That is the same order CI uses for lint and type-check. Default `pytest`
(and therefore `scripts/check.py`) excludes the `integration` marker.
Unit tests autouse-clear ambient `POSTGRES_*` (shell export or a pytest dotenv plugin loading `.env`); integration tests still read those variables.

On-demand hook run (same commit-stage checks as a commit, against every
file):

```text
pre-commit run --all-files
```

Integration tests need a live PostgreSQL/pgvector. With the stack from
section 2 already up and migrated:

```text
python -m pytest -m "integration and not network"
```

`pytest -m integration` alone also selects the live-feed test, because that
test is marked both `integration` and `network`. Use `and not network`
unless you intend to hit Bloomberg's RSS endpoint.

Live feed (outbound HTTP to a third-party host; excluded from CI):

```text
python -m pytest -m network
```

## 5. CI

CI is `.github/workflows/ci.yml`. It runs on every push and pull request
into `main` and `sprint/**`: ruff, strict mypy, then unit + integration
against a `pgvector/pgvector:pg16` service. It writes a `.env` for Alembic
and integration tests (the `.env`-not-job-`env:` shape is no longer
load-bearing for unit-test isolation) and runs `pytest -o addopts="" -m "not network"`.

Local pre-commit is the subset that does not need a database: commit gets
hygiene + ruff + mypy; push gets the unit suite. Integration stays
manual / CI.

## 6. Troubleshooting

- **`alembic` / seed / `run_once` cannot connect.** Confirm `.env` has
  `POSTGRES_HOST=localhost` and `POSTGRES_PORT=5433`, and that
  `docker compose ps` shows `db` healthy on `0.0.0.0:5433->5432/tcp`.
- **`/health` is unreachable.** The `app` container is what listens on
  8000. `docker compose up -d` must include `app`, not only `db`.
- **Cycle prints Reuters/AP failures.** Expected this sprint; Bloomberg
  should still succeed and write Documents.
- **`run_once` prints `cycle skipped`.** Another CycleRun is `RUNNING`
  (the scheduler tick, or a previous cycle). Wait and retry.
- **Integration tests fail with a connection error.** Start `db`, apply
  migrations, and keep host port 5433 (the test fixtures assume that
  published port).
- **`python -m venv .venv` says Permission denied on Windows.** The
  existing `.venv` is in use. Skip this step if the venv is already there.
- **`pre-commit run --all-files` rewrites a file you did not edit.** The
  end-of-file-fixer walks the whole tree, including frozen historical docs.
  That is the hook doing its job, not a broken setup.

## 7. Out of scope here

No VPS deploy, backup/restore, or dashboard. No remaining source adapters
and no LLM calls. Schema for those later pieces already exists; the
commands above do not invoke them.

## 8. Update rule

Update this file when a command, port, entrypoint, or test marker
changes. Link to CI config rather than copying it.
