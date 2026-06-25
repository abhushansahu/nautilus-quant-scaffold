from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from nautilus_zerodte.actors.data_types import RegimeTagSnapshot, SessionPhaseSnapshot
from nautilus_zerodte.gates.context import GateContext
from nautilus_zerodte.models.enums import RegimeTag, StrategyState
from nautilus_zerodte.models.risk import RiskPolicy
from nautilus_zerodte.strategies.context import ChainEvaluationContext
from nautilus_zerodte.strategies.reference import (
    ReferenceZeroDteStrategy,
    ReferenceZeroDteStrategyConfig,
)


def _ready_strategy(tmp_path: Path) -> ReferenceZeroDteStrategy:
    config = ReferenceZeroDteStrategyConfig(
        journal_path=str(tmp_path / "journal.jsonl"),
        backtest_plumbing=True,
        min_edge_after_cost_bps=0.0,
        min_liquidity_score=0.0,
        blocked_regimes=(),
        require_chain_snapshot=False,
        dry_run=True,
    )
    strategy = ReferenceZeroDteStrategy(config)
    strategy._on_session_phase(
        SessionPhaseSnapshot(
            allows_entry=True,
            session_phase="NORMAL",
            minutes_to_expiry=120,
            flatten_signal=False,
        )
    )
    strategy._on_regime_tag(RegimeTagSnapshot(regime_tag=RegimeTag.TREND.value))
    return strategy


def test_build_intent_from_plumbing_context(tmp_path: Path) -> None:
    strategy = _ready_strategy(tmp_path)
    context = ChainEvaluationContext(
        instrument_id="SPY.NYSE",
        underlying_mid=400.0,
        atm_strike=400.0,
        edge_after_cost_bps=10.0,
        liquidity_score=0.9,
        ts_event=1,
        rationale={"source": "backtest_plumbing"},
    )
    intent = strategy.build_intent(context)
    assert intent is not None
    assert intent.instrument_id == "SPY.NYSE"
    assert intent.edge_after_cost_bps == 10.0
    assert intent.rationale["structure"] == "vertical_spread"


def test_dry_run_journals_intent_without_submit(tmp_path: Path) -> None:
    strategy = _ready_strategy(tmp_path)
    context = ChainEvaluationContext(
        instrument_id="SPY.NYSE",
        underlying_mid=400.0,
        atm_strike=400.0,
        edge_after_cost_bps=10.0,
        liquidity_score=0.9,
        ts_event=1_000_000_000,
        rationale={"source": "backtest_plumbing"},
    )
    intent = strategy.build_intent(context)
    assert intent is not None
    greeks = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0}

    gate_context = GateContext(
        regime_tag=RegimeTag.TREND,
        session_allows_entry=True,
        underlying_quote_fresh=True,
        chain_snapshot_fresh=True,
        require_chain_snapshot=False,
        risk_policy=RiskPolicy(),
    )

    with patch.object(strategy, "submit_entry") as mock_submit, patch.object(
        strategy, "_portfolio_greek_snapshot", return_value=greeks
    ), patch.object(strategy, "_build_gate_context", return_value=gate_context):
        strategy._transition(StrategyState.EVALUATING, reason="test")
        strategy._run_gate_pipeline(intent, context)
        mock_submit.assert_not_called()

    entries = strategy._journal.entries
    events = [e.payload.get("event") for e in entries]
    assert "DRY_RUN_INTENT" in events
    assert "GREEK_PASSED" in events
    assert strategy.fsm_state == StrategyState.FLAT


def test_fsm_transition_journaled(tmp_path: Path) -> None:
    strategy = _ready_strategy(tmp_path)
    strategy._transition(StrategyState.EVALUATING, reason="test")
    entries = strategy._journal.entries
    transition = [e for e in entries if e.payload.get("event") == "FSM_TRANSITION"][-1]
    assert transition.payload["from"] == "Flat"
    assert transition.payload["to"] == "Evaluating"
