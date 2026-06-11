"""Databento ingestion stub.

Interface contract (to implement when wiring real historical data):
- `fetch_bars` downloads bars for one instrument/date-range from Databento,
  normalizes them to `data_pipeline.schemas.BAR_COLUMNS`, and returns the dataframe.
- Callers persist via `data_pipeline.catalog.MarketDataCatalog`, never to ad-hoc files.
- The API key comes from the `DATABENTO_API_KEY` env var (see `.env.example`),
  resolved through `core.secrets` — never passed as a literal.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.secrets import resolve_secret

DATABENTO_API_KEY_ENV = "DATABENTO_API_KEY"


def fetch_bars(
    dataset: str,
    symbol: str,
    start: datetime,
    end: datetime,
    schema: str = "ohlcv-1m",
) -> pd.DataFrame:
    """Fetch bars from Databento and return them in the normalized bar schema."""
    resolve_secret(DATABENTO_API_KEY_ENV)  # fail fast with a clear message if unset
    raise NotImplementedError(
        "Databento ingestion is not wired up yet. Implement using the `databento` client: "
        "query the timeseries API, rename columns to data_pipeline.schemas.BAR_COLUMNS, "
        "localize timestamps to UTC, and validate with validate_bar_dataframe()."
    )
