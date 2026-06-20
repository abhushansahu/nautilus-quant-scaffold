from __future__ import annotations

from pathlib import Path

from trade_baby_trade.config.schema import AppConfig
from trade_baby_trade.node.factory import _strategy_config


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
