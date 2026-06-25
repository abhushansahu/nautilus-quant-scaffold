from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from nautilus_zerodte.models.enums import RegimeTag


class TradeIntent(BaseModel):
    """Candidate trade decision before gate evaluation and order submit."""

    model_config = ConfigDict(frozen=True)

    intent_id: UUID = Field(default_factory=uuid4)
    strategy_id: str
    instrument_id: str
    edge_after_cost_bps: float = 0.0
    liquidity_score: float = 0.0
    regime_tag: RegimeTag = RegimeTag.UNKNOWN
    projected_greeks: dict[str, float] = Field(default_factory=dict)
    rationale: dict[str, Any] = Field(default_factory=dict)
