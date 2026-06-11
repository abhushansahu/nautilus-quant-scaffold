"""Report CLI: metrics + tearsheet for backtest runs.

`tbt-report latest` | `tbt-report show <run_id>`
"""

from __future__ import annotations

from pathlib import Path

import typer

from analysis.metrics import summarize_performance
from analysis.runs import load_equity, load_trade_pnls
from apps.backtester.results import find_latest_run
from core.config import load_config

app = typer.Typer(help="Analyze backtest runs and render tearsheets.")


@app.callback()
def main() -> None:
    """Run analysis and reporting."""


def _report(run_dir: Path) -> None:
    metrics = summarize_performance(load_equity(run_dir), load_trade_pnls(run_dir))
    typer.echo(f"Run: {run_dir.name}")
    for key, value in metrics.items():
        typer.echo(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")

    from viz.tearsheet import save_tearsheet  # deferred: requires the viz dep group

    output = save_tearsheet(run_dir)
    typer.echo(f"Tearsheet: {output}")


@app.command()
def latest(env: str = typer.Option("backtest", help="Environment: backtest|paper|live")) -> None:
    """Report on the most recent run in the configured results directory."""
    results_dir = load_config(env).results_dir
    run_dir = find_latest_run(results_dir)
    if run_dir is None:
        typer.echo(f"No runs found in {results_dir}", err=True)
        raise typer.Exit(code=1)
    _report(run_dir)


@app.command()
def show(
    run_id: str = typer.Argument(..., help="Run directory name under the results dir"),
    env: str = typer.Option("backtest", help="Environment: backtest|paper|live"),
) -> None:
    """Report on a specific run by id."""
    run_dir = load_config(env).results_dir / run_id
    if not (run_dir / "summary.json").exists():
        typer.echo(f"Run not found: {run_dir}", err=True)
        raise typer.Exit(code=1)
    _report(run_dir)


if __name__ == "__main__":
    app()
