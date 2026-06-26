from __future__ import annotations

from pathlib import Path

from nautilus_zerodte.config.loader import load_config
from nautilus_zerodte.config.schema import AppConfig
from nautilus_zerodte.models.enums import VenueAdapter


def test_load_paper_spy_profile() -> None:
    config = load_config("configs/profiles/paper_spy.yaml")
    assert config.strategy.underlying == "SPY.NYSE"
    assert config.strategy.strategy_id == "reference-001"
    assert config.strategy.strategy_class == "reference"
    assert config.venue.adapter is VenueAdapter.IB
    assert config.session.blackout_minutes_before_close == 30
    assert config.session.expiry_mode.value == "us_equity_close"
    assert config.reference.structure_selector == "ib"
    assert config.fees.model == "fixed_per_contract"
    assert config.fees.commission_per_contract == 0.65
    assert config.dry_run is True
    assert config.risk.version == "default"


def test_load_backtest_spy_fees_overlay() -> None:
    config = load_config("configs/profiles/backtest_spy.yaml")
    assert config.venue.adapter is VenueAdapter.IB
    assert config.fees.model == "fixed_per_contract"
    assert config.fees.commission_per_contract == 0.65
    assert config.reference.structure_selector == "ib"


def test_load_paper_btc_profile() -> None:
    config = load_config("configs/profiles/paper_btc.yaml")
    assert config.venue.adapter is VenueAdapter.DERIBIT
    assert config.venue.name == "DERIBIT"
    assert config.venue.base_currency == "USD"
    assert config.strategy.underlying == "BTC-PERPETUAL.DERIBIT"
    assert config.reference.option_series_id == "BTC"
    assert config.session.expiry_mode.value == "daily_utc"
    assert config.session.market_close_utc == "08:00"
    assert config.subscriptions.chain_snapshot_interval_ms == 30_000
    assert config.deribit.testnet is True
    assert config.dry_run is True
    assert config.fees.taker_fee == 0.0003
    assert config.fees.maker_fee == 0.0003


def test_load_backtest_btc_fees_overlay() -> None:
    config = load_config("configs/profiles/backtest_btc.yaml")
    assert config.fees.model == "maker_taker"
    assert config.fees.taker_fee == 0.0003


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


def test_resolved_journal_path_default() -> None:
    config = AppConfig()
    assert config.resolved_journal_path() == Path("runs/latest.jsonl")


def test_resolved_journal_path_custom_relative_uses_runs_dir() -> None:
    config = AppConfig(journal={"path": "custom/journal.jsonl"})
    base = Path("/tmp/test_runs")
    assert config.resolved_journal_path(base) == base / "custom/journal.jsonl"


def test_resolved_journal_path_strips_runs_prefix() -> None:
    config = AppConfig(journal={"path": "runs/audit/trades.jsonl"})
    base = Path("/tmp/test_runs")
    assert config.resolved_journal_path(base) == base / "audit/trades.jsonl"
