from datetime import UTC, datetime

import pandas as pd
import pytest
from nautilus_trader.model.data import BarType
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from data_pipeline.catalog import MarketDataCatalog
from data_pipeline.ingestion.synthetic import (
    dataframe_to_bars,
    generate_bar_dataframe,
    generate_bars,
)
from data_pipeline.schemas import BAR_COLUMNS, SchemaError, validate_bar_dataframe

START = datetime(2024, 1, 1, tzinfo=UTC)
INSTRUMENT = TestInstrumentProvider.default_fx_ccy("EUR/USD")
BAR_TYPE = BarType.from_str("EUR/USD.SIM-1-MINUTE-MID-EXTERNAL")


class TestSyntheticGenerator:
    def test_schema_and_length(self):
        df = generate_bar_dataframe(start=START, num_bars=100, seed=1)
        assert list(df.columns) == BAR_COLUMNS
        assert len(df) == 100

    def test_deterministic_for_same_seed(self):
        a = generate_bar_dataframe(start=START, num_bars=50, seed=7)
        b = generate_bar_dataframe(start=START, num_bars=50, seed=7)
        pd.testing.assert_frame_equal(a, b)

    def test_different_seeds_differ(self):
        a = generate_bar_dataframe(start=START, num_bars=50, seed=1)
        b = generate_bar_dataframe(start=START, num_bars=50, seed=2)
        assert not a["close"].equals(b["close"])

    def test_ohlc_invariants_hold(self):
        df = generate_bar_dataframe(start=START, num_bars=500, seed=3)
        assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
        assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()

    def test_conversion_to_nautilus_bars(self):
        bars = generate_bars(BAR_TYPE, INSTRUMENT, start=START, num_bars=10, seed=1)
        assert len(bars) == 10
        assert all(bar.bar_type == BAR_TYPE for bar in bars)
        assert bars[0].ts_event < bars[-1].ts_event


class TestSchemaValidation:
    def test_missing_column_rejected(self):
        df = generate_bar_dataframe(start=START, num_bars=10).drop(columns=["volume"])
        with pytest.raises(SchemaError, match="Missing required columns"):
            validate_bar_dataframe(df)

    def test_naive_timestamps_rejected(self):
        df = generate_bar_dataframe(start=START, num_bars=10)
        df["ts_event"] = df["ts_event"].dt.tz_localize(None)
        with pytest.raises(SchemaError, match="timezone-aware"):
            validate_bar_dataframe(df)

    def test_high_below_low_rejected(self):
        df = generate_bar_dataframe(start=START, num_bars=10)
        df.loc[3, ["high", "low"]] = [1.0, 2.0]
        with pytest.raises(SchemaError):
            validate_bar_dataframe(df)

    def test_unsorted_timestamps_rejected(self):
        df = generate_bar_dataframe(start=START, num_bars=10).iloc[::-1].reset_index(drop=True)
        with pytest.raises(SchemaError, match="monotonically increasing"):
            validate_bar_dataframe(df)


class TestMarketDataCatalog:
    def test_write_and_read_roundtrip(self, tmp_path):
        catalog = MarketDataCatalog(tmp_path / "catalog")
        bars = generate_bars(BAR_TYPE, INSTRUMENT, start=START, num_bars=20, seed=5)

        catalog.write_instrument(INSTRUMENT)
        catalog.write_bars(bars)

        read_back = catalog.read_bars(BAR_TYPE)
        assert len(read_back) == 20
        assert read_back[0].close == bars[0].close
        assert [i.id for i in catalog.instruments()] == [INSTRUMENT.id]

    def test_conversion_requires_valid_schema(self, tmp_path):
        df = generate_bar_dataframe(start=START, num_bars=5).drop(columns=["close"])
        with pytest.raises(SchemaError):
            dataframe_to_bars(df, BAR_TYPE, INSTRUMENT)
