"""Pure performance analytics on dataframes/series. No plotting, no engine imports."""

from __future__ import annotations

import numpy as np
import pandas as pd


def returns_from_equity(equity: pd.Series) -> pd.Series:
    """Simple per-period returns from an equity curve."""
    return equity.pct_change().dropna()


def sharpe_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    """Annualized Sharpe ratio (rf = 0). Returns 0.0 for degenerate (zero-vol) inputs."""
    if len(returns) < 2:
        return 0.0
    std = returns.std(ddof=1)
    if std == 0 or np.isnan(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(periods_per_year))


def max_drawdown(equity: pd.Series) -> float:
    """Maximum peak-to-trough drawdown as a positive fraction (0.1 = -10%)."""
    if equity.empty:
        return 0.0
    running_peak = equity.cummax()
    drawdowns = (running_peak - equity) / running_peak
    return float(drawdowns.max())


def hit_rate(pnls: pd.Series) -> float:
    """Fraction of trades with positive PnL."""
    if len(pnls) == 0:
        return 0.0
    return float((pnls > 0).mean())


def profit_factor(pnls: pd.Series) -> float:
    """Gross profit / gross loss. Returns inf when there are no losses (and some profit)."""
    gross_profit = float(pnls[pnls > 0].sum())
    gross_loss = float(-pnls[pnls < 0].sum())
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def summarize_performance(
    equity: pd.Series,
    trade_pnls: pd.Series,
    periods_per_year: int = 252,
) -> dict[str, float]:
    returns = returns_from_equity(equity)
    return {
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1) if len(equity) else 0.0,
        "sharpe_ratio": sharpe_ratio(returns, periods_per_year),
        "max_drawdown": max_drawdown(equity),
        "hit_rate": hit_rate(trade_pnls),
        "profit_factor": profit_factor(trade_pnls),
        "n_trades": int(len(trade_pnls)),
    }
