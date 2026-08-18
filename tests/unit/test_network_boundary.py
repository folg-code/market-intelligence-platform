"""Network I/O stays in the adapter layer (S001-T012).

Statically inspects every module under ``src/moj_projekt`` except
``ingestion/`` and fails if any of it imports ``httpx`` or ``feedparser``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import moj_projekt

FORBIDDEN = {"httpx", "feedparser"}


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


def test_httpx_and_feedparser_are_confined_to_ingestion() -> None:
    src_root = Path(moj_projekt.__file__).resolve().parent
    violations: dict[str, set[str]] = {}
    for path in src_root.rglob("*.py"):
        if "ingestion" in path.parts:
            continue
        imported = _imported_top_level_modules(path) & FORBIDDEN
        if imported:
            violations[str(path)] = imported

    assert not violations, (
        "httpx/feedparser must stay in ingestion/ (network confined to the "
        f"adapter layer): {violations}"
    )
