# moj-projekt

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Uruchomienie

```bash
python -m moj_projekt.main
```

## Checks

One command runs lint, type-check, and tests (S001-T002). See
`docs/reference/WORKFLOWS.md` for the full setup/run guide once it exists.

```bash
python scripts/check.py
```
