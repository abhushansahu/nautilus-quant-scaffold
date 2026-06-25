from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChainEvaluationContext:
    """Normalized chain signal inputs for build_intent — live slice or backtest synthetic."""

    instrument_id: str
    underlying_mid: float
    atm_strike: float
    edge_after_cost_bps: float
    liquidity_score: float
    ts_event: int
    spread_instrument_id: str | None = None
    rationale: dict[str, Any] = field(default_factory=dict)
