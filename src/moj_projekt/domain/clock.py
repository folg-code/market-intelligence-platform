"""``Clock`` - the injected source of "now" (root ``CLAUDE.md``: "The clock is
injected. No ``datetime.now()``/``utcnow()`` in domain or cycle code; the
pipeline is time-sensitive and must be testable.").

Pure/stdlib-only, so it is fine to live in ``domain/`` under the
no-infrastructure-import rule (there is nothing here to forbid). Every place
that would otherwise call ``datetime.now()``/``datetime.utcnow()`` in cycle
code takes a :class:`Clock` and calls :meth:`Clock.now` instead - this is
what lets :func:`moj_projekt.cycle.run_cycle.run_cycle` be exercised in a
unit test with a fake clock returning fixed/incrementing timestamps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

__all__ = ["Clock", "SystemClock"]


class Clock(Protocol):
    """Something that can report the current time."""

    def now(self) -> datetime:
        """Return the current time as a UTC-aware ``datetime``."""
        ...


class SystemClock:
    """The real :class:`Clock`, backed by the system clock.

    The only place in the codebase allowed to call ``datetime.now()``
    directly - every other call site takes a ``Clock`` and asks it instead.
    """

    def now(self) -> datetime:
        return datetime.now(UTC)
