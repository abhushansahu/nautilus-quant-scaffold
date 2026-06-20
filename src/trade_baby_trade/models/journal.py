from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from trade_baby_trade.models.enums import GateStage


class JournalEntry(BaseModel):
    """Append-only audit record — cross-cutting across gates, orders, and lifecycle."""

    model_config = ConfigDict(frozen=True)

    entry_id: UUID = Field(default_factory=uuid4)
    ts: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    stage: GateStage
    ref_id: UUID | None = None
    strategy_id: str | None = None
    level: str = "INFO"
    payload: dict[str, Any] = Field(default_factory=dict)
