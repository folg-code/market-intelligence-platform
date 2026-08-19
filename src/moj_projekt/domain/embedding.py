"""``IdentityEmbedding`` - the derived vector descriptor for a Narrative's
identity text (DOMAIN_MODEL.md section 4, ADR-0014).

This is a pure descriptor: model name, model version, and the vector itself.
It carries no storage concern (no column type, no dimension constraint) -
that belongs to the persistence layer (S001-T008). The embedding is always
derived, recomputable, and never authoritative: a Narrative with no
``IdentityEmbedding`` is still fully valid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["IdentityEmbedding"]


@dataclass(frozen=True, slots=True)
class IdentityEmbedding:
    """The embedding of one Narrative's identity text at one point in time.

    ``embedding_model`` and ``embedding_version`` identify what produced the
    vector, so a later model change is auditable rather than silent.
    """

    embedding_model: str
    embedding_version: str
    vector: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.embedding_model.strip():
            raise ValueError("IdentityEmbedding.embedding_model must not be empty")
        if not self.embedding_version.strip():
            raise ValueError("IdentityEmbedding.embedding_version must not be empty")
        if len(self.vector) == 0:
            raise ValueError("IdentityEmbedding.vector must not be empty")
        for component in self.vector:
            if not math.isfinite(component):
                raise ValueError(
                    "IdentityEmbedding.vector must contain only finite float values"
                )
