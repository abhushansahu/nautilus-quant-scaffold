from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from nautilus_trader.common.actor import Actor
from nautilus_trader.config import ActorConfig

from nautilus_zerodte.actors.data_types import (
    TRADE_INTENT_APPROVED_TOPIC,
    TRADE_INTENT_REJECTED_TOPIC,
    TRADE_INTENT_TOPIC,
    TradeIntentApprovedSnapshot,
    TradeIntentRejectedSnapshot,
    TradeIntentSnapshot,
    snapshot_to_trade_intent,
    trade_intent_to_snapshot,
)
from nautilus_zerodte.approval.classifier import ApprovalThresholds, classify_intent
from nautilus_zerodte.approval.handlers import AutomationHandler, HumanApprovalHandler
from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.models.diversification import DiversificationPolicy, select_intents
from nautilus_zerodte.models.enums import ActorKind, GateStage
from nautilus_zerodte.models.trade_intent import TradeIntent


class SelectorActorConfig(ActorConfig, frozen=True):
    journal_path: str = "runs/latest.jsonl"
    diversification: dict | None = None
    approval: dict | None = None
    batch_interval_ms: int = 100


class SelectorActor(Actor):
    """Collects TradeIntents from N strategies, applies TopN, routes approval."""

    def __init__(self, config: SelectorActorConfig) -> None:
        super().__init__(config)
        self._journal = Journal(Path(config.journal_path))
        policy_data = config.diversification or {}
        self._policy = DiversificationPolicy.model_validate(policy_data)
        approval_data = config.approval or {}
        self._approval_thresholds = ApprovalThresholds.model_validate(approval_data)
        self._human_handler = HumanApprovalHandler(self._journal)
        self._automation_handler = AutomationHandler(self._journal)
        self._buffer: list[TradeIntent] = []
        self._finalize_alert = "selector_finalize"

    def on_start(self) -> None:
        self.msgbus.subscribe(topic=TRADE_INTENT_TOPIC, handler=self._on_trade_intent)

    def on_stop(self) -> None:
        self.msgbus.unsubscribe(topic=TRADE_INTENT_TOPIC, handler=self._on_trade_intent)
        if self._finalize_alert in self.clock.timer_names:
            self.clock.cancel_timer(self._finalize_alert)
        if self._buffer:
            self.finalize()

    def collect(self, intent: TradeIntent) -> None:
        """Buffer a candidate intent (also invoked from MessageBus handler)."""
        self._buffer.append(intent)
        self._schedule_finalize()

    def finalize(self) -> list[TradeIntent]:
        """Apply diversification policy and run approval on the current buffer."""
        if not self._buffer:
            return []
        intents = list(self._buffer)
        self._buffer.clear()
        approved, rejected = select_intents(intents, self._policy)
        self._journal_rejected(rejected)
        routed: list[TradeIntent] = []
        for intent in approved:
            if self._route_approval(intent):
                routed.append(intent)
        return routed

    def _on_trade_intent(self, msg: TradeIntentSnapshot) -> None:
        self.collect(snapshot_to_trade_intent(msg))

    def _schedule_finalize(self) -> None:
        alert_time = self.clock.utc_now() + timedelta(milliseconds=self.config.batch_interval_ms)
        self.clock.set_time_alert(
            name=self._finalize_alert,
            alert_time=alert_time,
            callback=self._on_finalize_alert,
            override=True,
        )

    def _on_finalize_alert(self, _event) -> None:  # noqa: ANN001
        self.finalize()

    def _journal_rejected(self, rejected: list[TradeIntent]) -> None:
        for intent in rejected:
            self._journal.record(
                GateStage.LIFECYCLE,
                ref_id=intent.intent_id,
                payload={
                    "event": "SELECTOR_REJECTED",
                    "intent_id": str(intent.intent_id),
                    "strategy_id": intent.strategy_id,
                    "instrument_id": intent.instrument_id,
                    "edge_after_cost_bps": intent.edge_after_cost_bps,
                },
                strategy_id=intent.strategy_id,
            )
            self.msgbus.publish(
                TRADE_INTENT_REJECTED_TOPIC,
                TradeIntentRejectedSnapshot(
                    intent_id=str(intent.intent_id),
                    strategy_id=intent.strategy_id,
                    reason="diversification_cap",
                ),
            )

    def _route_approval(self, intent: TradeIntent) -> bool:
        actor_kind = classify_intent(intent, self._approval_thresholds)
        self._journal.record(
            GateStage.LIFECYCLE,
            ref_id=intent.intent_id,
            payload={
                "event": "SELECTOR_APPROVED",
                "intent_id": str(intent.intent_id),
                "strategy_id": intent.strategy_id,
                "instrument_id": intent.instrument_id,
                "edge_after_cost_bps": intent.edge_after_cost_bps,
                "actor_kind": actor_kind.value,
            },
            strategy_id=intent.strategy_id,
        )
        if actor_kind is ActorKind.HUMAN:
            approved = self._human_handler.handle(intent, actor_kind=actor_kind)
        else:
            approved = self._automation_handler.handle(intent, actor_kind=actor_kind)
        if not approved:
            return False
        snapshot = trade_intent_to_snapshot(intent)
        self.msgbus.publish(
            TRADE_INTENT_APPROVED_TOPIC,
            TradeIntentApprovedSnapshot(
                intent_id=snapshot.intent_id,
                strategy_id=snapshot.strategy_id,
                instrument_id=snapshot.instrument_id,
                edge_after_cost_bps=snapshot.edge_after_cost_bps,
                liquidity_score=snapshot.liquidity_score,
                regime_tag=snapshot.regime_tag,
                projected_greeks=snapshot.projected_greeks,
                rationale=snapshot.rationale,
                actor_kind=actor_kind.value,
            ),
        )
        return True
