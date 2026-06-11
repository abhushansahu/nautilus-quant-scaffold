from pathlib import Path

import pytest

from core.config import deep_merge, load_config, resolve_env
from core.experiment import load_experiment

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class TestDeepMerge:
    def test_overlay_wins_on_scalars(self):
        assert deep_merge({"a": 1, "b": 2}, {"b": 3})["b"] == 3

    def test_nested_dicts_merge(self):
        base = {"risk": {"max_open_positions": 5, "max_drawdown_pct": 0.2}}
        overlay = {"risk": {"max_open_positions": 3}}
        merged = deep_merge(base, overlay)
        assert merged["risk"] == {"max_open_positions": 3, "max_drawdown_pct": 0.2}

    def test_base_not_mutated(self):
        base = {"a": {"b": 1}}
        deep_merge(base, {"a": {"b": 2}})
        assert base["a"]["b"] == 1


class TestResolveEnv:
    def test_explicit_argument_wins(self, monkeypatch):
        monkeypatch.setenv("TRADE_ENV", "live")
        assert resolve_env("paper") == "paper"

    def test_env_var_used_when_no_argument(self, monkeypatch):
        monkeypatch.setenv("TRADE_ENV", "paper")
        assert resolve_env() == "paper"

    def test_defaults_to_backtest(self, monkeypatch):
        monkeypatch.delenv("TRADE_ENV", raising=False)
        assert resolve_env() == "backtest"

    def test_unknown_env_rejected(self):
        with pytest.raises(ValueError, match="Unknown TRADE_ENV"):
            resolve_env("production")


class TestLoadConfig:
    def test_backtest_config_loads(self):
        cfg = load_config("backtest", config_dir=CONFIG_DIR)
        assert cfg.environment == "backtest"
        assert cfg.venues == []
        assert cfg.risk.max_open_positions > 0

    def test_paper_overlays_base_risk(self):
        base_cfg = load_config("backtest", config_dir=CONFIG_DIR)
        paper_cfg = load_config("paper", config_dir=CONFIG_DIR)
        # paper.yaml tightens sizing but inherits max_drawdown_pct from base.yaml
        assert paper_cfg.risk.max_notional_per_order < base_cfg.risk.max_notional_per_order
        assert paper_cfg.risk.max_drawdown_pct == base_cfg.risk.max_drawdown_pct

    def test_live_config_references_secrets_by_name_only(self):
        cfg = load_config("live", config_dir=CONFIG_DIR)
        binance = next(v for v in cfg.venues if v.name == "BINANCE")
        assert binance.api_key_env == "BINANCE_API_KEY"
        assert binance.api_secret_env == "BINANCE_API_SECRET"


class TestExperimentConfig:
    def test_demo_experiment_loads(self):
        exp = load_experiment(CONFIG_DIR / "strategies" / "ema_cross_demo.yaml")
        assert exp.name == "ema_cross_demo"
        assert exp.strategy.key == "ema_cross"
        assert exp.strategy.params["fast_period"] < exp.strategy.params["slow_period"]
        assert exp.data.source == "synthetic"
        assert exp.data.num_bars > 1
