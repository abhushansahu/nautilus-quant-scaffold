from __future__ import annotations

from uuid import uuid4

from nautilus_zerodte.approval.classifier import ApprovalThresholds, classify_intent
from nautilus_zerodte.approval.handlers import AutomationHandler, HumanApprovalHandler
from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.models.diversification import DiversificationPolicy, select_intents
from nautilus_zerodte.models.enums import ActorKind
from nautilus_zerodte.models.trade_intent import TradeIntent


def _intent(
    *,
    strategy_id: str,
    instrument_id: str,
    edge: float,
) -> TradeIntent:
    return TradeIntent(
        intent_id=uuid4(),
        strategy_id=strategy_id,
        instrument_id=instrument_id,
        edge_after_cost_bps=edge,
        liquidity_score=0.8,
    )


def test_select_intents_top_n() -> None:
    policy = DiversificationPolicy(top_n=1, max_per_instrument=1, max_per_strategy=0.5)
    intents = [
        _intent(strategy_id="a", instrument_id="SPY-1", edge=10.0),
        _intent(strategy_id="b", instrument_id="SPY-2", edge=20.0),
    ]
    approved, rejected = select_intents(intents, policy)
    assert len(approved) == 1
    assert approved[0].strategy_id == "b"
    assert len(rejected) == 1


def test_select_intents_max_per_instrument() -> None:
    policy = DiversificationPolicy(top_n=3, max_per_instrument=1, max_per_strategy=1.0)
    intents = [
        _intent(strategy_id="a", instrument_id="SPY-1", edge=30.0),
        _intent(strategy_id="b", instrument_id="SPY-1", edge=25.0),
        _intent(strategy_id="c", instrument_id="SPY-2", edge=20.0),
    ]
    approved, rejected = select_intents(intents, policy)
    assert len(approved) == 2
    assert {intent.instrument_id for intent in approved} == {"SPY-1", "SPY-2"}
    assert len(rejected) == 1
    assert rejected[0].strategy_id == "b"


def test_select_intents_max_per_strategy() -> None:
    policy = DiversificationPolicy(top_n=3, max_per_instrument=2, max_per_strategy=0.5)
    intents = [
        _intent(strategy_id="a", instrument_id="SPY-1", edge=30.0),
        _intent(strategy_id="a", instrument_id="SPY-2", edge=25.0),
        _intent(strategy_id="b", instrument_id="SPY-3", edge=20.0),
    ]
    approved, rejected = select_intents(intents, policy)
    assert len(approved) == 2
    assert sum(1 for intent in approved if intent.strategy_id == "a") == 1


def test_classify_intent_human_on_edge() -> None:
    thresholds = ApprovalThresholds(human_edge_bps_threshold=50.0)
    intent = _intent(strategy_id="a", instrument_id="SPY-1", edge=60.0)
    assert classify_intent(intent, thresholds) is ActorKind.HUMAN


def test_classify_intent_automation() -> None:
    thresholds = ApprovalThresholds(
        human_edge_bps_threshold=50.0,
        human_notional_threshold=10_000.0,
    )
    intent = _intent(strategy_id="a", instrument_id="SPY-1", edge=10.0)
    assert classify_intent(intent, thresholds) is ActorKind.AUTOMATION


def test_human_approval_handler_journals_stub(tmp_path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    handler = HumanApprovalHandler(journal)
    intent = _intent(strategy_id="a", instrument_id="SPY-1", edge=10.0)
    assert handler.handle(intent, actor_kind=ActorKind.HUMAN) is True
    entries = journal.entries
    assert entries[-1].payload["event"] == "HUMAN_APPROVAL_STUB"


def test_automation_handler_journals_approval(tmp_path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    handler = AutomationHandler(journal)
    intent = _intent(strategy_id="a", instrument_id="SPY-1", edge=10.0)
    assert handler.handle(intent, actor_kind=ActorKind.AUTOMATION) is True
    entries = journal.entries
    assert entries[-1].payload["event"] == "AUTOMATION_APPROVED"
