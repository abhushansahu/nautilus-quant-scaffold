"""Declarative run profiles and suite configuration for parallel evaluation."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from core.config import TradeEnv, load_yaml


class MlFeedbackConfig(BaseModel):
    enabled: bool = False
    train_command: str = "mlp"


class RunProfile(BaseModel):
    name: str
    experiment: Path
    environment: TradeEnv
    catalog_path: Path | None = None
    results_dir: Path | None = None
    cache_key: str | None = None


class RunSuite(BaseModel):
    name: str
    profiles: list[RunProfile]
    parallelism: int = Field(default=1, ge=1)
    poll_interval_secs: int = 60
    bar_types: list[str] = []
    selection_metric: str = "sharpe_ratio"
    lookback_runs: int = 5
    ml_feedback: MlFeedbackConfig | None = None


def load_run_suite(path: Path) -> RunSuite:
    return RunSuite.model_validate(load_yaml(path))
