"""Bar source implementations and window resolution."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.instruments import Instrument

from core.experiment import DataSpec
from data_pipeline.catalog import MarketDataCatalog
from data_pipeline.data_window import DataWindow
from data_pipeline.ingestion.synthetic import dataframe_to_bars, generate_bar_dataframe


def resolve_window(
    data: DataSpec,
    data_window: DataWindow | None,
    catalog: MarketDataCatalog | None,
    bar_type: BarType,
) -> tuple[datetime | None, datetime | None, int | None]:
    mode = data_window.mode if data_window is not None else data.mode
    if mode == "incremental":
        watermark = data_window.watermark if data_window else data.start
        end = data_window.end if data_window else data.end
        return watermark, end, None
    if mode == "rolling":
        lookback = data_window.lookback_bars if data_window else data.lookback_bars
        end = data_window.end if data_window and data_window.end else None
        if end is None and catalog is not None:
            end = catalog.latest_ts(bar_type)
        return None, end, lookback
    start = data_window.start if data_window and data_window.start else data.start
    end = data_window.end if data_window else data.end
    return start, end, None


class CatalogBarSource:
    def read_bars(
        self,
        catalog: MarketDataCatalog,
        bar_type: BarType,
        data: DataSpec,
        data_window: DataWindow | None,
    ) -> list[Bar]:
        start, end, lookback = resolve_window(data, data_window, catalog, bar_type)
        bars = catalog.read_bars(bar_type, start=start, end=end)
        if (data_window is not None and data_window.mode == "incremental") or (
            data_window is None and data.mode == "incremental"
        ):
            watermark = (data_window.watermark if data_window else None) or data.start
            if watermark is not None:
                from nautilus_trader.core.datetime import dt_to_unix_nanos

                wm_ns = dt_to_unix_nanos(watermark)
                bars = [bar for bar in bars if bar.ts_event > wm_ns]
        if lookback is not None and len(bars) > lookback:
            bars = bars[-lookback:]
        if not bars:
            raise ValueError(f"No bars for {bar_type} in catalog {catalog.path}")
        return bars


class SyntheticBarSource:
    def generate_bars(
        self,
        bar_type: BarType,
        instrument: Instrument,
        data: DataSpec,
    ) -> list[Bar]:
        df = generate_bar_dataframe(
            start=data.start,
            num_bars=data.num_bars,
            seed=data.seed,
            bar_interval_secs=data.bar_interval_secs,
        )
        return dataframe_to_bars(df, bar_type, instrument)


class BarSource(Protocol):
    def read_bars(
        self,
        catalog: MarketDataCatalog,
        bar_type: BarType,
        data: DataSpec,
        data_window: DataWindow | None,
    ) -> list[Bar]: ...
