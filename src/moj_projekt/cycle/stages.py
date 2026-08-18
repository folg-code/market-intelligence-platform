"""The processing cycle's ordered stages (ADR-0004;
``ARCHITECTURE_FOUNDATIONS.md`` section 4): ingest, extract, narratives,
evidence, state, alerts - in that fixed order, every cycle.

:data:`DEFAULT_STAGES` is a plain ordered sequence of :class:`Stage`, not
branching logic keyed by name - :func:`moj_projekt.cycle.run_cycle.run_cycle`
iterates it uniformly, so adding real behaviour to one stage later (S001-T012
fills in "ingest" only; this task leaves all six as no-op placeholders) means
replacing that one ``Stage.run`` callable, not touching the orchestration
loop.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

__all__ = ["Stage", "DEFAULT_STAGES"]


@dataclass(frozen=True, slots=True)
class Stage:
    """One named step of the processing cycle.

    ``run`` takes no arguments and returns nothing; it signals failure only
    by raising, which :func:`~moj_projekt.cycle.run_cycle.run_cycle` catches
    and records as that stage's :class:`~moj_projekt.domain.cycle_run.StageOutcome`.
    """

    name: str
    run: Callable[[], None]


def _noop() -> None:
    """A structurally-real placeholder stage body: does nothing, succeeds.

    Out of scope for this task (S001-T011) is any real work inside a
    stage - every stage is this same no-op until a later task (S001-T012
    for "ingest") replaces one.
    """


DEFAULT_STAGES: Sequence[Stage] = (
    Stage("ingest", _noop),
    Stage("extract", _noop),
    Stage("narratives", _noop),
    Stage("evidence", _noop),
    Stage("state", _noop),
    Stage("alerts", _noop),
)
