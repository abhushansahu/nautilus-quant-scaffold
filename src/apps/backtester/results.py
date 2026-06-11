"""Persist backtest outputs in the standard layout.

experiments/results/<run_id>/
    fills.parquet      raw order fills
    positions.parquet  closed + open positions snapshot
    account.parquet    account balance timeline (equity curve source)
    summary.json       config snapshot + headline metrics
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class RunArtifacts:
    run_id: str
    run_dir: Path
    summary: dict[str, Any]


def make_run_id(experiment_name: str, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%S")
    return f"{experiment_name}_{stamp}"


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    # Reports indexed by timestamp keep the index as a column for downstream tools.
    df = df.reset_index()
    # Engine reports may contain dict/list columns (e.g. account 'info'); parquet
    # cannot store empty structs, so serialize such columns to JSON strings.
    for col in df.columns:
        if df[col].dtype == object and df[col].map(lambda v: isinstance(v, dict | list)).any():
            df[col] = df[col].map(lambda v: json.dumps(v, default=str))
    df.to_parquet(path, index=False)


def write_run_results(
    results_dir: Path,
    run_id: str,
    fills: pd.DataFrame,
    positions: pd.DataFrame,
    account: pd.DataFrame,
    config_snapshot: dict[str, Any],
    metrics: dict[str, Any],
) -> RunArtifacts:
    run_dir = results_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_parquet(fills, run_dir / "fills.parquet")
    _write_parquet(positions, run_dir / "positions.parquet")
    _write_parquet(account, run_dir / "account.parquet")

    summary = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "config": config_snapshot,
        "metrics": metrics,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return RunArtifacts(run_id=run_id, run_dir=run_dir, summary=summary)


def find_latest_run(results_dir: Path) -> Path | None:
    """Return the most recent run directory (by name, which embeds the timestamp)."""
    if not results_dir.exists():
        return None
    runs = sorted(d for d in results_dir.iterdir() if (d / "summary.json").exists())
    return runs[-1] if runs else None
