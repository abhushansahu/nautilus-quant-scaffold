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
    """Request emergency flatten — journals intent; session flatten is automatic when node runs."""
    app_config = load_config(config)
    journal_path = app_config.resolved_journal_path()
    journal = Journal(journal_path)
    journal.record(
        GateStage.LIFECYCLE,
        payload={
            "event": "FLATTEN_REQUEST",
            "strategy_id": app_config.strategy.strategy_id,
            "note": "Live flatten requires running node; SessionActor flatten_signal is automatic",
        },
        strategy_id=app_config.strategy.strategy_id,
        level="WARN",
    )
    typer.echo(
        f"Flatten request recorded in journal: {journal_path}. "
        "In-position strategies flatten on SessionActor blackout when the node is running."
    )


@journal_app.command("report")
def journal_report(
    path: Path = typer.Option(..., "--path", "-p", help="JSONL journal file."),
) -> None:
    """Report gate failures by stage and breached rule — for policy tuning."""
    entries = Journal.load(path)
    gate_stages = {
        GateStage.EDGE,
        GateStage.LIQUIDITY,
        GateStage.REGIME,
        GateStage.SESSION,
        GateStage.GREEK,
        GateStage.OPERATIONAL,
        GateStage.RISK_ENGINE,
    }
    by_stage: dict[str, int] = {}
    by_rule: dict[str, int] = {}

    for entry in entries:
        if entry.stage not in gate_stages:
            continue
        if entry.payload.get("event") not in {"GATE_REJECT", "ORDER_DENIED"}:
            continue
        by_stage[entry.stage.value] = by_stage.get(entry.stage.value, 0) + 1
        for rule in entry.payload.get("breached_rules", []):
            by_rule[str(rule)] = by_rule.get(str(rule), 0) + 1

    typer.echo(f"Gate rejection report: {path}")
    typer.echo(f"Total rejections: {sum(by_stage.values())}")
    if by_stage:
        typer.echo("\nBy stage:")
        for stage, count in sorted(by_stage.items()):
            typer.echo(f"  {stage}: {count}")
    if by_rule:
        typer.echo("\nBy breached rule:")
        for rule, count in sorted(by_rule.items(), key=lambda x: (-x[1], x[0])):
            typer.echo(f"  {rule}: {count}")
    if not by_stage and not by_rule:
        typer.echo("No gate rejections found.")


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
