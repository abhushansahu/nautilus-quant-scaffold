"""Normalized dataset schemas shared by all ingestion sources.

Every ingestion module must emit this schema so downstream consumers (catalog,
models, backtests) never care where data came from.
"""

from __future__ import annotations

import pandas as pd

# Canonical bar schema: UTC-nanosecond timestamps, float64 OHLCV.
BAR_COLUMNS = ["ts_event", "open", "high", "low", "close", "volume"]


class SchemaError(ValueError):
    """Raised when a dataframe does not conform to the normalized schema."""


def validate_bar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a normalized bar dataframe; returns it unchanged if valid."""
    missing = [c for c in BAR_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"Missing required columns: {missing}")
    if df.empty:
        raise SchemaError("Bar dataframe is empty")

    ts = df["ts_event"]
    if not pd.api.types.is_datetime64_any_dtype(ts):
        raise SchemaError("ts_event must be a datetime column")
    if ts.dt.tz is None:
        raise SchemaError("ts_event must be timezone-aware (UTC)")
    if not ts.is_monotonic_increasing:
        raise SchemaError("ts_event must be monotonically increasing")

    for col in ("open", "high", "low", "close", "volume"):
        if not pd.api.types.is_float_dtype(df[col]):
            raise SchemaError(f"Column '{col}' must be float64")

    if (df["high"] < df["low"]).any():
        raise SchemaError("Found bars with high < low")
    if ((df["high"] < df["open"]) | (df["high"] < df["close"])).any():
        raise SchemaError("Found bars with high below open/close")
    if ((df["low"] > df["open"]) | (df["low"] > df["close"])).any():
        raise SchemaError("Found bars with low above open/close")
    if (df["volume"] < 0).any():
        raise SchemaError("Found bars with negative volume")

    return df
