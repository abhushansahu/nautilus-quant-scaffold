from datetime import UTC, datetime

from nautilus_trader.model.data import BarType
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from data_pipeline.catalog import MarketDataCatalog
from data_pipeline.ingestion.synthetic import generate_bars
from data_pipeline.watermarks import WatermarkStore

START = datetime(2024, 1, 1, tzinfo=UTC)
BAR_TYPE_STR = "EUR/USD.SIM-1-MINUTE-MID-EXTERNAL"
BAR_TYPE = BarType.from_str(BAR_TYPE_STR)
INSTRUMENT = TestInstrumentProvider.default_fx_ccy("EUR/USD")


class TestWatermarkStore:
    def test_get_set_roundtrip(self, tmp_path):
        store = WatermarkStore(tmp_path / "watermarks.json")
        ts = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
        store.set(BAR_TYPE_STR, ts)
        assert store.get(BAR_TYPE_STR) == ts

    def test_has_new_data_when_no_watermark(self, tmp_path):
        catalog = MarketDataCatalog(tmp_path / "catalog")
        bars = generate_bars(BAR_TYPE, INSTRUMENT, start=START, num_bars=5, seed=1)
        catalog.write_instrument(INSTRUMENT)
        catalog.write_bars(bars)

        store = WatermarkStore(tmp_path / "watermarks.json")
        assert store.has_new_data(BAR_TYPE_STR, catalog)

    def test_has_new_data_false_when_caught_up(self, tmp_path):
        catalog = MarketDataCatalog(tmp_path / "catalog")
        bars = generate_bars(BAR_TYPE, INSTRUMENT, start=START, num_bars=5, seed=1)
        catalog.write_instrument(INSTRUMENT)
        catalog.write_bars(bars)

        latest = catalog.latest_ts(BAR_TYPE)
        store = WatermarkStore(tmp_path / "watermarks.json")
        store.set(BAR_TYPE_STR, latest)
        assert not store.has_new_data(BAR_TYPE_STR, catalog)

    def test_has_new_data_true_after_append(self, tmp_path):
        catalog = MarketDataCatalog(tmp_path / "catalog")
        bars = generate_bars(BAR_TYPE, INSTRUMENT, start=START, num_bars=5, seed=1)
        catalog.write_instrument(INSTRUMENT)
        catalog.write_bars(bars)
        latest = catalog.latest_ts(BAR_TYPE)

        store = WatermarkStore(tmp_path / "watermarks.json")
        store.set(BAR_TYPE_STR, latest)

        more = generate_bars(BAR_TYPE, INSTRUMENT, start=START, num_bars=10, seed=1)
        catalog.write_bars(more[5:])
        assert store.has_new_data(BAR_TYPE_STR, catalog)
