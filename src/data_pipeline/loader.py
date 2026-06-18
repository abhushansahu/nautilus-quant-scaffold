"""Bar data loading with in-process LRU and optional disk cache."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from core.config import AppConfig
from core.experiment import DataSpec, ExperimentConfig
from data_pipeline.catalog import MarketDataCatalog
from data_pipeline.ingestion.synthetic import dataframe_to_bars, generate_bar_dataframe

DEFAULT_CACHE_DIR = Path("data/cache")
MAX_MEMORY_ENTRIES = 32


@dataclass(frozen=True)
class DataWindow:
    """Optional override for bar loading window (orchestrator / watcher)."""

    mode: Literal["full", "incremental", "rolling"] = "full"
    start: datetime | None = None
    end: datetime | None = None
    watermark: datetime | None = None
    lookback_bars: int = 500


def _cache_key(
    catalog_path: Path,
    bar_type: str,
    start: datetime | None,
    end: datetime | None,
    source: str,
    seed: int,
    num_bars: int,
    cache_bucket: str | None,
) -> str:
    payload = json.dumps(
        {
            "catalog_path": str(catalog_path),
            "bar_type": bar_type,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "source": source,
            "seed": seed,
            "num_bars": num_bars,
            "cache_bucket": cache_bucket,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class BarDataLoader:
    """Load bars for experiments with memory and optional disk caching."""

    def __init__(
        self,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        use_disk_cache: bool = True,
    ) -> None:
        self._cache_dir = cache_dir
        self._use_disk_cache = use_disk_cache
        self._memory: OrderedDict[str, list[Bar]] = OrderedDict()

    def resolve_instrument(self, exp: ExperimentConfig, app_cfg: AppConfig) -> Instrument:
        from nautilus_trader.model.identifiers import InstrumentId

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

    def _memory_get(self, key: str) -> list[Bar] | None:
        if key not in self._memory:
            return None
        self._memory.move_to_end(key)
        return self._memory[key]

    def _memory_put(self, key: str, bars: list[Bar]) -> None:
        self._memory[key] = bars
        self._memory.move_to_end(key)
        while len(self._memory) > MAX_MEMORY_ENTRIES:
            self._memory.popitem(last=False)

    def _disk_path(self, key: str) -> Path:
        return self._cache_dir / key / "bars.parquet"

    def _load_disk(self, key: str, bar_type: BarType, instrument: Instrument) -> list[Bar] | None:
        path = self._disk_path(key)
        if not path.exists():
            return None
        df = pd.read_parquet(path)
        return dataframe_to_bars(df, bar_type, instrument)

    def _save_disk(self, key: str, bars: list[Bar]) -> None:
        path = self._disk_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "ts_event": pd.Timestamp(b.ts_event, unit="ns", tz="UTC"),
                "open": b.open.as_double(),
                "high": b.high.as_double(),
                "low": b.low.as_double(),
                "close": b.close.as_double(),
                "volume": float(b.volume),
            }
            for b in bars
        ]
        pd.DataFrame(rows).to_parquet(path, index=False)

    def _resolve_window(
        self,
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

    def load_bars(
        self,
        exp: ExperimentConfig,
        app_cfg: AppConfig,
        instrument: Instrument,
        data_window: DataWindow | None = None,
        cache_key: str | None = None,
    ) -> list[Bar]:
        bar_type = BarType.from_str(exp.strategy.bar_type)
        data = exp.data

        if data.source == "synthetic":
            return self._load_synthetic(bar_type, instrument, data)

        catalog = MarketDataCatalog(app_cfg.catalog_path)
        start, end, lookback = self._resolve_window(data, data_window, catalog, bar_type)
        key = _cache_key(
            app_cfg.catalog_path,
            str(bar_type),
            start,
            end,
            data.source,
            data.seed,
            data.num_bars,
            cache_key,
        )

        cached = self._memory_get(key)
        if cached is not None:
            return cached

        if self._use_disk_cache:
            disk_bars = self._load_disk(key, bar_type, instrument)
            if disk_bars is not None:
                self._memory_put(key, disk_bars)
                return disk_bars

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

        self._memory_put(key, bars)
        if self._use_disk_cache:
            self._save_disk(key, bars)
        return bars

    def _load_synthetic(
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


@lru_cache(maxsize=1)
def default_loader() -> BarDataLoader:
    return BarDataLoader()
