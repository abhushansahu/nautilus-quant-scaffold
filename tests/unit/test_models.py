from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from trade_baby_trade.models.enums import GateStage, RegimeTag
from trade_baby_trade.models.journal import JournalEntry
from trade_baby_trade.models.risk import RiskPolicy
from trade_baby_trade.models.trade_intent import TradeIntent


def test_trade_intent_defaults() -> None:
    intent = TradeIntent(strategy_id="s1", instrument_id="SPY.NYSE")
    assert intent.regime_tag == RegimeTag.UNKNOWN
    assert intent.intent_id is not None


def test_risk_policy_check_passes() -> None:
    policy = RiskPolicy(max_net_delta=100.0, max_net_gamma=50.0, max_net_vega=10_000.0)
    assessment = policy.check(
        current_greeks={"delta": 10.0},
        projected_greeks={"delta": 20.0, "gamma": 5.0, "vega": 100.0},
        intent_id=uuid4(),
    )
    assert assessment.passed
    assert assessment.breached_rules == []


def test_risk_policy_check_breaches_delta() -> None:
    policy = RiskPolicy(max_net_delta=10.0)
    assessment = policy.check(
        current_greeks={"delta": 0.0},
        projected_greeks={"delta": 15.0},
    )
    assert not assessment.passed
    assert "max_net_delta" in assessment.breached_rules


def test_journal_entry_has_strategy_id() -> None:
    entry = JournalEntry(
        stage=GateStage.LIFECYCLE,
        strategy_id="skeleton-001",
        payload={"event": "STRATEGY_START"},
    )
    assert entry.strategy_id == "skeleton-001"


def test_risk_policy_from_config_decimal() -> None:
    policy = RiskPolicy(max_daily_loss=Decimal("500.00"))
    assert policy.max_daily_loss == Decimal("500.00")
