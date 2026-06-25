"""MessageBus topics and payloads for cross-cutting actor context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from nautilus_zerodte.models.enums import RegimeTag
from nautilus_zerodte.models.trade_intent import TradeIntent

SESSION_PHASE_TOPIC = "data.session.phase"
REGIME_TAG_TOPIC = "data.regime.tag"
TRADE_INTENT_TOPIC = "data.trade.intent"
TRADE_INTENT_APPROVED_TOPIC = "data.trade.intent.approved"
TRADE_INTENT_REJECTED_TOPIC = "data.trade.intent.rejected"


@dataclass(frozen=True, slots=True)
class SessionPhaseSnapshot:
    allows_entry: bool
    session_phase: str
    minutes_to_expiry: int
    flatten_signal: bool


@dataclass(frozen=True, slots=True)
class RegimeTagSnapshot:
    regime_tag: str


@dataclass(frozen=True, slots=True)
class TradeIntentSnapshot:
    intent_id: str
    strategy_id: str
    instrument_id: str
    edge_after_cost_bps: float
    liquidity_score: float
    regime_tag: str
    projected_greeks: dict[str, float]
    rationale: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TradeIntentApprovedSnapshot:
    intent_id: str
    strategy_id: str
    instrument_id: str
    edge_after_cost_bps: float
    liquidity_score: float
    regime_tag: str
    projected_greeks: dict[str, float]
    rationale: dict[str, Any]
    actor_kind: str


@dataclass(frozen=True, slots=True)
class TradeIntentRejectedSnapshot:
    intent_id: str
    strategy_id: str
    reason: str


def trade_intent_to_snapshot(intent: TradeIntent) -> TradeIntentSnapshot:
    return TradeIntentSnapshot(
        intent_id=str(intent.intent_id),
        strategy_id=intent.strategy_id,
        instrument_id=intent.instrument_id,
        edge_after_cost_bps=intent.edge_after_cost_bps,
        liquidity_score=intent.liquidity_score,
        regime_tag=intent.regime_tag.value,
        projected_greeks=dict(intent.projected_greeks),
        rationale=dict(intent.rationale),
    )


def snapshot_to_trade_intent(snapshot: TradeIntentSnapshot) -> TradeIntent:
    return TradeIntent(
        intent_id=UUID(snapshot.intent_id),
        strategy_id=snapshot.strategy_id,
        instrument_id=snapshot.instrument_id,
        edge_after_cost_bps=snapshot.edge_after_cost_bps,
        liquidity_score=snapshot.liquidity_score,
        regime_tag=RegimeTag(snapshot.regime_tag),
        projected_greeks=dict(snapshot.projected_greeks),
        rationale=dict(snapshot.rationale),
    )


def approved_snapshot_to_trade_intent(snapshot: TradeIntentApprovedSnapshot) -> TradeIntent:
    return TradeIntent(
        intent_id=UUID(snapshot.intent_id),
        strategy_id=snapshot.strategy_id,
        instrument_id=snapshot.instrument_id,
        edge_after_cost_bps=snapshot.edge_after_cost_bps,
        liquidity_score=snapshot.liquidity_score,
        regime_tag=RegimeTag(snapshot.regime_tag),
        projected_greeks=dict(snapshot.projected_greeks),
        rationale=dict(snapshot.rationale),
    )
