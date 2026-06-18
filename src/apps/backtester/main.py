"""Backtester CLI: `tbt-backtest run --config config/strategies/ema_cross_demo.yaml`."""

from __future__ import annotations

from pathlib import Path

import typer

from apps.backtester.runner import run_experiment
from apps.backtester.watcher import run_watcher
from core.config import DEFAULT_CONFIG_DIR, profile_from_cli, resolve_run
from core.orchestrator import RunOrchestrator
from core.run_profile import load_run_suite

app = typer.Typer(help="Run backtest experiments and persist results.")


@app.callback()
def main() -> None:
    """Backtest experiment runner."""


@app.command()
def run(
    config: Path = typer.Option(..., help="Path to the experiment YAML (config/strategies/...)"),
    env: str = typer.Option("backtest", help="Environment: backtest|paper|live"),
) -> None:
    profile = profile_from_cli(config, env, config_dir=DEFAULT_CONFIG_DIR)
    app_cfg, exp = resolve_run(profile, config_dir=DEFAULT_CONFIG_DIR)
    artifacts = run_experiment(exp, app_cfg)

    typer.echo(f"Run complete: {artifacts.run_id}")
    typer.echo(f"Results: {artifacts.run_dir}")
    for key, value in artifacts.summary["metrics"].items():
        typer.echo(f"  {key}: {value}")


@app.command()
def suite(
    config: Path = typer.Option(..., help="Path to suite YAML (config/suites/...)"),
) -> None:
    suite_cfg = load_run_suite(config)
    orchestrator = RunOrchestrator(suite_cfg, config_dir=DEFAULT_CONFIG_DIR)
    results = orchestrator.run_all()

    typer.echo(f"Suite '{suite_cfg.name}' complete ({len(results)} profiles)")
    for result in results:
        metrics = result.artifacts.summary["metrics"]
        typer.echo(f"  {result.profile_name}: {result.artifacts.run_id}")
        typer.echo(f"    pnl: {metrics.get('pnl')} sharpe: {metrics.get('sharpe_ratio')}")


@app.command()
def watch(
    suite: Path = typer.Option(..., help="Path to suite YAML (config/suites/...)"),
) -> None:
    """Long-running daemon: re-evaluate suite when catalog data updates."""
    run_watcher(suite, config_dir=DEFAULT_CONFIG_DIR)


if __name__ == "__main__":
    app()
