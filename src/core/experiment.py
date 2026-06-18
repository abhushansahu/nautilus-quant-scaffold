"""Experiment configuration: a fully-specified, reproducible backtest run."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from core.config import RiskSettings, load_yaml


class StrategySpec(BaseModel):
    """Which strategy to run and with what parameters (resolved via nt_ext.factories)."""

    key: str
    instrument_id: str
    bar_type: str
    params: dict[str, Any] = {}
    model_artifact: Path | None = None


class DataSpec(BaseModel):
    """Where backtest data comes from: deterministic synthetic bars or the Parquet catalog."""

    source: Literal["synthetic", "catalog"] = "synthetic"
    mode: Literal["full", "incremental", "rolling"] = "full"
    start: datetime
    end: datetime | None = None
    lookback_bars: int = Field(default=500, gt=0)
    num_bars: int = Field(default=2000, gt=1)
    seed: int = 42
    bar_interval_secs: int = Field(default=60, gt=0)


class VenueSpec(BaseModel):
    name: str = "SIM"
    starting_balance: str = "1_000_000 USD"
    account_type: Literal["CASH", "MARGIN"] = "MARGIN"


class ExperimentConfig(BaseModel):
    name: str
    strategy: StrategySpec
    data: DataSpec
    venue: VenueSpec = VenueSpec()
    risk: RiskSettings | None = None


def load_experiment(path: Path) -> ExperimentConfig:
    return ExperimentConfig.model_validate(load_yaml(path))
