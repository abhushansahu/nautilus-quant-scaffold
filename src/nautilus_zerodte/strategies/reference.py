from __future__ import annotations

from uuid import UUID

from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId

from nautilus_zerodte.models.enums import GateStage, StrategyState, VenueAdapter
from nautilus_zerodte.models.trade_intent import TradeIntent
from nautilus_zerodte.strategies.base import BaseZeroDteStrategy, BaseZeroDteStrategyConfig
from nautilus_zerodte.strategies.context import ChainEvaluationContext
from nautilus_zerodte.strategies.selectors.base import SpreadStructure, StructureSelector
from nautilus_zerodte.strategies.selectors.registry import resolve_structure_selector


class ReferenceZeroDteStrategyConfig(BaseZeroDteStrategyConfig, frozen=True):
    backtest_plumbing: bool = False
    structure_selector: str = "auto"
    venue_adapter: str = "IB"
    option_series_id: str | None = None
    option_series_expiry: str | None = None
    option_series_expiry_time_utc: str = "08:00"
    settlement_currency: str = "BTC"
    strike_width: int = 5
    order_qty: float = 1.0
    take_profit_pct: float = 0.25
    stop_loss_pct: float = 0.50
    hedge_perp_instrument: str | None = None
    hedge_delta_band: float = 0.30


class ReferenceZeroDteStrategy(BaseZeroDteStrategy):
    """Minimal 0DTE reference strategy — plumbing validation, not production edge."""

    def __init__(self, config: ReferenceZeroDteStrategyConfig) -> None:
        super().__init__(config)
        self._ref_config = config
        self._exit_submitted = False
        self._hedge_submitted = False
        self._position_instrument_id: str | None = None
        self._leg_instrument_ids: tuple[str, ...] = ()
        self._selector: StructureSelector | None = None
        if not config.backtest_plumbing:
            adapter = VenueAdapter(config.venue_adapter.upper())
            underlying_symbol = config.option_series_id or config.underlying.split(".")[0]
            if "-" in underlying_symbol:
                underlying_symbol = underlying_symbol.split("-")[0]
            self._selector = resolve_structure_selector(
                config.structure_selector,
                venue_adapter=adapter,
                underlying_symbol=underlying_symbol,
                option_series_expiry=config.option_series_expiry,
                settlement_currency=config.settlement_currency,
            )

    def _subscribe_market_data(self) -> None:
        underlying = InstrumentId.from_str(self.config.underlying)
        self.subscribe_quote_ticks(underlying)
        if self._ref_config.hedge_perp_instrument:
            self.subscribe_quote_ticks(
                InstrumentId.from_str(self._ref_config.hedge_perp_instrument)
            )
        if self._ref_config.backtest_plumbing or self._selector is None:
            return
        if self._ref_config.option_series_expiry is None:
            return
        from nautilus_zerodte.strategies.selectors.deribit import deribit_option_series_id

        series_id = deribit_option_series_id(
            underlying=self._ref_config.option_series_id or "BTC",
            settlement_currency=self._ref_config.settlement_currency,
            expiry=self._ref_config.option_series_expiry,
            expiry_time_utc=self._ref_config.option_series_expiry_time_utc,
        )
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
                "structure": context.rationale.get("structure", "vertical_spread"),
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

        entry_price = self._estimate_entry_price(instrument_id)
        order_list = self.order_factory.bracket(
            instrument_id=instrument_id,
            order_side=OrderSide.BUY,
            quantity=instrument.make_qty(self._ref_config.order_qty),
            time_in_force=TimeInForce.IOC,
            tp_price=instrument.make_price(entry_price * (1 + self._ref_config.take_profit_pct))
            if entry_price
            else None,
            sl_trigger_price=(
                instrument.make_price(entry_price * (1 - self._ref_config.stop_loss_pct))
                if entry_price
                else None
            ),
        )
        self.submit_order_list(order_list)
        self._position_instrument_id = intent.instrument_id
        self._leg_instrument_ids = tuple(intent.rationale.get("leg_instrument_ids", ()))

    def submit_exit(self, intent_id: UUID, *, reason: str) -> None:
        if self._ref_config.backtest_plumbing:
            if self._active_intent is not None:
                self._submit_underlying_market(self._active_intent, OrderSide.SELL)
            return

        instrument_id_str = self._position_instrument_id or self.config.underlying
        instrument_id = InstrumentId.from_str(instrument_id_str)
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

    def on_option_greeks(self, greeks) -> None:  # noqa: ANN001
        if self._state != StrategyState.IN_POSITION:
            return
        if self._ref_config.backtest_plumbing or not self._ref_config.hedge_perp_instrument:
            return
        portfolio = self._portfolio_greek_snapshot()
        delta = abs(portfolio.get("delta", 0.0))
        if delta <= self._ref_config.hedge_delta_band or self._hedge_submitted:
            return
        self._hedge_submitted = True
        self._submit_delta_hedge(portfolio.get("delta", 0.0), reason="delta_band")

    def _context_from_chain_slice(self, option_chain_slice) -> ChainEvaluationContext | None:  # noqa: ANN001
        if self._ref_config.backtest_plumbing:
            return super()._context_from_chain_slice(option_chain_slice)
        if self._selector is None or not self._actors_ready():
            return None

        selection = self._selector.select_from_chain(
            option_chain_slice,
            strike_width=self._ref_config.strike_width,
            min_edge_after_cost_bps=self.config.min_edge_after_cost_bps,
            min_liquidity_score=self.config.min_liquidity_score,
        )
        if selection is None:
            return None
        return self._context_from_selection(selection, option_chain_slice)

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

    def _context_from_selection(
        self,
        selection: SpreadStructure,
        option_chain_slice,
    ) -> ChainEvaluationContext:
        underlying_mid = float(selection.low_strike)
        from nautilus_zerodte.strategies.selectors.deribit import _strike_price

        greeks = option_chain_slice.get_call_greeks(_strike_price(selection.low_strike))
        if greeks is not None and getattr(greeks, "underlying_price", None):
            underlying_mid = float(greeks.underlying_price)
        return ChainEvaluationContext(
            instrument_id=selection.spread_instrument_id,
            underlying_mid=underlying_mid,
            atm_strike=float(option_chain_slice.atm_strike),
            edge_after_cost_bps=selection.edge_after_cost_bps,
            liquidity_score=selection.liquidity_score,
            ts_event=int(option_chain_slice.ts_event),
            spread_instrument_id=selection.spread_instrument_id,
            rationale={
                **selection.rationale,
                "leg_instrument_ids": list(selection.leg_instrument_ids),
                "low_strike": selection.low_strike,
                "high_strike": selection.high_strike,
            },
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

    def on_order_filled(self, event) -> None:  # noqa: ANN001
        super().on_order_filled(event)
        if self._state == StrategyState.IN_POSITION and not self._ref_config.backtest_plumbing:
            spread_id = self._position_instrument_id or str(event.instrument_id)
            self.subscribe_quote_ticks(InstrumentId.from_str(spread_id))
            for leg_id in self._leg_instrument_ids:
                self.subscribe_option_greeks(InstrumentId.from_str(leg_id))

    def _estimate_entry_price(self, instrument_id: InstrumentId) -> float | None:
        quote = self.cache.quote_tick(instrument_id)
        if quote is None:
            return None
        return (float(quote.bid_price) + float(quote.ask_price)) / 2

    def _submit_delta_hedge(self, delta: float, *, reason: str) -> None:
        perp_id = InstrumentId.from_str(self._ref_config.hedge_perp_instrument)  # type: ignore[arg-type]
        instrument = self.cache.instrument(perp_id)
        if instrument is None:
            return
        side = OrderSide.SELL if delta > 0 else OrderSide.BUY
        qty = instrument.make_qty(min(abs(delta), float(self._ref_config.order_qty)))
        order = self.order_factory.market(
            instrument_id=perp_id,
            order_side=side,
            quantity=qty,
            time_in_force=TimeInForce.IOC,
        )
        self._journal.record(
            GateStage.LIFECYCLE,
            ref_id=self._active_intent_id,
            payload={
                "event": "DELTA_HEDGE",
                "reason": reason,
                "delta": delta,
                "instrument_id": str(perp_id),
                "side": side.name,
            },
            strategy_id=self._strategy_id,
        )
        if not self.config.dry_run:
            self.submit_order(order)

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
