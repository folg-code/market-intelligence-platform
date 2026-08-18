"""The processing cycle's ordered stages (ADR-0004;
``ARCHITECTURE_FOUNDATIONS.md`` section 4): ingest, extract, narratives,
evidence, state, alerts - in that fixed order, every cycle.

:data:`DEFAULT_STAGES` is a plain ordered sequence of :class:`Stage`, not
branching logic keyed by name - :func:`moj_projekt.cycle.run_cycle.run_cycle`
iterates it uniformly. Production replaces the ingest ``run`` callable via
:func:`moj_projekt.cycle.ingest.build_production_stages`; the other five
stages stay passthrough until later tasks fill them in.

``Stage.run`` takes the in-progress :class:`~moj_projekt.domain.cycle_run.CycleRun`
and returns it (possibly with ``source_outcomes`` recorded) so ingest can
attach per-source results without the orchestration loop knowing about
sources. Failure of the stage itself is still signalled by raising.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from moj_projekt.domain.cycle_run import CycleRun

__all__ = ["Stage", "DEFAULT_STAGES"]


@dataclass(frozen=True, slots=True)
class Stage:
    """One named step of the processing cycle.

    ``run`` receives the in-progress CycleRun and returns it. It signals
    stage-level failure only by raising, which
    :func:`~moj_projekt.cycle.run_cycle.run_cycle` catches and records as
    that stage's :class:`~moj_projekt.domain.cycle_run.StageOutcome`.
    Per-source ingest failures are *not* stage failures - they are written
    onto ``CycleRun.source_outcomes`` and the callable returns normally.
    """

    name: str
    run: Callable[[CycleRun], CycleRun]


def _passthrough(cycle_run: CycleRun) -> CycleRun:
    """A structurally-real placeholder stage body: no work, succeeds."""
    return cycle_run


DEFAULT_STAGES: Sequence[Stage] = (
    Stage("ingest", _passthrough),
    Stage("extract", _passthrough),
    Stage("narratives", _passthrough),
    Stage("evidence", _passthrough),
    Stage("state", _passthrough),
    Stage("alerts", _passthrough),
)
