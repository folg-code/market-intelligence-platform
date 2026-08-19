"""extraction/ imports no infrastructure (S002-T007).

Statically inspects every module under ``moj_projekt.extraction`` and fails
if any of it imports SQLAlchemy, httpx, or the Anthropic SDK - same style
as ``tests/unit/test_domain_boundary.py``.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import moj_projekt.extraction as extraction_package

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
                modules.add(alias.name.split(".", maxsplit=1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module.split(".", maxsplit=1)[0])
    return modules


def _extraction_module_files() -> list[Path]:
    extraction_dir = Path(extraction_package.__file__).parent
    return sorted(path for path in extraction_dir.rglob("*.py"))


def test_extraction_source_imports_no_infrastructure_modules() -> None:
    violations: dict[str, set[str]] = {}
    for path in _extraction_module_files():
        imported = _imported_top_level_modules(path) & FORBIDDEN_TOP_LEVEL_MODULES
        if imported:
            violations[str(path)] = imported

    assert not violations, (
        "extraction/ must not import infrastructure modules "
        f"(S002-T007, ADR-0002): {violations}"
    )


def test_importing_extraction_does_not_load_infrastructure_at_runtime() -> None:
    """AST isolation is not enough: ``from moj_projekt.llm.artifacts import ...``
    still executes ``llm/__init__.py``. A subprocess proves the SDK stays cold.
    """
    script = (
        "import sys\n"
        "import moj_projekt.extraction  # noqa: F401\n"
        "forbidden = {'anthropic', 'httpx', 'sqlalchemy'}\n"
        "loaded = sorted(\n"
        "    {name.split('.', 1)[0] for name in sys.modules\n"
        "     if name.split('.', 1)[0] in forbidden}\n"
        ")\n"
        "assert not loaded, loaded\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_extraction_does_not_construct_event_outside_the_service() -> None:
    """The validator judges; only the service constructs Event, on accepted."""
    for path in _extraction_module_files():
        if path.name == "service.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "Event":
                pytest_fail = f"{path} constructs Event at line {node.lineno}"
                raise AssertionError(pytest_fail)
            if isinstance(func, ast.Attribute) and func.attr == "Event":
                raise AssertionError(f"{path} constructs Event at line {node.lineno}")


def test_extraction_does_not_read_the_wall_clock() -> None:
    """``clock.now()`` is injected; ``datetime.now()`` / ``utcnow()`` are not."""
    for path in _extraction_module_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr not in {"now", "utcnow"}:
                continue
            if _is_datetime_clock_call(func):
                raise AssertionError(
                    f"{path} calls datetime.{func.attr}() at line {node.lineno}; "
                    "extraction must use an injected Clock"
                )


def _is_datetime_clock_call(func: ast.Attribute) -> bool:
    value = func.value
    if isinstance(value, ast.Name) and value.id == "datetime":
        return True
    return isinstance(value, ast.Attribute) and value.attr == "datetime"
