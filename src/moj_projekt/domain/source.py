"""``Source`` - an external data origin with an explicit trust tier
(DOMAIN_MODEL.md section 3, "Ingestion").

Pure domain representation: no persistence concern. The stable source key
(e.g. ``fed_fomc``, ``bls``, ``sec_edgar``) is the identity - not a
surrogate/auto-increment id.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from moj_projekt.domain.enums import SourceTier

__all__ = ["Source"]


@dataclass(frozen=True, slots=True)
class Source:
    """An external data origin (DOMAIN_MODEL.md section 3).

    ``key`` is the stable identity. ``publisher`` is the independence
    grouping key: sources sharing an originating publisher are not
    independent of each other (DOMAIN_MODEL.md invariant).
    """

    key: str
    name: str
    source_type: str
    tier: SourceTier
    publisher: str
    endpoint_config: Mapping[str, Any] = field(default_factory=dict)
    active: bool = True

    def __post_init__(self) -> None:
        for attr_name in ("key", "name", "source_type", "publisher"):
            value = getattr(self, attr_name)
            if not value.strip():
                raise ValueError(f"Source.{attr_name} must not be empty")
