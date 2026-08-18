"""Enforces root CLAUDE.md: "Domain code imports no infrastructure."

Statically inspects every module under ``moj_projekt.domain`` and fails if
any of it imports SQLAlchemy, httpx, or the Anthropic SDK - or any other
non-stdlib infrastructure package, so the boundary can't quietly widen.
Uses the AST rather than importing the modules, so this test does not
itself need a database, an HTTP client, or the Anthropic SDK to run.
"""

from __future__ import annotations

import ast
from pathlib import Path

import moj_projekt.domain as domain_package

FORBIDDEN_TOP_LEVEL_MODULES = {
    "sqlalchemy",
    "alembic",
    "psycopg",
    "pgvector",
    "httpx",
    "anthropic",
    "fastapi",
    "uvicorn",
    "apscheduler",
    "feedparser",
}


def _imported_top_level_modules(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def _domain_module_files() -> list[Path]:
    domain_dir = Path(domain_package.__file__).parent
    return sorted(domain_dir.rglob("*.py"))


def test_domain_source_imports_no_infrastructure_modules() -> None:
    violations: dict[str, set[str]] = {}
    for path in _domain_module_files():
        imported = _imported_top_level_modules(path) & FORBIDDEN_TOP_LEVEL_MODULES
        if imported:
            violations[str(path)] = imported

    assert not violations, (
        "domain/ must not import infrastructure modules (root CLAUDE.md): "
        f"{violations}"
    )
