# moj-projekt

Market Intelligence Platform - evidence-backed market narrative intelligence.
See `docs/README.md` for the full documentation set.

The operator's path from clone to a stored Document, including PowerShell vs
bash, is `docs/reference/WORKFLOWS.md`. Do not treat this README as a second
copy of those commands.

## Quickstart

Python 3.11+, Docker Desktop, then:

1. `python -m venv .venv` and activate (`.venv\Scripts\Activate.ps1` on
   Windows, `source .venv/bin/activate` on macOS/Linux).
2. `pip install -e ".[dev]"`
3. `pre-commit install --install-hooks` and
   `pre-commit install --hook-type pre-push`
4. Copy `.env.example` to `.env` (`Copy-Item` on PowerShell, `cp` on bash).
   Host-side commands use `localhost:5433`; the `app` container still uses
   `db:5432`.
5. `docker compose up -d` then `alembic upgrade head`
6. `python -m moj_projekt.persistence.seed_sources`
7. `python -m moj_projekt.cycle.run_once`

`GET http://localhost:8000/health` should report `database: ok` and
`pgvector: available`. The cycle writes Documents from the live Bloomberg
Markets RSS feed; Reuters/AP seed URLs fail in isolation and do not fail
the cycle.

## Checks

`python scripts/check.py` runs `ruff check`, strict `mypy` over `src/`, then
the unit suite. Default `pytest` excludes `integration`.

Integration tests need the compose database already migrated:

```text
python -m pytest -m "integration and not network"
```

Live RSS is marked `network` (and `integration`); it needs outbound HTTP and
is excluded from CI. See `WORKFLOWS.md` for the exact commands.

CI (`.github/workflows/ci.yml`) runs lint, type-check, and unit + integration
(`pytest -m "not network"`) on every push/PR into `main` and `sprint/**`.
Local pre-commit mirrors the DB-free subset: commit gets hygiene + ruff +
mypy; push gets the unit suite.

## Status

Sprint 001 ("Foundation to first real document") is in progress. See
`docs/planning/CURRENT_STATUS.md` for what is implemented today and
`docs/planning/sprints/SPRINT_001.md` for the full task breakdown.

## More

Full documentation: [docs/README.md](docs/README.md).
