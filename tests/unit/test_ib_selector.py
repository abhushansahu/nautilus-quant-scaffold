from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from nautilus_zerodte.config.schema import FeeScheduleConfig
from nautilus_zerodte.costs.ib import ib_commission_bps, ib_edge_after_cost_bps
from nautilus_zerodte.strategies.selectors.ib import (
    IbStructureSelector,
    _strike_price,
    ib_call_spread_id,
    ib_expiry_label,
)


def _ib_fee_schedule() -> FeeScheduleConfig:
    return FeeScheduleConfig(
        model="fixed_per_contract",
        commission_per_contract=0.65,
        contracts_per_spread=2,
    )


def _ib_selector() -> IbStructureSelector:
    return IbStructureSelector(
        underlying_symbol="SPY",
        expiry="2024-01-02",
        venue="NYSE",
        market_close_utc="21:00",
        fee_schedule=_ib_fee_schedule(),
        multiplier=100.0,
    )


def test_ib_expiry_label() -> None:
    assert ib_expiry_label("2024-01-02") == "20240102"


def test_ib_call_spread_id() -> None:
    spread_id = ib_call_spread_id(
        underlying="SPY",
        expiry_label="20240102",
        low_strike=400,
        high_strike=405,
    )
    assert spread_id == "SPY-CS-20240102-400_405.NYSE"


def test_ib_commission_bps() -> None:
    schedule = FeeScheduleConfig(
        model="fixed_per_contract",
        commission_per_contract=0.65,
        contracts_per_spread=2,
    )
    # $1.30 commission on $150 notional (1.50 * 100 multiplier)
    assert ib_commission_bps(notional_usd=150.0, fee_schedule=schedule) == pytest.approx(
        86.67, abs=0.1
    )


def test_ib_edge_after_cost_includes_commission() -> None:
    schedule = FeeScheduleConfig(
        model="fixed_per_contract",
        commission_per_contract=0.65,
        contracts_per_spread=2,
    )
    edge = ib_edge_after_cost_bps(
        underlying=400.50,
        low_strike=400.0,
        high_strike=405.0,
        net_debit_per_share=1.50,
        low_spread_bps=50.0,
        high_spread_bps=400.0,
        fee_schedule=schedule,
    )
    # intrinsic 0.50 vs debit 1.50 => -6666 bps before costs
    assert edge < -6000.0


def test_select_vertical_call_spread_from_chain() -> None:
    selector = _ib_selector()
    chain = MagicMock()
    chain.is_empty.return_value = False
    chain.atm_strike = 400.0
    chain.strikes.return_value = [400.0, 405.0]
    chain.ts_event = 1_000_000_000
    chain.get_call_greeks.return_value = MagicMock(underlying_price=400.50)

    low_quote = MagicMock(bid_price=1.99, ask_price=2.00)
    high_quote = MagicMock(bid_price=0.49, ask_price=0.50)
    chain.get_call_quote.side_effect = lambda strike: {
        _strike_price(400.0): low_quote,
        _strike_price(405.0): high_quote,
    }.get(strike)
    chain.get_call.return_value = None

    selection = selector.select_from_chain(
        chain,
        strike_width=5,
        min_edge_after_cost_bps=-10_000.0,
        min_liquidity_score=0.0,
    )

    assert selection is not None
    assert selection.spread_instrument_id == "SPY-CS-20240102-400_405.NYSE"
    assert selection.low_strike == 400.0
    assert selection.high_strike == 405.0
    assert selection.rationale["expected_commission_bps"] > 0.0


def test_select_rejects_empty_chain() -> None:
    selector = _ib_selector()
    chain = MagicMock()
    chain.is_empty.return_value = True

    assert (
        selector.select_from_chain(
            chain,
            strike_width=5,
            min_edge_after_cost_bps=0.0,
            min_liquidity_score=0.0,
        )
        is None
    )
