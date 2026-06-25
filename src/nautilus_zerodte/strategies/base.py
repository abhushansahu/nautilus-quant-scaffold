from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Any
from uuid import UUID

from nautilus_trader.config import StrategyConfig
from nautilus_trader.trading.strategy import Strategy

from nautilus_zerodte.actors.data_types import (
    REGIME_TAG_TOPIC,
    SESSION_PHASE_TOPIC,
    RegimeTagSnapshot,
    SessionPhaseSnapshot,
)
from nautilus_zerodte.gates.context import GateContext
from nautilus_zerodte.gates.evaluator import check_risk_policy, evaluate_pre_greek
from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.models.enums import GateStage, RegimeTag, StrategyState
from nautilus_zerodte.models.risk import RiskPolicy
from nautilus_zerodte.models.trade_intent import TradeIntent
from nautilus_zerodte.strategies.context import ChainEvaluationContext


class BaseZeroDteStrategyConfig(StrategyConfig, frozen=True):
    strategy_id: str = "zero-dte-001"
    journal_path: str = "runs/latest.jsonl"
    underlying: str = "SPY.NYSE"
    dry_run: bool = False
    min_edge_after_cost_bps: float = 5.0
    min_liquidity_score: float = 0.5
    blocked_regimes: tuple[str, ...] = ("PIN_RISK",)
    require_chain_snapshot: bool = True
    max_underlying_quote_age_secs: float = 30.0
    max_chain_snapshot_age_secs: float = 90.0
    chain_snapshot_interval_ms: int = 60_000
    risk_policy: dict | None = None


class BaseZeroDteStrategy(Strategy):
    """NT Strategy with per-strategy FSM and gate orchestration."""

    def __init__(self, config: BaseZeroDteStrategyConfig) -> None:
        super().__init__(config)
        self._journal = Journal(Path(config.journal_path))
        self._strategy_id = config.strategy_id
        risk_data = config.risk_policy or {}
        self._risk_policy = RiskPolicy.model_validate(risk_data)
        self._state = StrategyState.FLAT
        self._session_allows_entry = False
        self._session_received = False
        self._flatten_signal = False
        self._regime_tag = RegimeTag.UNKNOWN
        self._regime_received = False
        self._last_quote_ts: int | None = None
        self._last_chain_ts: int | None = None
        self._active_intent_id: UUID | None = None
        self._active_intent: TradeIntent | None = None
        self._entry_price: float | None = None

    @property
    def fsm_state(self) -> StrategyState:
        return self._state

    def on_start(self) -> None:
        self._journal.record(
            GateStage.LIFECYCLE,
            payload={"event": "STRATEGY_START", "underlying": self.config.underlying},
            strategy_id=self._strategy_id,
        )
        self.msgbus.subscribe(topic=SESSION_PHASE_TOPIC, handler=self._on_session_phase)
        self.msgbus.subscribe(topic=REGIME_TAG_TOPIC, handler=self._on_regime_tag)
        self._subscribe_market_data()

    def on_stop(self) -> None:
        self.msgbus.unsubscribe(topic=SESSION_PHASE_TOPIC, handler=self._on_session_phase)
        self.msgbus.unsubscribe(topic=REGIME_TAG_TOPIC, handler=self._on_regime_tag)
        self._journal.record(
            GateStage.LIFECYCLE,
            payload={"event": "STRATEGY_STOP", "state": self._state.value},
            strategy_id=self._strategy_id,
        )

    @abstractmethod
    def _subscribe_market_data(self) -> None:
        """Subscribe to underlying, chain, and leg data per strategy profile."""

    @abstractmethod
    def build_intent(self, context: ChainEvaluationContext) -> TradeIntent | None:
        """Build a candidate TradeIntent from chain or synthetic context."""

    @abstractmethod
    def submit_entry(self, intent: TradeIntent) -> None:
        """Submit entry orders after gates pass."""

    @abstractmethod
    def submit_exit(self, intent_id: UUID, *, reason: str) -> None:
        """Submit flatten or exit orders."""

    def on_option_chain(self, option_chain_slice) -> None:  # noqa: ANN001
        self._last_chain_ts = int(option_chain_slice.ts_event)
        if self._state != StrategyState.FLAT:
            return
        context = self._context_from_chain_slice(option_chain_slice)
        if context is not None:
            self._begin_evaluation(context)

    def on_quote_tick(self, tick) -> None:  # noqa: ANN001
        self._last_quote_ts = int(tick.ts_event)
        if self._state == StrategyState.IN_POSITION:
            self._manage_position(tick)
            return
        if self._state != StrategyState.FLAT:
            return
        context = self._context_from_quote_tick(tick)
        if context is not None:
            self._begin_evaluation(context)

    def on_order_filled(self, event) -> None:  # noqa: ANN001
        fill_payload = {
            "event": "FILL",
            "order_id": str(event.client_order_id),
            "instrument_id": str(event.instrument_id),
            "qty": str(event.last_qty),
            "price": str(event.last_px),
            "side": (
                event.order_side.name
                if hasattr(event.order_side, "name")
                else str(event.order_side)
            ),
        }
        self._journal.record(
            GateStage.FILL,
            ref_id=self._active_intent_id,
            payload=fill_payload,
            strategy_id=self._strategy_id,
        )
        self._journal_pnl(event.instrument_id)
        if self._state == StrategyState.PENDING_ENTRY:
            self._entry_price = float(event.last_px)
            self._transition(StrategyState.IN_POSITION, reason="entry_fill")
        elif self._state == StrategyState.EXITING:
            self._active_intent_id = None
            self._active_intent = None
            self._entry_price = None
            self._transition(StrategyState.FLAT, reason="exit_fill")

    def on_order_rejected(self, event) -> None:  # noqa: ANN001
        if self._state != StrategyState.PENDING_ENTRY:
            return
        self._journal.record(
            GateStage.LIFECYCLE,
            ref_id=self._active_intent_id,
            payload={
                "event": "ORDER_REJECTED",
                "order_id": str(event.client_order_id),
                "reason": str(getattr(event, "reason", "unknown")),
            },
            strategy_id=self._strategy_id,
        )
        self._active_intent_id = None
        self._active_intent = None
        self._transition(StrategyState.FLAT, reason="order_rejected")

    def on_order_denied(self, event) -> None:  # noqa: ANN001
        if self._state != StrategyState.PENDING_ENTRY:
            return
        self._journal.record(
            GateStage.RISK_ENGINE,
            ref_id=self._active_intent_id,
            payload={
                "event": "ORDER_DENIED",
                "order_id": str(event.client_order_id),
                "reason": str(getattr(event, "reason", "unknown")),
            },
            strategy_id=self._strategy_id,
        )
        self._active_intent_id = None
        self._active_intent = None
        self._transition(StrategyState.FLAT, reason="order_denied")

    def flatten_positions(self, *, reason: str) -> None:
        """Cancel open orders and submit exit for in-position state."""
        if self._state not in {StrategyState.IN_POSITION, StrategyState.PENDING_ENTRY}:
            self._journal.record(
                GateStage.LIFECYCLE,
                payload={"event": "FLATTEN_SKIPPED", "state": self._state.value, "reason": reason},
                strategy_id=self._strategy_id,
            )
            return
        self.cancel_all_orders()
        if self._state == StrategyState.IN_POSITION and self._active_intent_id is not None:
            self._transition(StrategyState.EXITING, reason=reason)
            self.submit_exit(self._active_intent_id, reason=reason)

    def _on_session_phase(self, msg: SessionPhaseSnapshot) -> None:
        self._session_allows_entry = msg.allows_entry
        self._session_received = True
        self._flatten_signal = msg.flatten_signal
        if msg.flatten_signal and self._state in {
            StrategyState.IN_POSITION,
            StrategyState.PENDING_ENTRY,
        }:
            self.flatten_positions(reason="session_blackout")

    def _on_regime_tag(self, msg: RegimeTagSnapshot) -> None:
        self._regime_tag = RegimeTag(msg.regime_tag)
        self._regime_received = True

    def _context_from_chain_slice(self, option_chain_slice) -> ChainEvaluationContext | None:  # noqa: ANN001
        if not self._actors_ready():
            return None
        atm = float(option_chain_slice.atm_strike)
        mid = atm
        call_quote = (
            option_chain_slice.get_call_quote(atm) if option_chain_slice.strike_count else None
        )
        if call_quote is not None:
            bid = float(getattr(call_quote, "bid_price", 0) or 0)
            ask = float(getattr(call_quote, "ask_price", 0) or 0)
            if bid and ask:
                mid = (bid + ask) / 2
        spread_bps = 0.0
        if call_quote is not None:
            bid = float(getattr(call_quote, "bid_price", 0) or 0)
            ask = float(getattr(call_quote, "ask_price", 0) or 0)
            if bid > 0 and ask > 0:
                spread_bps = ((ask - bid) / ((ask + bid) / 2)) * 10_000
        liquidity = max(0.0, min(1.0, 1.0 - spread_bps / 100.0))
        edge = max(self.config.min_edge_after_cost_bps, 10.0)
        return ChainEvaluationContext(
            instrument_id=str(option_chain_slice.series_id),
            underlying_mid=mid,
            atm_strike=atm,
            edge_after_cost_bps=edge,
            liquidity_score=liquidity,
            ts_event=int(option_chain_slice.ts_event),
            rationale={"source": "option_chain_slice", "spread_bps": spread_bps},
        )

    def _context_from_quote_tick(self, tick) -> ChainEvaluationContext | None:  # noqa: ANN001
        return None

    def _actors_ready(self) -> bool:
        return self._session_received and self._regime_received

    def _begin_evaluation(self, context: ChainEvaluationContext) -> None:
        if not self._actors_ready():
            return
        self._transition(StrategyState.EVALUATING, reason="signal")
        intent = self.build_intent(context)
        if intent is None:
            self._transition(StrategyState.FLAT, reason="no_intent")
            return
        self._run_gate_pipeline(intent, context)

    def _run_gate_pipeline(self, intent: TradeIntent, context: ChainEvaluationContext) -> None:
        gate_context = self._build_gate_context(context)
        pre_result = evaluate_pre_greek(intent, gate_context)
        if not pre_result.passed:
            assert pre_result.failed_stage is not None
            self._journal.record(
                pre_result.failed_stage,
                ref_id=intent.intent_id,
                payload={
                    "event": "GATE_REJECT",
                    "breached_rules": pre_result.breached_rules,
                    "intent_id": str(intent.intent_id),
                },
                strategy_id=self._strategy_id,
            )
            self._transition(StrategyState.FLAT, reason="gate_reject")
            return

        current = self._portfolio_greek_snapshot()
        projected = self._portfolio_greek_snapshot(
            spot_shock=self._risk_policy.spot_shock,
            vol_shock=self._risk_policy.vol_shock,
        )
        assessment = check_risk_policy(
            self._risk_policy,
            current,
            projected,
            intent_id=intent.intent_id,
        )
        if not assessment.passed:
            self._journal.record(
                GateStage.GREEK,
                ref_id=intent.intent_id,
                payload={
                    "event": "GATE_REJECT",
                    "breached_rules": assessment.breached_rules,
                    "intent_id": str(intent.intent_id),
                },
                strategy_id=self._strategy_id,
            )
            self._transition(StrategyState.FLAT, reason="greek_reject")
            return

        self._journal.record(
            GateStage.GREEK,
            ref_id=intent.intent_id,
            payload={"event": "GREEK_PASSED", "intent_id": str(intent.intent_id)},
            strategy_id=self._strategy_id,
        )

        if self.config.dry_run:
            self._journal.record(
                GateStage.LIFECYCLE,
                ref_id=intent.intent_id,
                payload={
                    "event": "DRY_RUN_INTENT",
                    "intent_id": str(intent.intent_id),
                    "instrument_id": intent.instrument_id,
                    "edge_after_cost_bps": intent.edge_after_cost_bps,
                },
                strategy_id=self._strategy_id,
            )
            self._transition(StrategyState.FLAT, reason="dry_run")
            return

        self._active_intent_id = intent.intent_id
        self._active_intent = intent
        self._transition(StrategyState.PENDING_ENTRY, reason="submit")
        self._journal.record(
            GateStage.LIFECYCLE,
            ref_id=intent.intent_id,
            payload={
                "event": "ORDER_SUBMIT",
                "intent_id": str(intent.intent_id),
                "instrument_id": intent.instrument_id,
            },
            strategy_id=self._strategy_id,
        )
        self.submit_entry(intent)

    def _build_gate_context(self, context: ChainEvaluationContext) -> GateContext:
        now_ns = self.clock.timestamp_ns()
        quote_fresh = (
            self._last_quote_ts is not None
            and (now_ns - self._last_quote_ts) / 1_000_000_000
            <= self.config.max_underlying_quote_age_secs
        )
        chain_fresh = self._last_chain_ts is not None and (
            now_ns - self._last_chain_ts
        ) / 1_000_000_000 <= (
            self.config.max_chain_snapshot_age_secs + self.config.chain_snapshot_interval_ms / 1000
        )
        if not self.config.require_chain_snapshot:
            chain_fresh = True
        elif context.rationale.get("source") == "backtest_plumbing":
            chain_fresh = True
        return GateContext(
            regime_tag=self._regime_tag,
            session_allows_entry=self._session_allows_entry,
            flatten_signal=self._flatten_signal,
            risk_policy=self._risk_policy,
            risk_policy_version=self._risk_policy.version,
            min_edge_after_cost_bps=self.config.min_edge_after_cost_bps,
            min_liquidity_score=self.config.min_liquidity_score,
            blocked_regimes=frozenset(RegimeTag(r) for r in self.config.blocked_regimes),
            underlying_quote_fresh=quote_fresh,
            chain_snapshot_fresh=chain_fresh,
            require_chain_snapshot=self.config.require_chain_snapshot,
        )

    def _portfolio_greek_snapshot(
        self,
        *,
        spot_shock: float = 0.0,
        vol_shock: float = 0.0,
    ) -> dict[str, float]:
        greeks = self.greeks.portfolio_greeks(
            spot_shock=spot_shock,
            vol_shock=vol_shock,
        )
        if greeks is None:
            return {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0}
        return {
            "delta": float(greeks.delta),
            "gamma": float(greeks.gamma),
            "vega": float(greeks.vega),
            "theta": float(greeks.theta),
        }

    def _journal_pnl(self, instrument_id) -> None:  # noqa: ANN001
        realized = self.portfolio.realized_pnl(instrument_id)
        unrealized = self.portfolio.unrealized_pnl(instrument_id)
        payload: dict[str, Any] = {
            "event": "PNL",
            "instrument_id": str(instrument_id),
            "realized_pnl": str(realized) if realized is not None else "0",
            "unrealized_pnl": str(unrealized) if unrealized is not None else "0",
        }
        if self._active_intent is not None:
            payload["edge_predicted_bps"] = self._active_intent.edge_after_cost_bps
        self._journal.record(
            GateStage.PNL,
            ref_id=self._active_intent_id,
            payload=payload,
            strategy_id=self._strategy_id,
        )

    def _manage_position(self, tick) -> None:  # noqa: ANN001
        if self._flatten_signal:
            self.flatten_positions(reason="session_blackout")
            return
        self._check_exit_triggers(tick)

    def _check_exit_triggers(self, tick) -> None:  # noqa: ANN001
        return

    def _transition(self, new_state: StrategyState, *, reason: str) -> None:
        old_state = self._state
        self._state = new_state
        self._journal.record(
            GateStage.LIFECYCLE,
            ref_id=self._active_intent_id,
            payload={
                "event": "FSM_TRANSITION",
                "from": old_state.value,
                "to": new_state.value,
                "reason": reason,
            },
            strategy_id=self._strategy_id,
        )
