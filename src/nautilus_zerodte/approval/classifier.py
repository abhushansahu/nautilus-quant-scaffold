from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from nautilus_zerodte.models.enums import ActorKind
from nautilus_zerodte.models.trade_intent import TradeIntent


class ApprovalThresholds(BaseModel):
    """Thresholds for routing intents to human vs automation approval."""

    model_config = ConfigDict(frozen=True)

    human_notional_threshold: float = 10_000.0
    human_edge_bps_threshold: float = 50.0


def classify_intent(intent: TradeIntent, thresholds: ApprovalThresholds) -> ActorKind:
    """Route large or high-edge trades to human approval; otherwise automation."""
    if intent.edge_after_cost_bps >= thresholds.human_edge_bps_threshold:
        return ActorKind.HUMAN
    notional = intent.rationale.get("notional") or intent.rationale.get("net_debit")
    if notional is not None and float(notional) >= thresholds.human_notional_threshold:
        return ActorKind.HUMAN
    return ActorKind.AUTOMATION
