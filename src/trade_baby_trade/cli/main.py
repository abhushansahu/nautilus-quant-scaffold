from __future__ import annotations

from pathlib import Path

import typer

from trade_baby_trade.config.loader import load_config
from trade_baby_trade.journal.service import Journal
from trade_baby_trade.models.enums import GateStage
from trade_baby_trade.node.factory import build_trading_node, run_backtest

app = typer.Typer(
    name="trade-baby-trade",
    help="0DTE extension layer on NautilusTrader.",
    no_args_is_help=True,
)

journal_app = typer.Typer(help="Inspect JSONL audit logs.")
app.add_typer(journal_app, name="journal")


@app.command()
def backtest(
    config: Path = typer.Option(..., "--config", "-c", help="Profile YAML path."),
    catalog: Path = typer.Option(..., "--catalog", help="Parquet catalog directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Evaluate only; no order submit."),
) -> None:
    """Run a catalog backtest with the skeleton strategy."""
    app_config = load_config(config)
    if dry_run:
        app_config = app_config.model_copy(update={"dry_run": True})
    journal = run_backtest(app_config, catalog)
    typer.echo(f"Backtest complete. Journal: {journal.path}")


@app.command()
def paper(
    config: Path = typer.Option(..., "--config", "-c", help="Profile YAML path."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build node without live orders."),
) -> None:
    """Build (and optionally run) a TradingNode against IB paper."""
    app_config = load_config(config)
    if dry_run:
        app_config = app_config.model_copy(update={"dry_run": True})

    journal_path = app_config.resolved_journal_path()
    journal = Journal(journal_path)
    journal.record(
        GateStage.LIFECYCLE,
        payload={
            "event": "NODE_START",
            "node": "TradingNode",
            "dry_run": app_config.dry_run,
        },
    )
    node = build_trading_node(app_config)
    typer.echo(f"TradingNode built (dry_run={app_config.dry_run}). Journal: {journal_path}")
    if app_config.dry_run:
        journal.record(
            GateStage.LIFECYCLE,
            payload={"event": "NODE_STOP", "node": "TradingNode", "reason": "dry_run"},
        )
        return
    typer.echo("Starting live node — Ctrl+C to stop.")
    try:
        node.build()
        node.run()
    finally:
        journal.record(
            GateStage.LIFECYCLE,
            payload={"event": "NODE_STOP", "node": "TradingNode"},
        )


@app.command()
def flatten(
    config: Path = typer.Option(..., "--config", "-c", help="Profile YAML path."),
) -> None:
    """Emergency flatten-all — not yet implemented (Phase 3)."""
    app_config = load_config(config)
    journal_path = app_config.resolved_journal_path()
    journal = Journal(journal_path)
    journal.record(
        GateStage.LIFECYCLE,
        payload={"event": "FLATTEN_NOT_IMPLEMENTED"},
        level="WARN",
    )
    typer.echo("flatten: not yet implemented (Phase 3). Journal entry recorded.")


@journal_app.command("summary")
def journal_summary(
    path: Path = typer.Option(..., "--path", "-p", help="JSONL journal file."),
) -> None:
    """Summarize journal entries by stage, gate rejections, and recent events."""
    entries = Journal.load(path)
    stage_counts: dict[str, int] = {}
    gate_rejections: dict[str, int] = {}
    strategies: set[str] = set()

    gate_stages = {
        GateStage.EDGE,
        GateStage.LIQUIDITY,
        GateStage.REGIME,
        GateStage.SESSION,
        GateStage.GREEK,
        GateStage.OPERATIONAL,
    }

    for entry in entries:
        stage_counts[entry.stage.value] = stage_counts.get(entry.stage.value, 0) + 1
        if entry.strategy_id:
            strategies.add(entry.strategy_id)
        if entry.stage in gate_stages and entry.payload.get("event") == "GATE_REJECT":
            gate_rejections[entry.stage.value] = gate_rejections.get(entry.stage.value, 0) + 1

    typer.echo(f"Journal: {path}")
    typer.echo(f"Total entries: {len(entries)}")
    if strategies:
        typer.echo(f"Strategies: {', '.join(sorted(strategies))}")
    typer.echo("Stage counts:")
    for stage, count in sorted(stage_counts.items()):
        typer.echo(f"  {stage}: {count}")

    if gate_rejections:
        typer.echo("\nGate rejections:")
        for stage, count in sorted(gate_rejections.items()):
            typer.echo(f"  {stage}: {count}")

    typer.echo("\nLast 10 entries:")
    for entry in entries[-10:]:
        event = entry.payload.get("event", "")
        breached = entry.payload.get("breached_rules")
        extra = f" rules={breached}" if breached else ""
        typer.echo(
            f"  [{entry.ts.isoformat()}] {entry.stage.value}"
            f"{f'/{event}' if event else ''}"
            f"{f' strategy={entry.strategy_id}' if entry.strategy_id else ''}"
            f"{extra}"
        )


if __name__ == "__main__":
    app()
