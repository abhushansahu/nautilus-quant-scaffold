"""End-to-end smoke test: EMA-cross demo on synthetic data through the real engine."""

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from apps.backtester.runner import run_experiment
from core.config import load_config
from core.experiment import load_experiment

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def run_artifacts(tmp_path_factory):
    app_cfg = load_config("backtest", config_dir=CONFIG_DIR)
    app_cfg = app_cfg.model_copy(
        update={"logging": app_cfg.logging.model_copy(update={"level": "ERROR"})}
    )
    exp = load_experiment(CONFIG_DIR / "strategies" / "ema_cross_demo.yaml")
    results_dir = tmp_path_factory.mktemp("results")
    return run_experiment(exp, app_cfg, results_dir=results_dir)


def test_backtest_produces_trades(run_artifacts):
    metrics = run_artifacts.summary["metrics"]
    assert metrics["n_fills"] > 0
    assert metrics["n_positions"] > 0


def test_pnl_is_finite(run_artifacts):
    metrics = run_artifacts.summary["metrics"]
    assert math.isfinite(metrics["pnl"])
    assert math.isfinite(metrics["final_balance"])
    assert metrics["final_balance"] > 0


def test_result_files_written(run_artifacts):
    run_dir = run_artifacts.run_dir
    for name in ("fills.parquet", "positions.parquet", "account.parquet", "summary.json"):
        assert (run_dir / name).exists(), f"missing {name}"

    fills = pd.read_parquet(run_dir / "fills.parquet")
    assert len(fills) == run_artifacts.summary["metrics"]["n_fills"]

    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["config"]["name"] == "ema_cross_demo"
    assert summary["config"]["data"]["seed"] == 42


def test_run_is_deterministic(run_artifacts, tmp_path):
    """Same seed and config must reproduce identical fills and PnL."""
    app_cfg = load_config("backtest", config_dir=CONFIG_DIR)
    app_cfg = app_cfg.model_copy(
        update={"logging": app_cfg.logging.model_copy(update={"level": "ERROR"})}
    )
    exp = load_experiment(CONFIG_DIR / "strategies" / "ema_cross_demo.yaml")
    second = run_experiment(exp, app_cfg, results_dir=tmp_path)

    first_metrics = run_artifacts.summary["metrics"]
    second_metrics = second.summary["metrics"]
    assert second_metrics["n_fills"] == first_metrics["n_fills"]
    assert second_metrics["pnl"] == pytest.approx(first_metrics["pnl"])
