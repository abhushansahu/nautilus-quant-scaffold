import numpy as np
import pandas as pd
import pytest

from analysis.metrics import (
    hit_rate,
    max_drawdown,
    profit_factor,
    returns_from_equity,
    sharpe_ratio,
    summarize_performance,
)
from analysis.runs import parse_money


class TestMetricsOnKnownData:
    def test_returns_from_equity(self):
        equity = pd.Series([100.0, 110.0, 99.0])
        returns = returns_from_equity(equity)
        np.testing.assert_allclose(returns.to_numpy(), [0.1, -0.1])

    def test_max_drawdown_known_value(self):
        equity = pd.Series([100.0, 110.0, 99.0, 108.0])
        assert max_drawdown(equity) == pytest.approx((110 - 99) / 110)

    def test_max_drawdown_monotonic_equity_is_zero(self):
        assert max_drawdown(pd.Series([100.0, 101.0, 102.0])) == 0.0

    def test_sharpe_zero_for_constant_returns(self):
        assert sharpe_ratio(pd.Series([0.01, 0.01, 0.01])) == 0.0

    def test_sharpe_known_value(self):
        returns = pd.Series([0.02, 0.0, 0.02, 0.0])
        expected = returns.mean() / returns.std(ddof=1) * np.sqrt(252)
        assert sharpe_ratio(returns) == pytest.approx(float(expected))

    def test_hit_rate(self):
        assert hit_rate(pd.Series([1.0, -1.0, 2.0, 3.0])) == 0.75
        assert hit_rate(pd.Series(dtype=float)) == 0.0

    def test_profit_factor(self):
        assert profit_factor(pd.Series([10.0, -5.0])) == 2.0
        assert profit_factor(pd.Series([10.0])) == float("inf")
        assert profit_factor(pd.Series([-10.0])) == 0.0

    def test_summarize_performance_keys_and_values(self):
        equity = pd.Series([100.0, 110.0, 99.0, 108.0])
        pnls = pd.Series([5.0, -2.0])
        summary = summarize_performance(equity, pnls)
        assert summary["total_return"] == pytest.approx(0.08)
        assert summary["n_trades"] == 2
        assert summary["hit_rate"] == 0.5
        assert 0 < summary["max_drawdown"] < 1


class TestParseMoney:
    def test_parses_currency_strings(self):
        assert parse_money("432.57 USD") == 432.57
        assert parse_money("-1,234.50 USD") == -1234.50
        assert parse_money("1_000_000 USDT") == 1_000_000.0

    def test_passes_through_numbers(self):
        assert parse_money(42) == 42.0
        assert parse_money(4.2) == 4.2
