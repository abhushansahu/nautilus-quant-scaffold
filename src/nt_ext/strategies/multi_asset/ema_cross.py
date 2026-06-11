"""Demo strategy: EMA cross with optional model overlay.

Long when fast EMA > slow EMA, short when fast EMA < slow EMA. If a `SignalModel`
is injected, its signal must agree in direction or the entry is skipped — a
minimal example of combining a learned signal with a rules-based one.
"""

from __future__ import annotations

import numpy as np
from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model.data import Bar, BarType

from nt_ext.strategies.base import BaseSignalStrategy, BaseSignalStrategyConfig


class EMACrossConfig(BaseSignalStrategyConfig):  # type: ignore[misc]
    fast_period: int = 10
    slow_period: int = 30


class EMACross(BaseSignalStrategy):
    def __init__(self, config: EMACrossConfig, **kwargs) -> None:
        if config.fast_period >= config.slow_period:
            raise ValueError(
                f"fast_period ({config.fast_period}) must be < slow_period ({config.slow_period})"
            )
        super().__init__(config, **kwargs)
        self.fast_ema = ExponentialMovingAverage(config.fast_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_period)

    def register_indicators(self, bar_type: BarType) -> None:
        self.register_indicator_for_bars(bar_type, self.fast_ema)
        self.register_indicator_for_bars(bar_type, self.slow_ema)

    def on_signal_bar(self, bar: Bar) -> None:
        last_px = bar.close.as_double()

        if self.fast_ema.value > self.slow_ema.value:
            if not self.is_net_long and self._model_agrees(direction=1, bar=bar):
                self.flatten()
                self.enter_long(last_px)
        elif self.fast_ema.value < self.slow_ema.value:  # noqa: SIM102
            if not self.is_net_short and self._model_agrees(direction=-1, bar=bar):
                self.flatten()
                self.enter_short(last_px)

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
