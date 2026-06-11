"""Backtester CLI: `tbt-backtest run --config config/strategies/ema_cross_demo.yaml`."""

from __future__ import annotations

from pathlib import Path

import typer

from apps.backtester.runner import run_experiment
from core.config import load_config
from core.experiment import load_experiment

app = typer.Typer(help="Run backtest experiments and persist results.")


@app.callback()
def main() -> None:
    """Backtest experiment runner."""


@app.command()
def run(
    config: Path = typer.Option(..., help="Path to the experiment YAML (config/strategies/...)"),
    env: str = typer.Option("backtest", help="Environment: backtest|paper|live"),
) -> None:
    app_cfg = load_config(env)
    exp = load_experiment(config)
    artifacts = run_experiment(exp, app_cfg)

    typer.echo(f"Run complete: {artifacts.run_id}")
    typer.echo(f"Results: {artifacts.run_dir}")
    for key, value in artifacts.summary["metrics"].items():
        typer.echo(f"  {key}: {value}")


if __name__ == "__main__":
    app()
