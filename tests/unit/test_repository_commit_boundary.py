"""Repositories flush; they do not commit (S002-T002, D-S002-04 clause 6)."""

from __future__ import annotations

import ast
from pathlib import Path

import moj_projekt.persistence as persistence_package


def _repository_files() -> list[Path]:
    persistence_dir = Path(persistence_package.__file__).parent
    return sorted(
        path
        for path in persistence_dir.glob("*_repository.py")
        if path.name != "unit_of_work.py"
    )


def _calls_commit(source_path: Path) -> list[int]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "commit":
            lines.append(node.lineno)
    return lines


def test_no_repository_implementation_calls_commit() -> None:
    files = _repository_files()
    assert files, "expected persistence/*_repository.py files"

    violations: dict[str, list[int]] = {}
    for path in files:
        lines = _calls_commit(path)
        if lines:
            violations[path.name] = lines

    assert not violations, (
        "repository implementations must flush, not commit "
        f"(S002-T002): {violations}"
    )
