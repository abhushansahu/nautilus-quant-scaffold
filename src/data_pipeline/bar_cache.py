"""Memory and disk caching for bar data."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

import pandas as pd
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.instruments import Instrument

from data_pipeline.ingestion.synthetic import dataframe_to_bars

DEFAULT_CACHE_DIR = Path("data/cache")
MAX_MEMORY_ENTRIES = 32


def cache_key(
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


class BarCache:
    """In-process LRU cache with optional on-disk parquet persistence."""

    def __init__(
        self,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        use_disk_cache: bool = True,
        max_memory_entries: int = MAX_MEMORY_ENTRIES,
    ) -> None:
        self._cache_dir = cache_dir
        self._use_disk_cache = use_disk_cache
        self._max_memory_entries = max_memory_entries
        self._memory: OrderedDict[str, list[Bar]] = OrderedDict()

    def get_memory(self, key: str) -> list[Bar] | None:
        if key not in self._memory:
            return None
        self._memory.move_to_end(key)
        return self._memory[key]

    def get_disk(self, key: str, bar_type: BarType, instrument: Instrument) -> list[Bar] | None:
        if not self._use_disk_cache:
            return None
        path = self._disk_path(key)
        if not path.exists():
            return None
        df = pd.read_parquet(path)
        return dataframe_to_bars(df, bar_type, instrument)

    def put(self, key: str, bars: list[Bar]) -> None:
        self._memory[key] = bars
        self._memory.move_to_end(key)
        while len(self._memory) > self._max_memory_entries:
            self._memory.popitem(last=False)
        if self._use_disk_cache:
            self._save_disk(key, bars)

    def _disk_path(self, key: str) -> Path:
        return self._cache_dir / key / "bars.parquet"

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
