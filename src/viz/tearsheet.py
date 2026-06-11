"""Reusable performance tearsheet (Plotly). Analytics come from `analysis`; this
module only renders. Requires the `viz` dependency group."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.metrics import summarize_performance
from analysis.runs import load_equity, load_summary, load_trade_pnls


def build_tearsheet(run_dir: Path) -> go.Figure:
    """Equity curve, drawdown, and per-trade PnL for one backtest run."""
    equity = load_equity(run_dir)
    trade_pnls = load_trade_pnls(run_dir)
    summary = load_summary(run_dir)
    metrics = summarize_performance(equity, trade_pnls)

    drawdown = -(equity.cummax() - equity) / equity.cummax()

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=False,
        subplot_titles=("Equity curve", "Drawdown", "Per-trade realized PnL"),
        vertical_spacing=0.09,
    )
    fig.add_trace(go.Scatter(x=equity.index, y=equity.values, name="Equity"), row=1, col=1)
    fig.add_trace(
        go.Scatter(x=drawdown.index, y=drawdown.values, name="Drawdown", fill="tozeroy"),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Bar(x=list(range(len(trade_pnls))), y=trade_pnls.values, name="Trade PnL"),
        row=3,
        col=1,
    )

    title = (
        f"{summary['run_id']} | return {metrics['total_return']:.2%} | "
        f"sharpe {metrics['sharpe_ratio']:.2f} | max DD {metrics['max_drawdown']:.2%} | "
        f"hit rate {metrics['hit_rate']:.2%} | trades {metrics['n_trades']}"
    )
    fig.update_layout(title=title, height=900, showlegend=False)
    return fig


def save_tearsheet(run_dir: Path, output: Path | None = None) -> Path:
    """Render the tearsheet to a standalone HTML file (default: inside the run dir)."""
    output = output or run_dir / "tearsheet.html"
    build_tearsheet(run_dir).write_html(output, include_plotlyjs="cdn")
    return output
