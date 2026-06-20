#!/usr/bin/env python3
"""Generate the committed minimal Parquet catalog fixture for backtest smoke tests."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
from nautilus_trader.test_kit.mocks.data import setup_catalog
from nautilus_trader.test_kit.providers import TestInstrumentProvider

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "catalog"


def build_catalog(output: Path = CATALOG_PATH) -> tuple[int, int]:
    if output.exists():
        shutil.rmtree(output)
    catalog = setup_catalog(protocol="file", path=output)

    spy = TestInstrumentProvider.equity(symbol="SPY", venue="NYSE")
    catalog.write_data([spy])

    start_dt = datetime(2024, 1, 2, 14, 30, 0, tzinfo=timezone.utc)
    end_dt = datetime(2024, 1, 2, 14, 35, 0, tzinfo=timezone.utc)
    start_ns = dt_to_unix_nanos(start_dt)
    end_ns = dt_to_unix_nanos(end_dt)

    ticks: list[QuoteTick] = []
    for i in range(100):
        ts = start_ns + i * 100_000_000
        ticks.append(
            QuoteTick(
                instrument_id=spy.id,
                bid_price=Price.from_str(f"{400.00 + i * 0.01:.2f}"),
                ask_price=Price.from_str(f"{400.01 + i * 0.01:.2f}"),
                bid_size=Quantity.from_int(100),
                ask_size=Quantity.from_int(100),
                ts_event=ts,
                ts_init=ts,
            )
        )
    catalog.write_data(ticks)
    return start_ns, end_ns


def main() -> None:
    start_ns, end_ns = build_catalog()
    catalog = ParquetDataCatalog(str(CATALOG_PATH))
    spy = TestInstrumentProvider.equity(symbol="SPY", venue="NYSE")
    ticks = catalog.quote_ticks(instrument_ids=[spy.id])
    print(f"Catalog written to {CATALOG_PATH}")
    print(f"  ticks: {len(ticks)}")
    print(f"  start: {start_ns}")
    print(f"  end:   {end_ns}")


if __name__ == "__main__":
    main()
