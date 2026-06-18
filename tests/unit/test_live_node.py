from pathlib import Path

import pytest
from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment

from apps.live.node import UnknownVenueError, build_trading_node_config
from core.config import VenueSettings, load_config
from core.secrets import MissingSecretError

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture()
def binance_env(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "test-key")
    monkeypatch.setenv("BINANCE_API_SECRET", "test-secret")
    monkeypatch.setenv("BINANCE_TESTNET", "true")


class TestBuildTradingNodeConfig:
    def test_paper_config_builds_binance_clients(self, binance_env):
        app_cfg = load_config("paper", config_dir=CONFIG_DIR)
        node_cfg = build_trading_node_config(app_cfg)
        assert str(node_cfg.trader_id) == "TRADER-PAPER"
        assert "BINANCE" in node_cfg.data_clients
        assert "BINANCE" in node_cfg.exec_clients
        assert node_cfg.exec_clients["BINANCE"].environment == BinanceEnvironment.TESTNET
        assert node_cfg.exec_clients["BINANCE"].api_key == "test-key"

    def test_paper_defaults_to_testnet_when_unset(self, binance_env, monkeypatch):
        monkeypatch.delenv("BINANCE_TESTNET", raising=False)
        app_cfg = load_config("paper", config_dir=CONFIG_DIR)
        node_cfg = build_trading_node_config(app_cfg)
        assert node_cfg.exec_clients["BINANCE"].environment == BinanceEnvironment.TESTNET

    def test_missing_secret_fails_fast(self, monkeypatch):
        monkeypatch.delenv("BINANCE_API_KEY", raising=False)
        monkeypatch.delenv("BINANCE_API_SECRET", raising=False)
        app_cfg = load_config("paper", config_dir=CONFIG_DIR)
        with pytest.raises(MissingSecretError):
            build_trading_node_config(app_cfg)

    def test_backtest_env_rejected(self):
        app_cfg = load_config("backtest", config_dir=CONFIG_DIR)
        with pytest.raises(ValueError, match="paper/live"):
            build_trading_node_config(app_cfg)

    def test_unknown_venue_raises(self, binance_env):
        app_cfg = load_config("paper", config_dir=CONFIG_DIR)
        unknown = VenueSettings(name="UNKNOWN", api_key_env="K", api_secret_env="S")
        patched = app_cfg.model_copy(update={"venues": [unknown]})
        with pytest.raises(UnknownVenueError, match="UNKNOWN"):
            build_trading_node_config(patched)
