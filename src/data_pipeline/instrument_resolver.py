"""Instrument resolution for experiments."""

from __future__ import annotations

from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from core.config import AppConfig
from core.experiment import ExperimentConfig
from data_pipeline.catalog import MarketDataCatalog


def resolve_instrument(exp: ExperimentConfig, app_cfg: AppConfig) -> Instrument:
    instrument_id = InstrumentId.from_str(exp.strategy.instrument_id)
    if exp.data.source == "catalog":
        catalog = MarketDataCatalog(app_cfg.catalog_path)
        for instrument in catalog.instruments():
            if instrument.id == instrument_id:
                return instrument
        raise ValueError(f"Instrument {instrument_id} not found in catalog {catalog.path}")
    return TestInstrumentProvider.default_fx_ccy(
        str(instrument_id.symbol),
        venue=instrument_id.venue,
    )
