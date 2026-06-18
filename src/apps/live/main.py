"""Live/paper trading CLI: `tbt-live run --config config/strategies/<name>.yaml --env paper`.

Builds the same strategy objects as the backtester (via nt_ext.factories), wired
into a NautilusTrader TradingNode connected to the configured venues.
"""

from __future__ import annotations

from pathlib import Path

import typer

from apps.live.node import build_trading_node_config
from core.active_strategy import DEFAULT_STATE_PATH, ActiveStrategyState
from core.config import DEFAULT_CONFIG_DIR, profile_from_cli, resolve_run
from core.experiment import load_experiment
from core.run_profile import load_run_suite
from nt_ext.factories import build_strategy

app = typer.Typer(help="Run paper/live trading via a NautilusTrader TradingNode.")


@app.callback()
def main() -> None:
    """Paper/live trading node."""


@app.command()
def run(
    config: Path | None = typer.Option(
        None, help="Strategy/experiment YAML (config/strategies/...)"
    ),
    suite: Path | None = typer.Option(
        None, help="Suite YAML; uses active_strategy.json + switcher_demo.yaml"
    ),
    env: str = typer.Option("paper", help="Environment: paper|live"),
) -> None:
    from nautilus_trader.adapters.binance import (  # deferred: heavy import
        BINANCE,
        BinanceLiveDataClientFactory,
        BinanceLiveExecClientFactory,
    )
    from nautilus_trader.live.node import TradingNode

    if config is None and suite is None:
        raise typer.BadParameter("Provide --config or --suite")

    if env == "live" and not typer.confirm("Run with REAL money on live endpoints?"):
        raise typer.Abort()

    if suite is not None:
        suite_cfg = load_run_suite(suite)
        state = ActiveStrategyState.load(DEFAULT_STATE_PATH)
        if state is None:
            raise typer.BadParameter(
                f"No active strategy state at {DEFAULT_STATE_PATH}; run watcher first"
            )
        active = next(p for p in suite_cfg.profiles if p.name == state.active_profile)
        app_cfg, _ = resolve_run(active, config_dir=DEFAULT_CONFIG_DIR)
        exp = load_experiment(DEFAULT_CONFIG_DIR / "strategies" / "switcher_demo.yaml")
        typer.echo(
            f"Suite mode: switcher with active profile '{state.active_profile}' "
            f"({state.metric}={state.metric_value})"
        )
    else:
        profile = profile_from_cli(config, env, config_dir=DEFAULT_CONFIG_DIR)  # type: ignore[arg-type]
        app_cfg, exp = resolve_run(profile, config_dir=DEFAULT_CONFIG_DIR)

    node = TradingNode(config=build_trading_node_config(app_cfg))
    node.trader.add_strategy(build_strategy(exp.strategy, risk=exp.risk or app_cfg.risk))
    node.add_data_client_factory(BINANCE, BinanceLiveDataClientFactory)
    node.add_exec_client_factory(BINANCE, BinanceLiveExecClientFactory)
    node.build()

    try:
        node.run()
    finally:
        node.dispose()


if __name__ == "__main__":
    app()
