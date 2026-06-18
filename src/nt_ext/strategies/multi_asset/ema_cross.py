"""Demo strategy: EMA cross with optional model overlay.

Long when fast EMA > slow EMA, short when fast EMA < slow EMA. If a `SignalModel`
is injected, its signal must agree in direction or the entry is skipped — a
minimal example of combining a learned signal with a rules-based one.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import numpy as np
from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model.data import Bar, BarType

from nt_ext.strategies.base import BaseSignalStrategy, BaseSignalStrategyConfig
from nt_ext.strategies.signals import PositionState, SignalIntent

if TYPE_CHECKING:
    from models.inference import SignalModel

RegisterIndicator = Callable[[BarType, Any], None]


class EMACrossConfig(BaseSignalStrategyConfig):  # type: ignore[misc]
    fast_period: int = 10
    slow_period: int = 30


def _validate_ema_periods(fast_period: int, slow_period: int) -> None:
    if fast_period >= slow_period:
        raise ValueError(f"fast_period ({fast_period}) must be < slow_period ({slow_period})")


class EmaCrossSignalEngine:
    """Composable signal engine for EMA-cross logic (used by EMACross and SwitcherStrategy)."""

    def __init__(
        self,
        fast_period: int,
        slow_period: int,
        signal_model: SignalModel | None = None,
    ) -> None:
        _validate_ema_periods(fast_period, slow_period)
        self.fast_ema = ExponentialMovingAverage(fast_period)
        self.slow_ema = ExponentialMovingAverage(slow_period)
        self.signal_model = signal_model

    def register_indicators(self, bar_type: BarType, register: RegisterIndicator) -> None:
        register(bar_type, self.fast_ema)
        register(bar_type, self.slow_ema)

    def evaluate(self, bar: Bar, position: PositionState) -> SignalIntent:
        if self.fast_ema.value > self.slow_ema.value:
            if not position.is_net_long and self._model_agrees(direction=1, bar=bar):
                return SignalIntent.ENTER_LONG
        elif self.fast_ema.value < self.slow_ema.value:  # noqa: SIM102
            if not position.is_net_short and self._model_agrees(direction=-1, bar=bar):
                return SignalIntent.ENTER_SHORT
        return SignalIntent.NOOP

    def _model_agrees(self, direction: int, bar: Bar) -> bool:
        if self.signal_model is None:
            return True
        features = np.array(
            [
                self.fast_ema.value,
                self.slow_ema.value,
                bar.close.as_double(),
            ],
            dtype=np.float64,
        )
        signal = self.signal_model.predict(features)
        return signal * direction > 0


class EMACross(BaseSignalStrategy):
    def __init__(self, config: EMACrossConfig, **kwargs) -> None:
        _validate_ema_periods(config.fast_period, config.slow_period)
        super().__init__(config, **kwargs)
        self._engine = EmaCrossSignalEngine(
            config.fast_period,
            config.slow_period,
            signal_model=self.signal_model,
        )

    @property
    def fast_ema(self) -> ExponentialMovingAverage:
        return self._engine.fast_ema

    @property
    def slow_ema(self) -> ExponentialMovingAverage:
        return self._engine.slow_ema

    def register_indicators(self, bar_type: BarType) -> None:
        self._engine.register_indicators(bar_type, self.register_indicator_for_bars)

    def on_signal_bar(self, bar: Bar) -> None:
        intent = self._engine.evaluate(bar, self._position_state())
        self._execute_intent(intent, bar.close.as_double())
