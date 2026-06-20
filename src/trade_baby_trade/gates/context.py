from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from trade_baby_trade.models.enums import RegimeTag
from trade_baby_trade.models.risk import RiskPolicy


class GateContext(BaseModel):
    """Immutable snapshot of cross-cutting gate inputs for pure evaluation."""

    model_config = ConfigDict(frozen=True)

    regime_tag: RegimeTag = RegimeTag.UNKNOWN
    session_allows_entry: bool = False
    flatten_signal: bool = False
    risk_policy: RiskPolicy = Field(default_factory=RiskPolicy)
    risk_policy_version: str = "default"

    min_edge_after_cost_bps: float = 0.0
    min_liquidity_score: float = 0.0
    blocked_regimes: frozenset[RegimeTag] = Field(default_factory=frozenset)

    trading_state_active: bool = True
    underlying_quote_fresh: bool = False
    chain_snapshot_fresh: bool = False
    daily_loss_breached: bool = False
    feed_healthy: bool = True
    require_chain_snapshot: bool = True
