from datetime import UTC, datetime
from pathlib import Path

from nautilus_trader.model.data import BarType
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from core.config import load_config
from core.experiment import load_experiment
from data_pipeline.catalog import MarketDataCatalog
from data_pipeline.ingestion.synthetic import generate_bars
from data_pipeline.loader import BarDataLoader, DataWindow

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
START = datetime(2024, 1, 1, tzinfo=UTC)
BAR_TYPE = BarType.from_str("EUR/USD.SIM-1-MINUTE-MID-EXTERNAL")
INSTRUMENT = TestInstrumentProvider.default_fx_ccy("EUR/USD")


class TestBarDataLoader:
    def test_synthetic_load(self):
        loader = BarDataLoader(use_disk_cache=False)
        exp = load_experiment(CONFIG_DIR / "strategies" / "ema_cross_demo.yaml")
        app_cfg = load_config("backtest", config_dir=CONFIG_DIR)
        instrument = loader.resolve_instrument(exp, app_cfg)
        bars = loader.load_bars(exp, app_cfg, instrument)
        assert len(bars) == exp.data.num_bars

    def test_memory_cache_hit(self, tmp_path):
        catalog_path = tmp_path / "catalog"
        catalog = MarketDataCatalog(catalog_path)
        bars = generate_bars(BAR_TYPE, INSTRUMENT, start=START, num_bars=30, seed=1)
        catalog.write_instrument(INSTRUMENT)
        catalog.write_bars(bars)

        exp = load_experiment(CONFIG_DIR / "strategies" / "ema_cross_demo.yaml")
        exp = exp.model_copy(update={"data": exp.data.model_copy(update={"source": "catalog"})})
        app_cfg = load_config("backtest", config_dir=CONFIG_DIR).model_copy(
            update={"catalog_path": catalog_path}
        )
        loader = BarDataLoader(use_disk_cache=False)
        instrument = loader.resolve_instrument(exp, app_cfg)

        first = loader.load_bars(exp, app_cfg, instrument, cache_key="bucket-a")
        second = loader.load_bars(exp, app_cfg, instrument, cache_key="bucket-a")
        assert first is second
        assert len(first) == 30

    def test_incremental_window_filters_bars(self, tmp_path):
        catalog_path = tmp_path / "catalog"
        catalog = MarketDataCatalog(catalog_path)
        bars = generate_bars(BAR_TYPE, INSTRUMENT, start=START, num_bars=50, seed=2)
        catalog.write_instrument(INSTRUMENT)
        catalog.write_bars(bars)

        from nautilus_trader.core.datetime import unix_nanos_to_dt

        watermark = unix_nanos_to_dt(bars[24].ts_event)

        exp = load_experiment(CONFIG_DIR / "strategies" / "ema_cross_demo.yaml")
        exp = exp.model_copy(update={"data": exp.data.model_copy(update={"source": "catalog"})})
        app_cfg = load_config("backtest", config_dir=CONFIG_DIR).model_copy(
            update={"catalog_path": catalog_path}
        )
        loader = BarDataLoader(use_disk_cache=False)
        instrument = loader.resolve_instrument(exp, app_cfg)
        window = DataWindow(mode="incremental", watermark=watermark)
        loaded = loader.load_bars(exp, app_cfg, instrument, data_window=window)
        assert len(loaded) == 25

    def test_rolling_window_limits_bars(self, tmp_path):
        catalog_path = tmp_path / "catalog"
        catalog = MarketDataCatalog(catalog_path)
        bars = generate_bars(BAR_TYPE, INSTRUMENT, start=START, num_bars=100, seed=3)
        catalog.write_instrument(INSTRUMENT)
        catalog.write_bars(bars)

        exp = load_experiment(CONFIG_DIR / "strategies" / "ema_cross_demo.yaml")
        exp = exp.model_copy(update={"data": exp.data.model_copy(update={"source": "catalog"})})
        app_cfg = load_config("backtest", config_dir=CONFIG_DIR).model_copy(
            update={"catalog_path": catalog_path}
        )
        loader = BarDataLoader(use_disk_cache=False)
        instrument = loader.resolve_instrument(exp, app_cfg)
        window = DataWindow(mode="rolling", lookback_bars=10)
        loaded = loader.load_bars(exp, app_cfg, instrument, data_window=window)
        assert len(loaded) == 10
