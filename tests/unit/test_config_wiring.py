from __future__ import annotations

from pathlib import Path

import pytest

from nautilus_zerodte.config.loader import load_config
from nautilus_zerodte.config.schema import (
    AppConfig,
    resolved_option_expiry_time,
    resolved_option_multiplier,
    resolved_option_series_id,
    resolved_option_venue,
    resolved_settlement_currency,
    underlying_symbol_from_id,
)
from nautilus_zerodte.node.factory import _actor_configs, _reference_strategy_config


def test_underlying_symbol_from_perp() -> None:
    assert underlying_symbol_from_id("BTC-PERPETUAL.DERIBIT") == "BTC"
    assert underlying_symbol_from_id("SPY.NYSE") == "SPY"


def test_backtest_spy_resolves_ib_wiring() -> None:
    config = load_config("configs/profiles/backtest_spy.yaml")
    assert resolved_option_venue(config) == "NYSE"
    assert resolved_option_expiry_time(config) == "21:00"
    assert resolved_option_multiplier(config) == 100.0
    assert resolved_settlement_currency(config) == "USD"
    assert resolved_option_series_id(config) == "SPY"


def test_backtest_btc_resolves_deribit_wiring() -> None:
    config = load_config("configs/profiles/backtest_btc.yaml")
    assert resolved_option_multiplier(config) == 1.0
    assert resolved_settlement_currency(config) == "BTC"
    assert resolved_option_expiry_time(config) == "08:00"
    assert resolved_option_series_id(config) == "BTC"


def test_reference_strategy_config_threads_resolved_values() -> None:
    config = load_config("configs/profiles/backtest_spy.yaml")
    wired = _reference_strategy_config(config, config.reference)
    assert wired["option_series_id"] == "SPY"
    assert wired["option_venue"] == "NYSE"
    assert wired["option_multiplier"] == 100.0
    assert wired["settlement_currency"] == "USD"
    assert wired["option_series_expiry_time_utc"] == "21:00"


def test_streaming_overlay_disabled_by_default() -> None:
    config = load_config("configs/profiles/paper_btc.yaml")
    assert config.streaming.enabled is False
    assert "QuoteTick" in config.streaming.include_types[0]


def test_ingestion_actor_registered_when_enabled() -> None:
    config = AppConfig(
        ingestion={"enabled": True},
        strategy={"underlying": "SPY.NYSE"},
        reference={"option_series_id": "SPY"},
    )
    actors = _actor_configs(config)
    assert any("ingestion" in actor.actor_path for actor in actors)


def test_resolve_stream_instance_id_single(tmp_path: Path) -> None:
    from nautilus_zerodte.node.streaming import resolve_stream_instance_id

    live = tmp_path / "run-1" / "live" / "abc-123"
    live.mkdir(parents=True)
    assert resolve_stream_instance_id(tmp_path, "run-1") == "abc-123"


def test_resolve_stream_instance_id_requires_disambiguation(tmp_path: Path) -> None:
    from nautilus_zerodte.node.streaming import resolve_stream_instance_id

    live = tmp_path / "run-1" / "live"
    (live / "a").mkdir(parents=True)
    (live / "b").mkdir(parents=True)
    with pytest.raises(ValueError, match="Multiple instance"):
        resolve_stream_instance_id(tmp_path, "run-1")
