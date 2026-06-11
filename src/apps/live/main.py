"""Live/paper trading CLI: `tbt-live run --config config/strategies/<name>.yaml --env paper`.

Builds the same strategy objects as the backtester (via nt_ext.factories), wired
into a NautilusTrader TradingNode connected to the configured venues.
"""

from __future__ import annotations

from pathlib import Path

import typer

from apps.live.node import build_trading_node_config
from core.config import load_config
from core.experiment import load_experiment
from nt_ext.factories import build_strategy

app = typer.Typer(help="Run paper/live trading via a NautilusTrader TradingNode.")


@app.callback()
def main() -> None:
    """Paper/live trading node."""


@app.command()
def run(
    config: Path = typer.Option(..., help="Strategy/experiment YAML (config/strategies/...)"),
    env: str = typer.Option("paper", help="Environment: paper|live"),
) -> None:
    from nautilus_trader.adapters.binance import (  # deferred: heavy import
        BINANCE,
        BinanceLiveDataClientFactory,
        BinanceLiveExecClientFactory,
    )
    from nautilus_trader.live.node import TradingNode

    if env == "live" and not typer.confirm("Run with REAL money on live endpoints?"):
        raise typer.Abort()

    app_cfg = load_config(env)
    exp = load_experiment(config)

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
