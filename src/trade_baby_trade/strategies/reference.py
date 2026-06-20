from __future__ import annotations

from uuid import UUID

from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId

from trade_baby_trade.models.enums import GateStage, StrategyState
from trade_baby_trade.models.trade_intent import TradeIntent
from trade_baby_trade.strategies.base import BaseZeroDteStrategy, BaseZeroDteStrategyConfig
from trade_baby_trade.strategies.context import ChainEvaluationContext


class ReferenceZeroDteStrategyConfig(BaseZeroDteStrategyConfig, frozen=True):
    backtest_plumbing: bool = False
    option_series_id: str | None = None
    strike_width: int = 5
    order_qty: int = 1
    take_profit_pct: float = 0.25
    stop_loss_pct: float = 0.50


class ReferenceZeroDteStrategy(BaseZeroDteStrategy):
    """Minimal 0DTE reference strategy — plumbing validation, not production edge."""

    def __init__(self, config: ReferenceZeroDteStrategyConfig) -> None:
        super().__init__(config)
        self._ref_config = config
        self._exit_submitted = False

    def _subscribe_market_data(self) -> None:
        underlying = InstrumentId.from_str(self.config.underlying)
        self.subscribe_quote_ticks(underlying)
        if self._ref_config.option_series_id and not self._ref_config.backtest_plumbing:
            from nautilus_trader.model.data import nautilus_pyo3

            series_id = nautilus_pyo3.OptionSeriesId(self._ref_config.option_series_id)
            self.subscribe_option_chain(
                series_id,
                snapshot_interval_ms=self.config.chain_snapshot_interval_ms,
            )

    def build_intent(self, context: ChainEvaluationContext) -> TradeIntent | None:
        spread_id = context.spread_instrument_id or context.instrument_id
        return TradeIntent(
            strategy_id=self._strategy_id,
            instrument_id=spread_id,
            edge_after_cost_bps=context.edge_after_cost_bps,
            liquidity_score=context.liquidity_score,
            regime_tag=self._regime_tag,
            rationale={
                **context.rationale,
                "atm_strike": context.atm_strike,
                "underlying_mid": context.underlying_mid,
                "structure": "vertical_spread",
                "strike_width": self._ref_config.strike_width,
            },
        )

    def submit_entry(self, intent: TradeIntent) -> None:
        if self._ref_config.backtest_plumbing:
            self._submit_underlying_market(intent, OrderSide.BUY)
            return
        instrument_id = InstrumentId.from_str(intent.instrument_id)
        instrument = self.cache.instrument(instrument_id)
        if instrument is None:
            self._journal_order_error(intent, "instrument_not_found")
            return
        order = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=OrderSide.BUY,
            quantity=instrument.make_qty(self._ref_config.order_qty),
            time_in_force=TimeInForce.IOC,
        )
        self.submit_order(order)

    def submit_exit(self, intent_id: UUID, *, reason: str) -> None:
        if self._ref_config.backtest_plumbing:
            if self._active_intent is not None:
                self._submit_underlying_market(self._active_intent, OrderSide.SELL)
            return
        instrument_id = InstrumentId.from_str(self.config.underlying)
        instrument = self.cache.instrument(instrument_id)
        if instrument is None:
            return
        order = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=OrderSide.SELL,
            quantity=instrument.make_qty(self._ref_config.order_qty),
            time_in_force=TimeInForce.IOC,
        )
        self.submit_order(order)

    def _context_from_quote_tick(self, tick) -> ChainEvaluationContext | None:  # noqa: ANN001
        if not self._ref_config.backtest_plumbing or not self._actors_ready():
            return None
        bid = float(tick.bid_price)
        ask = float(tick.ask_price)
        mid = (bid + ask) / 2
        spread_bps = ((ask - bid) / mid) * 10_000 if mid > 0 else 100.0
        liquidity = max(0.0, min(1.0, 1.0 - spread_bps / 100.0))
        atm = round(mid)
        return ChainEvaluationContext(
            instrument_id=str(tick.instrument_id),
            underlying_mid=mid,
            atm_strike=float(atm),
            edge_after_cost_bps=max(self.config.min_edge_after_cost_bps, 10.0),
            liquidity_score=max(self.config.min_liquidity_score, liquidity),
            ts_event=int(tick.ts_event),
            spread_instrument_id=str(tick.instrument_id),
            rationale={"source": "backtest_plumbing", "spread_bps": spread_bps},
        )

    def _check_exit_triggers(self, tick) -> None:  # noqa: ANN001
        if self._exit_submitted or self._entry_price is None or self._active_intent_id is None:
            return
        bid = float(tick.bid_price)
        entry = self._entry_price
        pnl_pct = (bid - entry) / entry if entry > 0 else 0.0
        if (
            pnl_pct >= self._ref_config.take_profit_pct
            or pnl_pct <= -self._ref_config.stop_loss_pct
        ):
            self._exit_submitted = True
            self._transition(StrategyState.EXITING, reason="tp_sl")
            self.submit_exit(self._active_intent_id, reason="tp_sl")

    def _submit_underlying_market(self, intent: TradeIntent, side: OrderSide) -> None:
        instrument_id = InstrumentId.from_str(self.config.underlying)
        instrument = self.cache.instrument(instrument_id)
        if instrument is None:
            self._journal_order_error(intent, "instrument_not_found")
            return
        order = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=side,
            quantity=instrument.make_qty(self._ref_config.order_qty),
            time_in_force=TimeInForce.IOC,
        )
        self.submit_order(order)

    def _journal_order_error(self, intent: TradeIntent, reason: str) -> None:
        self._journal.record(
            GateStage.LIFECYCLE,
            ref_id=intent.intent_id,
            payload={"event": "ORDER_ERROR", "reason": reason},
            strategy_id=self._strategy_id,
        )
        self._transition(StrategyState.FLAT, reason=reason)
