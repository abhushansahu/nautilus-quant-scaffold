from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class SpreadStructure:
    """Venue-neutral selected spread structure ready for order submission."""

    spread_instrument_id: str
    low_strike: float
    high_strike: float
    edge_after_cost_bps: float
    liquidity_score: float
    leg_instrument_ids: tuple[str, ...] = ()
    rationale: dict[str, Any] = field(default_factory=dict)


class StructureSelector(Protocol):
    """Select a vertical spread structure from an option chain snapshot."""

    def select_from_chain(
        self,
        option_chain_slice,
        *,
        strike_width: int,
        min_edge_after_cost_bps: float,
        min_liquidity_score: float,
    ) -> SpreadStructure | None: ...
