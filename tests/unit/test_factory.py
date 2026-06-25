from __future__ import annotations

from pathlib import Path

from nautilus_zerodte.config.schema import AppConfig
from nautilus_zerodte.node.factory import _strategy_config


def test_unknown_strategy_class_gets_gated_skeleton_config() -> None:
    config = AppConfig(
        strategy={
            "strategy_id": "s1",
            "strategy_class": "nonexistent",
            "underlying": "SPY.NYSE",
        },
        gates={"min_edge_after_cost_bps": 7.5, "min_liquidity_score": 0.6},
        regime={"blocked_regimes": ["TREND"]},
        operational={"require_chain_snapshot": False},
        risk={"version": "test-policy", "max_net_delta": 42.0},
    )
    importable = _strategy_config(config, Path("/tmp/journal.jsonl"))

    assert "gated_skeleton" in importable.strategy_path
    assert importable.config["min_edge_after_cost_bps"] == 7.5
    assert importable.config["min_liquidity_score"] == 0.6
    assert importable.config["blocked_regimes"] == ("TREND",)
    assert importable.config["require_chain_snapshot"] is False
    assert importable.config["risk_policy"]["version"] == "test-policy"
    assert importable.config["risk_policy"]["max_net_delta"] == 42.0


def test_reference_strategy_config_wiring() -> None:
    config = AppConfig(
        strategy={
            "strategy_id": "ref-1",
            "strategy_class": "reference",
            "underlying": "SPY.NYSE",
        },
        reference={"backtest_plumbing": True, "order_qty": 2},
        dry_run=True,
    )
    importable = _strategy_config(config, Path("/tmp/journal.jsonl"))

    assert "reference" in importable.strategy_path
    assert importable.config["backtest_plumbing"] is True
    assert importable.config["order_qty"] == 2
    assert importable.config["dry_run"] is True
