from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class LearningRecord(BaseModel):
    """PnL attribution record — theta/gamma/vega, commission, slippage, edge comparison."""

    model_config = ConfigDict(frozen=True)

    record_id: UUID = Field(default_factory=uuid4)
    intent_id: UUID
    order_id: str | None = None
    realized_pnl: Decimal = Decimal("0")
    theta_pnl: Decimal = Decimal("0")
    gamma_pnl: Decimal = Decimal("0")
    vega_pnl: Decimal = Decimal("0")
    slippage_bps: float = 0.0
    commission: Decimal = Decimal("0")
    edge_predicted_bps: float = 0.0
    edge_realized_bps: float = 0.0
    features: dict[str, Any] = Field(default_factory=dict)
