"""Composite quality-gate command: lint, type-check, and test the project.

Usage::

    python scripts/check.py

Runs, in order: ruff (lint), mypy (strict type-check over ``src/``), pytest
(tests). Stops at the first failing step and returns its exit code, so the
same command is used locally and in CI (S001-T002).
"""

from __future__ import annotations

import subprocess
import sys

STEPS: list[list[str]] = [
    [sys.executable, "-m", "ruff", "check", "."],
    [sys.executable, "-m", "mypy", "src"],
    [sys.executable, "-m", "pytest"],
]


def main() -> int:
    for step in STEPS:
        print(f"$ {' '.join(step)}")
        result = subprocess.run(step)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
