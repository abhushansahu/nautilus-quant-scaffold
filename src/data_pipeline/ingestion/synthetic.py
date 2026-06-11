"""Deterministic synthetic bar generation for tests, demos, and RL environments.

Prices follow a seeded random walk with a slow sine-wave trend overlaid so that
trend-following strategies (e.g. EMA cross) produce meaningful crossings.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.instruments import Instrument

from data_pipeline.schemas import validate_bar_dataframe


def generate_bar_dataframe(
    start: datetime,
    num_bars: int,
    seed: int = 42,
    bar_interval_secs: int = 60,
    initial_price: float = 1.1000,
    volatility: float = 0.0006,
    trend_amplitude: float = 0.01,
    trend_period_bars: int = 400,
) -> pd.DataFrame:
    """Generate a normalized OHLCV dataframe (see `data_pipeline.schemas.BAR_COLUMNS`)."""
    rng = np.random.default_rng(seed)

    noise = rng.normal(loc=0.0, scale=volatility, size=num_bars)
    trend = trend_amplitude * np.sin(2 * np.pi * np.arange(num_bars) / trend_period_bars)
    log_close = np.log(initial_price) + np.cumsum(noise) + trend
    close = np.exp(log_close)

    open_ = np.empty(num_bars)
    open_[0] = initial_price
    open_[1:] = close[:-1]

    wick = np.abs(rng.normal(loc=0.0, scale=volatility / 2, size=num_bars)) * close
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick
    volume = rng.uniform(1e5, 1e6, size=num_bars).round(0)

    start_ts = pd.Timestamp(start)
    start_ts = (
        start_ts.tz_localize("UTC") if start_ts.tzinfo is None else start_ts.tz_convert("UTC")
    )
    ts = pd.date_range(start=start_ts, periods=num_bars, freq=f"{bar_interval_secs}s")
    df = pd.DataFrame(
        {
            "ts_event": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )
    return validate_bar_dataframe(df)


def dataframe_to_bars(df: pd.DataFrame, bar_type: BarType, instrument: Instrument) -> list[Bar]:
    """Convert a normalized bar dataframe into NautilusTrader `Bar` objects."""
    validate_bar_dataframe(df)
    bars: list[Bar] = []
    for row in df.itertuples(index=False):
        ts = dt_to_unix_nanos(row.ts_event)
        bars.append(
            Bar(
                bar_type=bar_type,
                open=instrument.make_price(row.open),
                high=instrument.make_price(row.high),
                low=instrument.make_price(row.low),
                close=instrument.make_price(row.close),
                volume=instrument.make_qty(row.volume),
                ts_event=ts,
                ts_init=ts,
            )
        )
    return bars


def generate_bars(
    bar_type: BarType,
    instrument: Instrument,
    start: datetime,
    num_bars: int,
    seed: int = 42,
    bar_interval_secs: int = 60,
) -> list[Bar]:
    """Convenience: generate NautilusTrader bars directly from the synthetic source."""
    df = generate_bar_dataframe(
        start=start,
        num_bars=num_bars,
        seed=seed,
        bar_interval_secs=bar_interval_secs,
    )
    return dataframe_to_bars(df, bar_type, instrument)
