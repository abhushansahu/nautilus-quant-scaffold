from __future__ import annotations

from pathlib import Path

from trade_baby_trade.config.loader import load_config


def test_load_paper_spy_profile() -> None:
    config = load_config("configs/profiles/paper_spy.yaml")
    assert config.strategy.underlying == "SPY.NYSE"
    assert config.strategy.strategy_id == "skeleton-001"
    assert config.session.blackout_minutes_before_close == 30
    assert config.risk.version == "default"


def test_layered_risk_overlay(tmp_path: Path) -> None:
    configs_root = tmp_path / "configs"
    (configs_root / "risk").mkdir(parents=True)
    (configs_root / "session").mkdir()
    (configs_root / "strategies").mkdir()
    (configs_root / "profiles").mkdir()

    (configs_root / "base.yaml").write_text("trader_id: TEST\n")
    (configs_root / "risk" / "default.yaml").write_text("risk:\n  version: default\n")
    (configs_root / "session" / "us_equity.yaml").write_text(
        "session:\n  blackout_minutes_before_close: 30\n"
    )
    (configs_root / "strategies" / "reference.yaml").write_text(
        "strategy:\n  underlying: SPY.NYSE\n"
    )
    (configs_root / "profiles" / "test.yaml").write_text("risk:\n  version: conservative\n")

    config = load_config(configs_root / "profiles" / "test.yaml")
    assert config.risk.version == "conservative"
    assert config.strategy.underlying == "SPY.NYSE"
