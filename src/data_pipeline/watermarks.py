"""Persist per-bar-type processing watermarks for incremental backtests."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from nautilus_trader.core.datetime import dt_to_unix_nanos

from data_pipeline.catalog import MarketDataCatalog

DEFAULT_WATERMARK_PATH = Path("data/state/watermarks.json")


class WatermarkStore:
    """Tracks the last processed bar timestamp per bar type."""

    def __init__(self, path: Path = DEFAULT_WATERMARK_PATH) -> None:
        self._path = path

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text())

    def _save(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2, sort_keys=True))

    def get(self, bar_type: str) -> datetime | None:
        raw = self._load().get(bar_type)
        if raw is None:
            return None
        return datetime.fromisoformat(raw)

    def set(self, bar_type: str, ts: datetime) -> None:
        data = self._load()
        data[bar_type] = ts.isoformat()
        self._save(data)

    def has_new_data(self, bar_type: str, catalog: MarketDataCatalog) -> bool:
        latest = catalog.latest_ts(bar_type)
        if latest is None:
            return False
        watermark = self.get(bar_type)
        if watermark is None:
            return True
        return dt_to_unix_nanos(latest) > dt_to_unix_nanos(watermark)
