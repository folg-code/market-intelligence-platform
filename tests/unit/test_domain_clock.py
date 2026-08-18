"""Unit tests for Clock/SystemClock (S001-T011) - no database."""

from __future__ import annotations

from datetime import UTC, datetime

from moj_projekt.domain.clock import Clock, SystemClock


def test_system_clock_now_is_utc_aware_and_close_to_wall_clock() -> None:
    clock: Clock = SystemClock()
    before = datetime.now(UTC)

    reported = clock.now()

    after = datetime.now(UTC)
    assert reported.tzinfo is not None
    assert before <= reported <= after
