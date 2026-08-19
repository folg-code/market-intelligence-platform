"""Suite-wide fixtures.

Unit tests must not inherit ambient ``POSTGRES_*`` values from the shell or
from a dotenv pytest plugin that loaded a local ``.env``. Integration tests
still need those variables to reach the compose database.
"""

from __future__ import annotations

import os

import pytest

_POSTGRES_PREFIX = "POSTGRES_"


def _is_integration_test(request: pytest.FixtureRequest) -> bool:
    if request.node.get_closest_marker("integration") is not None:
        return True
    return "integration" in request.path.parts


@pytest.fixture(autouse=True)
def _clear_postgres_env_for_unit_tests(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if _is_integration_test(request):
        return
    for name in list(os.environ):
        if name.startswith(_POSTGRES_PREFIX):
            monkeypatch.delenv(name, raising=False)
