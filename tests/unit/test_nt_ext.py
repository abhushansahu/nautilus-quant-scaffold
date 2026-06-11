from datetime import UTC, datetime

import pytest
from nautilus_trader.model.enums import OptionKind
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from core.config import RiskSettings
from core.experiment import StrategySpec
from nt_ext.factories import UnknownStrategyError, build_strategy
from nt_ext.risk.engine import build_risk_engine_config
from nt_ext.strategies.multi_asset.ema_cross import EMACross
from nt_ext.strategies.options.selection import select_option_contract

RISK = RiskSettings(max_notional_per_order=200_000, max_open_positions=1, max_drawdown_pct=0.5)


def ema_spec(**param_overrides) -> StrategySpec:
    params = {"fast_period": 10, "slow_period": 30, "trade_size": 100_000}
    params.update(param_overrides)
    return StrategySpec(
        key="ema_cross",
        instrument_id="EUR/USD.SIM",
        bar_type="EUR/USD.SIM-1-MINUTE-MID-EXTERNAL",
        params=params,
    )


class TestStrategyFactory:
    def test_builds_ema_cross_with_risk_wiring(self):
        strategy = build_strategy(ema_spec(), risk=RISK)
        assert isinstance(strategy, EMACross)
        assert strategy.config.fast_period == 10
        assert strategy.config.slow_period == 30
        assert {rule.name for rule in strategy.risk_rules} == {
            "max_notional_per_order",
            "max_open_positions",
        }
        assert strategy.drawdown_tracker is not None
        assert strategy.drawdown_tracker.max_drawdown_pct == 0.5

    def test_no_risk_means_no_rules(self):
        strategy = build_strategy(ema_spec())
        assert strategy.risk_rules == []
        assert strategy.drawdown_tracker is None

    def test_unknown_key_raises(self):
        spec = ema_spec()
        spec = spec.model_copy(update={"key": "nope"})
        with pytest.raises(UnknownStrategyError, match="nope"):
            build_strategy(spec)

    def test_invalid_periods_rejected(self):
        with pytest.raises(ValueError, match="fast_period"):
            build_strategy(ema_spec(fast_period=30, slow_period=10))


class TestRiskEngineConfigBuilder:
    def test_maps_notional_per_instrument(self):
        config = build_risk_engine_config(RISK, ["EUR/USD.SIM", "GBP/USD.SIM"])
        assert config.max_notional_per_order == {
            "EUR/USD.SIM": 200_000,
            "GBP/USD.SIM": 200_000,
        }


class TestOptionSelection:
    def test_selects_matching_contract(self):
        aapl_call = TestInstrumentProvider.aapl_option()  # AAPL CALL, strike 149, exp 2021-12-17
        non_option = TestInstrumentProvider.default_fx_ccy("EUR/USD")
        selected = select_option_contract(
            instruments=[non_option, aapl_call],
            underlying="AAPL",
            option_kind=OptionKind.CALL,
            target_strike=150.0,
        )
        assert selected is aapl_call

    def test_filters_by_kind_and_expiry(self):
        aapl_call = TestInstrumentProvider.aapl_option()
        assert (
            select_option_contract(
                instruments=[aapl_call],
                underlying="AAPL",
                option_kind=OptionKind.PUT,
                target_strike=150.0,
            )
            is None
        )
        assert (
            select_option_contract(
                instruments=[aapl_call],
                underlying="AAPL",
                option_kind=OptionKind.CALL,
                target_strike=150.0,
                expires_after=datetime(2030, 1, 1, tzinfo=UTC),
            )
            is None
        )

    def test_no_candidates_returns_none(self):
        assert (
            select_option_contract(
                instruments=[],
                underlying="AAPL",
                option_kind=OptionKind.CALL,
                target_strike=150.0,
            )
            is None
        )
