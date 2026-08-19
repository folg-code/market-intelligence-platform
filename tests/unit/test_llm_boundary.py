"""Anthropic SDK stays inside ``llm/`` (S002-T006).

Statically inspects every module under ``src/moj_projekt`` except ``llm/``
and fails if any of it imports ``anthropic``. Same style as
``test_domain_boundary.py`` / ``test_network_boundary.py``: AST, not import.
"""

from __future__ import annotations

import ast
from pathlib import Path

import moj_projekt

FORBIDDEN = {"anthropic"}


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


def test_anthropic_sdk_is_confined_to_llm() -> None:
    src_root = Path(moj_projekt.__file__).resolve().parent
    violations: dict[str, set[str]] = {}
    for path in src_root.rglob("*.py"):
        if "llm" in path.parts:
            continue
        imported = _imported_top_level_modules(path) & FORBIDDEN
        if imported:
            violations[str(path)] = imported

    assert not violations, (
        "anthropic must stay in llm/ (the only module allowed to talk to "
        f"the Anthropic SDK): {violations}"
    )
