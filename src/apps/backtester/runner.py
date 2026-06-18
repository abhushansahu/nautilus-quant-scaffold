"""Backtest runner: experiment config -> NautilusTrader BacktestEngine -> persisted results."""

from __future__ import annotations

from pathlib import Path

from apps.backtester.experiment_steps import (
    build_backtest_engine,
    collect_and_persist_results,
    load_experiment_bars,
)
from apps.backtester.results import RunArtifacts
from core.config import AppConfig
from core.experiment import ExperimentConfig
from data_pipeline.loader import BarDataLoader, DataWindow, default_loader
from models.inference import SignalModel
from models.loader import load_signal_model


def run_experiment(
    exp: ExperimentConfig,
    app_cfg: AppConfig,
    signal_model: SignalModel | None = None,
    results_dir: Path | None = None,
    data_window: DataWindow | None = None,
    profile_name: str | None = None,
    suite_name: str | None = None,
    cache_key: str | None = None,
    index_dir: Path | None = None,
    loader: BarDataLoader | None = None,
) -> RunArtifacts:
    """Run a single experiment end-to-end and persist its results. Returns the artifacts."""
    if signal_model is None and exp.strategy.model_artifact is not None:
        signal_model = load_signal_model(exp.strategy.model_artifact)

    bar_loader = loader or default_loader()
    risk = exp.risk or app_cfg.risk
    engine = build_backtest_engine(app_cfg, exp, risk)
    try:
        instrument, bars, data_range = load_experiment_bars(
            exp,
            app_cfg,
            bar_loader,
            data_window=data_window,
            cache_key=cache_key,
        )
        engine.add_instrument(instrument)
        engine.add_data(bars)
        return collect_and_persist_results(
            engine,
            exp,
            app_cfg,
            data_range,
            risk,
            signal_model,
            results_dir=results_dir,
            profile_name=profile_name,
            suite_name=suite_name,
            index_dir=index_dir,
        )
    finally:
        engine.dispose()
