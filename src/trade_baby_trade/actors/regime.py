from __future__ import annotations

from collections import deque

from nautilus_trader.common.actor import Actor
from nautilus_trader.config import ActorConfig
from nautilus_trader.model.identifiers import InstrumentId

from trade_baby_trade.actors.data_types import REGIME_TAG_TOPIC, RegimeTagSnapshot
from trade_baby_trade.models.enums import RegimeTag


class RegimeActorConfig(ActorConfig, frozen=True):
    underlying: str = "SPY.NYSE"
    trend_move_pct: float = 0.005
    chop_range_pct: float = 0.002
    pin_strike_proximity_pct: float = 0.001


def compute_regime_tag(
    mid: float,
    *,
    open_price: float | None,
    recent_prices: list[float],
    trend_move_pct: float,
    chop_range_pct: float,
    pin_strike_proximity_pct: float,
) -> RegimeTag:
    if open_price and abs(mid - open_price) / open_price >= trend_move_pct:
        return RegimeTag.TREND
    if len(recent_prices) >= 5:
        range_pct = (max(recent_prices) - min(recent_prices)) / mid
        if range_pct <= chop_range_pct:
            return RegimeTag.CHOP
    round_strike = round(mid)
    if mid > 0 and abs(mid - round_strike) / mid <= pin_strike_proximity_pct:
        return RegimeTag.PIN_RISK
    return RegimeTag.UNKNOWN


class RegimeActor(Actor):
    """Rule-based regime tags for gate input — no ML."""

    def __init__(self, config: RegimeActorConfig) -> None:
        super().__init__(config)
        self._prices: deque[float] = deque(maxlen=20)
        self._open_price: float | None = None
        self._last_tag: RegimeTag | None = None

    def on_start(self) -> None:
        instrument_id = InstrumentId.from_str(self.config.underlying)
        self.subscribe_quote_ticks(instrument_id)

    def regime_tag(self) -> RegimeTag:
        if not self._prices:
            return RegimeTag.UNKNOWN
        return self._compute_regime(self._prices[-1])

    def on_quote_tick(self, tick) -> None:  # noqa: ANN001
        mid = (float(tick.bid_price) + float(tick.ask_price)) / 2.0
        if self._open_price is None:
            self._open_price = mid
        self._prices.append(mid)
        tag = self._compute_regime(mid)
        if tag == self._last_tag:
            return
        self._last_tag = tag
        self.msgbus.publish(REGIME_TAG_TOPIC, RegimeTagSnapshot(regime_tag=tag.value))

    def _compute_regime(self, mid: float) -> RegimeTag:
        return compute_regime_tag(
            mid,
            open_price=self._open_price,
            recent_prices=list(self._prices),
            trend_move_pct=self.config.trend_move_pct,
            chop_range_pct=self.config.chop_range_pct,
            pin_strike_proximity_pct=self.config.pin_strike_proximity_pct,
        )
