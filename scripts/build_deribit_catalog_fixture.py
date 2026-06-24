#!/usr/bin/env python3
"""Generate the committed Deribit Parquet catalog fixture for Phase 5 backtests."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytz
from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.model.currencies import BTC, USD
from nautilus_trader.model.data import OptionGreeks, QuoteTick
from nautilus_trader.model.enums import OptionKind
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments.crypto_option import CryptoOption
from nautilus_trader.model.instruments.crypto_perpetual import CryptoPerpetual
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
from nautilus_trader.test_kit.providers import TestInstrumentProvider

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "catalog_deribit"

EXPIRY_NS = pd.Timestamp("2026-05-19T08:00:00", tz=pytz.utc).value
ACTIVATION_NS = pd.Timestamp("2026-05-12T00:00:00", tz=pytz.utc).value
LOW_STRIKE = 70_000
HIGH_STRIKE = 75_000
TICK_COUNT = 50


def _make_call(strike: int) -> CryptoOption:
    sym = f"BTC-19MAY26-{strike}-C"
    return CryptoOption(
        instrument_id=InstrumentId(symbol=Symbol(sym), venue=Venue("DERIBIT")),
        raw_symbol=Symbol(sym),
        underlying=BTC,
        quote_currency=USD,
        settlement_currency=BTC,
        is_inverse=False,
        option_kind=OptionKind.CALL,
        strike_price=Price.from_str(f"{strike}.00"),
        activation_ns=ACTIVATION_NS,
        expiration_ns=EXPIRY_NS,
        price_precision=2,
        size_precision=1,
        price_increment=Price.from_str("0.01"),
        size_increment=Quantity.from_str("0.1"),
        maker_fee=Decimal("0.0003"),
        taker_fee=Decimal("0.0003"),
        margin_init=Decimal(0),
        margin_maint=Decimal(0),
        max_quantity=Quantity.from_str("9000"),
        min_quantity=Quantity.from_str("0.1"),
        min_notional=Money(10.00, USD),
        ts_event=0,
        ts_init=0,
    )


def _make_perp() -> CryptoPerpetual:
    return CryptoPerpetual(
        instrument_id=InstrumentId(symbol=Symbol("BTC-PERPETUAL"), venue=Venue("DERIBIT")),
        raw_symbol=Symbol("BTC-PERPETUAL"),
        base_currency=BTC,
        quote_currency=USD,
        settlement_currency=BTC,
        is_inverse=True,
        price_precision=1,
        size_precision=0,
        price_increment=Price.from_str("0.5"),
        size_increment=Quantity.from_int(1),
        max_quantity=Quantity.from_int(1_000_000),
        min_quantity=Quantity.from_int(1),
        multiplier=Quantity.from_int(10),
        lot_size=Quantity.from_int(1),
        margin_init=Decimal("0.01"),
        margin_maint=Decimal("0.005"),
        maker_fee=Decimal("0"),
        taker_fee=Decimal("0.0005"),
        ts_event=0,
        ts_init=0,
    )


def _quote_ticks(instrument, base_price: float, start_ns: int) -> list[QuoteTick]:
    ticks: list[QuoteTick] = []
    for i in range(TICK_COUNT):
        ts = start_ns + i * 1_000_000_000
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
    catalog = ParquetDataCatalog(str(output))

    perp = _make_perp()
    call_lo = _make_call(LOW_STRIKE)
    call_hi = _make_call(HIGH_STRIKE)
    spread = TestInstrumentProvider.crypto_option_spread_inverse()
    catalog.write_data([perp, call_lo, call_hi, spread])

    start_dt = datetime(2026, 5, 19, 6, 0, 0, tzinfo=UTC)
    start_ns = dt_to_unix_nanos(start_dt)
    end_ns = start_ns + (TICK_COUNT - 1) * 1_000_000_000

    ticks = (
        _quote_ticks(perp, 72_000.0, start_ns)
        + _quote_ticks(call_lo, 0.05, start_ns)
        + _quote_ticks(call_hi, 0.02, start_ns)
        + _quote_ticks(spread, 0.03, start_ns)
    )
    catalog.write_data(ticks)

    greeks: list[OptionGreeks] = []
    for idx, option in enumerate((call_lo, call_hi)):
        for i in range(TICK_COUNT):
            ts = start_ns + i * 1_000_000_000
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
                    underlying_price=72_000.0 + i,
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
    perp = _make_perp()
    spread = TestInstrumentProvider.crypto_option_spread_inverse()
    print(f"Catalog written to {CATALOG_PATH}")
    print(f"  perp ticks: {len(catalog.quote_ticks(instrument_ids=[perp.id]))}")
    print(f"  spread ticks: {len(catalog.quote_ticks(instrument_ids=[spread.id]))}")
    print(f"  data types: {catalog.list_data_types()}")
    print(f"  start: {start_ns}")
    print(f"  end:   {end_ns}")


if __name__ == "__main__":
    main()
