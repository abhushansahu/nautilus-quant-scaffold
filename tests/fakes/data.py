from __future__ import annotations

from nautilus_trader.model.instruments import Instrument
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from core.config import AppConfig
from core.experiment import ExperimentConfig


class FakeBarLoader:
    def __init__(self, bars: list | None = None) -> None:
        self.bars = bars or []
        self.resolve_calls: list[tuple[ExperimentConfig, AppConfig]] = []
        self.load_calls: list[tuple[ExperimentConfig, AppConfig, Instrument]] = []

    def resolve_instrument(self, exp: ExperimentConfig, app_cfg: AppConfig) -> Instrument:
        self.resolve_calls.append((exp, app_cfg))
        instrument_id = exp.strategy.instrument_id
        symbol = instrument_id.split(".")[0]
        return TestInstrumentProvider.default_fx_ccy(symbol)

    def load_bars(self, exp, app_cfg, instrument, data_window=None, cache_key=None) -> list:
        self.load_calls.append((exp, app_cfg, instrument))
        return self.bars
