"""Project base strategy: config-driven, model-injectable, risk-rule aware.

Subclasses implement `register_indicators()` and `on_signal_bar()`; the base
handles instrument resolution, subscriptions, drawdown halting, and risk-checked
order submission. The same class runs unchanged in backtest and live.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.trading.strategy import Strategy

from nt_ext.risk.rules import DrawdownTracker, OrderContext, OrderRiskRule

if TYPE_CHECKING:
    from models.inference import SignalModel


# NT configs are frozen msgspec structs; mypy misreads inheritance as dataclasses.
class BaseSignalStrategyConfig(StrategyConfig):  # type: ignore[misc]
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal


class BaseSignalStrategy(Strategy):
    """Base for all project strategies (multi-asset, options, model-driven)."""

    def __init__(
        self,
        config: BaseSignalStrategyConfig,
        risk_rules: list[OrderRiskRule] | None = None,
        drawdown_tracker: DrawdownTracker | None = None,
        signal_model: SignalModel | None = None,
    ) -> None:
        super().__init__(config)
        self.risk_rules = list(risk_rules or [])
        self.drawdown_tracker = drawdown_tracker
        self.signal_model = signal_model
        self.instrument: Instrument | None = None
        self._halted = False

    # -- lifecycle ----------------------------------------------------------

    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Instrument {self.config.instrument_id} not found in cache; stopping")
            self.stop()
            return

        self.register_indicators(self.config.bar_type)
        self.subscribe_bars(self.config.bar_type)

    def on_stop(self) -> None:
        self.cancel_all_orders(self.config.instrument_id)
        self.close_all_positions(self.config.instrument_id)
        self.unsubscribe_bars(self.config.bar_type)

    def on_bar(self, bar: Bar) -> None:
        if self._halted:
            return
        if self.drawdown_tracker is not None and self._check_drawdown():
            return
        if not self.indicators_initialized():
            return
        self.on_signal_bar(bar)

    # -- hooks for subclasses -------------------------------------------------

    def register_indicators(self, bar_type: BarType) -> None:
        """Register indicators against the configured bar type (override in subclass)."""

    def on_signal_bar(self, bar: Bar) -> None:
        """Trading logic, called once indicators are warm (override in subclass)."""
        raise NotImplementedError

    # -- risk ----------------------------------------------------------------

    def _check_drawdown(self) -> bool:
        """Update the drawdown tracker; halt and flatten on breach. Returns True if halted."""
        assert self.drawdown_tracker is not None
        equity = self._current_equity()
        if equity is None:
            return False
        if self.drawdown_tracker.update(equity):
            self.log.error(
                f"Max drawdown breached (peak={self.drawdown_tracker.peak:.2f}, "
                f"equity={equity:.2f}); flattening and halting strategy"
            )
            self._halted = True
            self.cancel_all_orders(self.config.instrument_id)
            self.close_all_positions(self.config.instrument_id)
            return True
        return False

    def _current_equity(self) -> float | None:
        assert self.instrument is not None  # set in on_start
        venue = self.config.instrument_id.venue
        account = self.portfolio.account(venue)
        if account is None:
            return None
        currency = account.base_currency or self.instrument.quote_currency
        balance = account.balance_total(currency)
        if balance is None:
            return None
        equity = balance.as_double()
        unrealized = self.portfolio.unrealized_pnl(self.config.instrument_id)
        if unrealized is not None and unrealized.currency == currency:
            equity += unrealized.as_double()
        return equity

    def _risk_approved(self, notional: float) -> bool:
        ctx = OrderContext(
            instrument_id=str(self.config.instrument_id),
            notional=notional,
            open_positions=len(self.cache.positions_open()),
        )
        for rule in self.risk_rules:
            decision = rule.check(ctx)
            if not decision.approved:
                self.log.warning(f"Order rejected by risk rule '{rule.name}': {decision.reason}")
                return False
        return True

    # -- order helpers ---------------------------------------------------------

    def submit_market_order(self, side: OrderSide, last_px: float) -> None:
        """Submit a market order for the configured trade size, gated by risk rules."""
        assert self.instrument is not None  # set in on_start
        qty = self.instrument.make_qty(self.config.trade_size)
        if not self._risk_approved(notional=float(qty) * last_px):
            return
        order = self.order_factory.market(
            instrument_id=self.config.instrument_id,
            order_side=side,
            quantity=qty,
        )
        self.submit_order(order)

    def enter_long(self, last_px: float) -> None:
        self.submit_market_order(OrderSide.BUY, last_px)

    def enter_short(self, last_px: float) -> None:
        self.submit_market_order(OrderSide.SELL, last_px)

    def flatten(self) -> None:
        self.close_all_positions(self.config.instrument_id)

    # -- position state ---------------------------------------------------------

    @property
    def is_net_long(self) -> bool:
        return self.portfolio.is_net_long(self.config.instrument_id)

    @property
    def is_net_short(self) -> bool:
        return self.portfolio.is_net_short(self.config.instrument_id)

    @property
    def is_flat(self) -> bool:
        return self.portfolio.is_flat(self.config.instrument_id)
