import pytest

from nt_ext.risk.rules import (
    DrawdownTracker,
    MaxNotionalPerOrderRule,
    MaxOpenPositionsRule,
    OrderContext,
)


def ctx(notional: float = 1000.0, open_positions: int = 0) -> OrderContext:
    return OrderContext(
        instrument_id="EUR/USD.SIM",
        notional=notional,
        open_positions=open_positions,
    )


class TestMaxNotionalPerOrderRule:
    def test_approves_below_limit(self):
        rule = MaxNotionalPerOrderRule(max_notional=10_000)
        assert rule.check(ctx(notional=9_999)).approved

    def test_approves_at_limit(self):
        rule = MaxNotionalPerOrderRule(max_notional=10_000)
        assert rule.check(ctx(notional=10_000)).approved

    def test_rejects_above_limit_with_reason(self):
        rule = MaxNotionalPerOrderRule(max_notional=10_000)
        decision = rule.check(ctx(notional=10_001))
        assert not decision.approved
        assert "exceeds limit" in decision.reason

    def test_rejects_invalid_limit(self):
        with pytest.raises(ValueError):
            MaxNotionalPerOrderRule(max_notional=0)


class TestMaxOpenPositionsRule:
    def test_approves_below_limit(self):
        rule = MaxOpenPositionsRule(max_positions=2)
        assert rule.check(ctx(open_positions=1)).approved

    def test_rejects_at_limit(self):
        rule = MaxOpenPositionsRule(max_positions=2)
        decision = rule.check(ctx(open_positions=2))
        assert not decision.approved


class TestDrawdownTracker:
    def test_no_breach_within_limit(self):
        tracker = DrawdownTracker(max_drawdown_pct=0.10)
        assert tracker.update(100_000) is False
        assert tracker.update(95_000) is False  # -5% from peak
        assert tracker.breached is False

    def test_breach_at_limit(self):
        tracker = DrawdownTracker(max_drawdown_pct=0.10)
        tracker.update(100_000)
        assert tracker.update(90_000) is True  # exactly -10%
        assert tracker.breached is True

    def test_peak_ratchets_up(self):
        tracker = DrawdownTracker(max_drawdown_pct=0.10)
        tracker.update(100_000)
        tracker.update(120_000)  # new peak
        assert tracker.peak == 120_000
        assert tracker.update(110_000) is False  # only -8.3% from the new peak
        assert tracker.update(108_000) is True  # exactly -10% from the new peak

    def test_breach_is_sticky(self):
        tracker = DrawdownTracker(max_drawdown_pct=0.10)
        tracker.update(100_000)
        tracker.update(80_000)
        assert tracker.update(100_000) is True  # recovery does not un-halt

    def test_rejects_invalid_pct(self):
        with pytest.raises(ValueError):
            DrawdownTracker(max_drawdown_pct=0.0)
        with pytest.raises(ValueError):
            DrawdownTracker(max_drawdown_pct=1.5)
