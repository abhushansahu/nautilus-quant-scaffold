"""Thin wrapper over NautilusTrader's ParquetDataCatalog.

All persisted market data goes through this module so storage layout stays consistent.
"""

from __future__ import annotations

from pathlib import Path

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

    def read_bars(self, bar_type: BarType | str) -> list[Bar]:
        return self._catalog.bars(bar_types=[str(bar_type)])

    def instruments(self) -> list[Instrument]:
        return self._catalog.instruments()
