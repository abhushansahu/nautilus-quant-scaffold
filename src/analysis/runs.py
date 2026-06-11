"""Load persisted backtest run artifacts into analysis-ready series/frames."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def parse_money(value: str | float) -> float:
    """Parse engine money strings like '432.57 USD' (or plain numbers) to float."""
    if isinstance(value, int | float):
        return float(value)
    return float(str(value).split(" ")[0].replace(",", "").replace("_", ""))


def load_summary(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "summary.json").read_text())


def load_equity(run_dir: Path) -> pd.Series:
    """Equity curve (account total per timestamp) from account.parquet."""
    account = pd.read_parquet(run_dir / "account.parquet")
    equity = pd.Series(
        account["total"].map(parse_money).to_numpy(),
        index=pd.DatetimeIndex(account["index"]),
        name="equity",
    )
    # Multiple balance updates can share a timestamp; keep the latest per ts.
    return equity.groupby(level=0).last()


def load_trade_pnls(run_dir: Path) -> pd.Series:
    """Realized PnL per closed position from positions.parquet."""
    positions = pd.read_parquet(run_dir / "positions.parquet")
    if positions.empty:
        return pd.Series(dtype=float, name="realized_pnl")
    closed = positions[positions["realized_pnl"].notna()]
    return closed["realized_pnl"].map(parse_money).rename("realized_pnl")


def load_fills(run_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(run_dir / "fills.parquet")
