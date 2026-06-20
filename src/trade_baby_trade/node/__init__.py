"""Dual-node factory — BacktestNode and TradingNode wiring."""

from trade_baby_trade.node.factory import build_backtest_node, build_trading_node, run_backtest

__all__ = ["build_backtest_node", "build_trading_node", "run_backtest"]
