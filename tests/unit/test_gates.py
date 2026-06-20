from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from trade_baby_trade.actors.session import minutes_to_close, parse_close_time
from trade_baby_trade.gates.context import GateContext
from trade_baby_trade.gates.evaluator import (
    check_risk_policy,
    evaluate_edge,
    evaluate_liquidity,
    evaluate_operational,
    evaluate_pre_greek,
    evaluate_regime,
    evaluate_session,
)
from trade_baby_trade.models.enums import GateStage, RegimeTag
from trade_baby_trade.models.risk import RiskPolicy
from trade_baby_trade.models.trade_intent import TradeIntent


def _intent(**kwargs) -> TradeIntent:
    defaults = {"strategy_id": "s1", "instrument_id": "SPY.NYSE"}
    defaults.update(kwargs)
    return TradeIntent(**defaults)


def _context(**kwargs) -> GateContext:
    return GateContext(**kwargs)


def test_evaluate_edge_passes() -> None:
    result = evaluate_edge(
        _intent(edge_after_cost_bps=10.0),
        _context(min_edge_after_cost_bps=5.0),
    )
    assert result.passed


def test_evaluate_edge_fails() -> None:
    result = evaluate_edge(
        _intent(edge_after_cost_bps=1.0),
        _context(min_edge_after_cost_bps=5.0),
    )
    assert not result.passed
    assert result.failed_stage == GateStage.EDGE
    assert "min_edge_after_cost_bps" in result.breached_rules


def test_evaluate_liquidity_fails() -> None:
    result = evaluate_liquidity(
        _intent(liquidity_score=0.1),
        _context(min_liquidity_score=0.5),
    )
    assert not result.passed
    assert result.failed_stage == GateStage.LIQUIDITY


def test_evaluate_regime_blocks_tag() -> None:
    result = evaluate_regime(
        _intent(regime_tag=RegimeTag.TREND),
        _context(
            regime_tag=RegimeTag.PIN_RISK,
            blocked_regimes=frozenset({RegimeTag.PIN_RISK}),
        ),
    )
    assert not result.passed
    assert result.failed_stage == GateStage.REGIME


def test_evaluate_session_blackout() -> None:
    result = evaluate_session(
        _intent(),
        _context(session_allows_entry=False),
    )
    assert not result.passed
    assert result.failed_stage == GateStage.SESSION
    assert "session_blackout" in result.breached_rules


def test_evaluate_operational_stale_quote() -> None:
    result = evaluate_operational(
        _intent(),
        _context(underlying_quote_fresh=False, chain_snapshot_fresh=True),
    )
    assert not result.passed
    assert result.failed_stage == GateStage.OPERATIONAL
    assert "underlying_quote_stale" in result.breached_rules


def test_evaluate_operational_chain_required() -> None:
    result = evaluate_operational(
        _intent(),
        _context(
            underlying_quote_fresh=True,
            chain_snapshot_fresh=False,
            require_chain_snapshot=True,
        ),
    )
    assert not result.passed
    assert "chain_snapshot_stale" in result.breached_rules


def test_evaluate_operational_daily_loss() -> None:
    result = evaluate_operational(
        _intent(),
        _context(
            underlying_quote_fresh=True,
            chain_snapshot_fresh=True,
            require_chain_snapshot=False,
            daily_loss_breached=True,
        ),
    )
    assert not result.passed
    assert "daily_loss_budget" in result.breached_rules


def test_evaluate_pre_greek_stops_at_first_failure() -> None:
    result = evaluate_pre_greek(
        _intent(edge_after_cost_bps=0.0, liquidity_score=0.0),
        _context(min_edge_after_cost_bps=5.0, min_liquidity_score=0.5),
    )
    assert not result.passed
    assert result.failed_stage == GateStage.EDGE


def test_evaluate_pre_greek_all_pass() -> None:
    result = evaluate_pre_greek(
        _intent(edge_after_cost_bps=10.0, liquidity_score=0.8),
        _context(
            min_edge_after_cost_bps=5.0,
            min_liquidity_score=0.5,
            session_allows_entry=True,
            underlying_quote_fresh=True,
            chain_snapshot_fresh=True,
            require_chain_snapshot=False,
        ),
    )
    assert result.passed


def test_check_risk_policy_wrapper() -> None:
    policy = RiskPolicy(max_net_delta=10.0)
    assessment = check_risk_policy(
        policy,
        current_greeks={"delta": 0.0},
        projected_greeks={"delta": 15.0},
        intent_id=uuid4(),
    )
    assert not assessment.passed
    assert "max_net_delta" in assessment.breached_rules


def test_minutes_to_close_in_blackout_window() -> None:
    close = parse_close_time("14:45")
    now = datetime(2024, 1, 2, 14, 30, 0, tzinfo=UTC)
    assert minutes_to_close(now, close) == 15


def test_minutes_to_close_after_close() -> None:
    close = parse_close_time("14:45")
    now = datetime(2024, 1, 2, 15, 0, 0, tzinfo=UTC)
    assert minutes_to_close(now, close) == 0
