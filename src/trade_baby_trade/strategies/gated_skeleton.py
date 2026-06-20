from __future__ import annotations

from pathlib import Path

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy

from trade_baby_trade.actors.data_types import (
    REGIME_TAG_TOPIC,
    SESSION_PHASE_TOPIC,
    RegimeTagSnapshot,
    SessionPhaseSnapshot,
)
from trade_baby_trade.gates.context import GateContext
from trade_baby_trade.gates.evaluator import evaluate_pre_greek
from trade_baby_trade.journal.service import Journal
from trade_baby_trade.models.enums import GateStage, RegimeTag
from trade_baby_trade.models.risk import RiskPolicy
from trade_baby_trade.models.trade_intent import TradeIntent


class GatedSkeletonStrategyConfig(StrategyConfig, frozen=True):
    strategy_id: str = "gated-skeleton-001"
    journal_path: str = "runs/latest.jsonl"
    underlying: str = "SPY.NYSE"
    min_edge_after_cost_bps: float = 5.0
    min_liquidity_score: float = 0.5
    blocked_regimes: tuple[str, ...] = ("PIN_RISK",)
    require_chain_snapshot: bool = True
    max_underlying_quote_age_secs: float = 30.0
    risk_policy: dict | None = None


class GatedSkeletonStrategy(Strategy):
    """Phase 2 stub — evaluates pre-greek gates on first quote tick; no orders."""

    def __init__(self, config: GatedSkeletonStrategyConfig) -> None:
        super().__init__(config)
        self._journal = Journal(Path(config.journal_path))
        self._strategy_id = config.strategy_id
        risk_data = config.risk_policy or {}
        self._risk_policy = RiskPolicy.model_validate(risk_data)
        self._session_allows_entry = False
        self._session_received = False
        self._regime_tag = RegimeTag.UNKNOWN
        self._regime_received = False
        self._evaluated = False
        self._pending_tick = None

    def on_start(self) -> None:
        self._journal.record(
            GateStage.LIFECYCLE,
            payload={"event": "STRATEGY_START", "underlying": self.config.underlying},
            strategy_id=self._strategy_id,
        )
        self.msgbus.subscribe(topic=SESSION_PHASE_TOPIC, handler=self._on_session_phase)
        self.msgbus.subscribe(topic=REGIME_TAG_TOPIC, handler=self._on_regime_tag)
        self.subscribe_quote_ticks(InstrumentId.from_str(self.config.underlying))

    def on_stop(self) -> None:
        self.msgbus.unsubscribe(topic=SESSION_PHASE_TOPIC, handler=self._on_session_phase)
        self.msgbus.unsubscribe(topic=REGIME_TAG_TOPIC, handler=self._on_regime_tag)
        self._journal.record(
            GateStage.LIFECYCLE,
            payload={"event": "STRATEGY_STOP", "underlying": self.config.underlying},
            strategy_id=self._strategy_id,
        )

    def _on_session_phase(self, msg: SessionPhaseSnapshot) -> None:
        self._session_allows_entry = msg.allows_entry
        self._session_received = True
        self._maybe_evaluate_gates()

    def _on_regime_tag(self, msg: RegimeTagSnapshot) -> None:
        self._regime_tag = RegimeTag(msg.regime_tag)
        self._regime_received = True
        self._maybe_evaluate_gates()

    def on_quote_tick(self, tick) -> None:  # noqa: ANN001
        self._pending_tick = tick
        self._maybe_evaluate_gates()

    def _maybe_evaluate_gates(self) -> None:
        if (
            self._evaluated
            or not self._session_received
            or not self._regime_received
            or self._pending_tick is None
        ):
            return
        self._evaluated = True
        self._evaluate_gates(self._pending_tick)

    def _evaluate_gates(self, tick) -> None:  # noqa: ANN001
        intent = TradeIntent(
            strategy_id=self._strategy_id,
            instrument_id=str(tick.instrument_id),
            edge_after_cost_bps=max(self.config.min_edge_after_cost_bps, 10.0),
            liquidity_score=max(self.config.min_liquidity_score, 0.8),
            regime_tag=self._regime_tag,
        )
        context = GateContext(
            regime_tag=self._regime_tag,
            session_allows_entry=self._session_allows_entry,
            risk_policy=self._risk_policy,
            risk_policy_version=self._risk_policy.version,
            min_edge_after_cost_bps=self.config.min_edge_after_cost_bps,
            min_liquidity_score=self.config.min_liquidity_score,
            blocked_regimes=frozenset(RegimeTag(r) for r in self.config.blocked_regimes),
            underlying_quote_fresh=True,
            chain_snapshot_fresh=not self.config.require_chain_snapshot,
            require_chain_snapshot=self.config.require_chain_snapshot,
        )
        result = evaluate_pre_greek(intent, context)
        if result.passed:
            self._journal.record(
                GateStage.LIFECYCLE,
                ref_id=intent.intent_id,
                payload={"event": "GATES_PASSED", "intent_id": str(intent.intent_id)},
                strategy_id=self._strategy_id,
            )
            return
        assert result.failed_stage is not None
        self._journal.record(
            result.failed_stage,
            ref_id=intent.intent_id,
            payload={
                "event": "GATE_REJECT",
                "breached_rules": result.breached_rules,
                "intent_id": str(intent.intent_id),
            },
            strategy_id=self._strategy_id,
        )
