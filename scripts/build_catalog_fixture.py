#!/usr/bin/env python3
"""Generate the committed minimal Parquet catalog fixture for backtest smoke tests."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytz
from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import OptionGreeks, QuoteTick
from nautilus_trader.model.enums import AssetClass, OptionKind
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import OptionContract, OptionSpread
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
from nautilus_trader.test_kit.mocks.data import setup_catalog
from nautilus_trader.test_kit.providers import TestInstrumentProvider

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "catalog"

EXPIRY_NS = pd.Timestamp("2024-01-02T21:00:00", tz=pytz.utc).value
ACTIVATION_NS = pd.Timestamp("2023-12-26T00:00:00", tz=pytz.utc).value
LOW_STRIKE = 400
HIGH_STRIKE = 405
TICK_COUNT = 100


def _make_spy_call(strike: int) -> OptionContract:
    sym = f"SPY20240102C{strike:08d}"
    return OptionContract(
        instrument_id=InstrumentId(symbol=Symbol(sym), venue=Venue("NYSE")),
        raw_symbol=Symbol(sym),
        asset_class=AssetClass.EQUITY,
        exchange="NYSE",
        currency=USD,
        price_precision=2,
        price_increment=Price.from_str("0.01"),
        multiplier=Quantity.from_int(100),
        lot_size=Quantity.from_int(1),
        underlying="SPY",
        option_kind=OptionKind.CALL,
        strike_price=Price.from_str(f"{strike}.00"),
        activation_ns=ACTIVATION_NS,
        expiration_ns=EXPIRY_NS,
        ts_event=0,
        ts_init=0,
    )


def _make_spy_spread(call_lo: OptionContract, call_hi: OptionContract) -> OptionSpread:
    spread_id = InstrumentId(
        symbol=Symbol(f"SPY-CS-20240102-{LOW_STRIKE}_{HIGH_STRIKE}"),
        venue=Venue("NYSE"),
    )
    return OptionSpread(
        instrument_id=spread_id,
        raw_symbol=spread_id.symbol,
        asset_class=AssetClass.EQUITY,
        exchange="NYSE",
        underlying="SPY",
        strategy_type="BAG",
        activation_ns=ACTIVATION_NS,
        expiration_ns=EXPIRY_NS,
        currency=USD,
        price_precision=2,
        price_increment=Price.from_str("0.01"),
        multiplier=Quantity.from_int(100),
        lot_size=Quantity.from_int(1),
        margin_init=Decimal(0),
        margin_maint=Decimal(0),
        maker_fee=Decimal(0),
        taker_fee=Decimal(0),
        ts_event=0,
        ts_init=0,
    )


def _quote_ticks(instrument, base_price: float, start_ns: int, step_ns: int) -> list[QuoteTick]:
    ticks: list[QuoteTick] = []
    for i in range(TICK_COUNT):
        ts = start_ns + i * step_ns
        bid = instrument.make_price(base_price + i * instrument.price_increment.as_double())
        ask = instrument.make_price(bid.as_double() + instrument.price_increment.as_double())
        ticks.append(
            QuoteTick(
                instrument_id=instrument.id,
                bid_price=bid,
                ask_price=ask,
                bid_size=instrument.make_qty(10.0),
                ask_size=instrument.make_qty(10.0),
                ts_event=ts,
                ts_init=ts,
            )
        )
    return ticks


def build_catalog(output: Path = CATALOG_PATH) -> tuple[int, int]:
    if output.exists():
        shutil.rmtree(output)
    catalog = setup_catalog(protocol="file", path=output)

    spy = TestInstrumentProvider.equity(symbol="SPY", venue="NYSE")
    call_lo = _make_spy_call(LOW_STRIKE)
    call_hi = _make_spy_call(HIGH_STRIKE)
    spread = _make_spy_spread(call_lo, call_hi)
    catalog.write_data([spy, call_lo, call_hi, spread])

    start_dt = datetime(2024, 1, 2, 14, 30, 0, tzinfo=timezone.utc)
    start_ns = dt_to_unix_nanos(start_dt)
    end_ns = start_ns + (TICK_COUNT - 1) * 100_000_000
    step_ns = 100_000_000

    ticks = (
        _quote_ticks(spy, 400.00, start_ns, step_ns)
        + _quote_ticks(call_lo, 2.00, start_ns, step_ns)
        + _quote_ticks(call_hi, 0.50, start_ns, step_ns)
        + _quote_ticks(spread, 1.50, start_ns, step_ns)
    )
    catalog.write_data(ticks)

    greeks: list[OptionGreeks] = []
    for idx, option in enumerate((call_lo, call_hi)):
        for i in range(TICK_COUNT):
            ts = start_ns + i * step_ns
            underlying = 400.00 + i * 0.01
            greeks.append(
                OptionGreeks(
                    instrument_id=option.id,
                    delta=0.5 - idx * 0.1,
                    gamma=0.001,
                    vega=10.0,
                    theta=-5.0,
                    rho=0.1,
                    mark_iv=0.5,
                    bid_iv=0.49,
                    ask_iv=0.51,
                    underlying_price=underlying,
                    open_interest=100.0,
                    ts_event=ts,
                    ts_init=ts,
                )
            )
    catalog.write_data(greeks)
    return start_ns, end_ns


def main() -> None:
    start_ns, end_ns = build_catalog()
    catalog = ParquetDataCatalog(str(CATALOG_PATH))
    spy = TestInstrumentProvider.equity(symbol="SPY", venue="NYSE")
    ticks = catalog.quote_ticks(instrument_ids=[spy.id])
    print(f"Catalog written to {CATALOG_PATH}")
    print(f"  ticks: {len(ticks)}")
    print(f"  data types: {catalog.list_data_types()}")
    print(f"  start: {start_ns}")
    print(f"  end:   {end_ns}")


if __name__ == "__main__":
    main()
