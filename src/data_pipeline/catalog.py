"""Thin wrapper over NautilusTrader's ParquetDataCatalog.

All persisted market data goes through this module so storage layout stays consistent.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from nautilus_trader.core.datetime import dt_to_unix_nanos, unix_nanos_to_dt
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.persistence.catalog import ParquetDataCatalog


class MarketDataCatalog:
    """Project-level access point for the Parquet data catalog."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._catalog = ParquetDataCatalog(str(self._path))

    @property
    def path(self) -> Path:
        return self._path

    @property
    def raw(self) -> ParquetDataCatalog:
        """Escape hatch to the underlying NautilusTrader catalog."""
        return self._catalog

    def write_instrument(self, instrument: Instrument) -> None:
        self._catalog.write_data([instrument])

    def write_bars(self, bars: list[Bar]) -> None:
        if not bars:
            return
        self._catalog.write_data(bars)

    def read_bars(
        self,
        bar_type: BarType | str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Bar]:
        bars = self._catalog.bars(bar_types=[str(bar_type)])
        if start is not None:
            start_ns = dt_to_unix_nanos(start)
            bars = [bar for bar in bars if bar.ts_event >= start_ns]
        if end is not None:
            end_ns = dt_to_unix_nanos(end)
            bars = [bar for bar in bars if bar.ts_event <= end_ns]
        return bars

    def latest_ts(self, bar_type: BarType | str) -> datetime | None:
        bars = self.read_bars(bar_type)
        if not bars:
            return None
        return unix_nanos_to_dt(bars[-1].ts_event)

    def instruments(self) -> list[Instrument]:
        return self._catalog.instruments()
