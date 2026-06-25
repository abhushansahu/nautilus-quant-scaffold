from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from nautilus_zerodte.strategies.selectors.deribit import (
    DeribitStructureSelector,
    _edge_after_cost_bps,
    _strike_price,
    deribit_call_spread_id,
    deribit_expiry_label,
)


def test_deribit_expiry_label() -> None:
    assert deribit_expiry_label("2026-05-19") == "19MAY26"


def test_deribit_call_spread_id() -> None:
    spread_id = deribit_call_spread_id(
        underlying="BTC",
        expiry_label="19MAY26",
        low_strike=70_000,
        high_strike=75_000,
    )
    assert spread_id == "BTC-CS-19MAY26-70000_75000.DERIBIT"


def test_select_vertical_call_spread_from_chain() -> None:
    selector = DeribitStructureSelector(underlying_symbol="BTC", expiry="2026-05-19")
    chain = MagicMock()
    chain.is_empty.return_value = False
    chain.atm_strike = 70_000.0
    chain.strikes.return_value = [70_000.0, 75_000.0]
    chain.ts_event = 1_000_000_000
    chain.get_call_greeks.return_value = MagicMock(underlying_price=72_000.0)

    low_quote = MagicMock(bid_price=0.0400, ask_price=0.0401)
    high_quote = MagicMock(bid_price=0.0200, ask_price=0.0201)
    chain.get_call_quote.side_effect = lambda strike: {
        _strike_price(70_000.0): low_quote,
        _strike_price(75_000.0): high_quote,
    }.get(strike)
    chain.get_call.return_value = None

    selection = selector.select_from_chain(
        chain,
        strike_width=5_000,
        min_edge_after_cost_bps=0.0,
        min_liquidity_score=0.0,
    )

    assert selection is not None
    assert selection.spread_instrument_id == "BTC-CS-19MAY26-70000_75000.DERIBIT"
    assert selection.low_strike == 70_000.0
    assert selection.high_strike == 75_000.0
    assert selection.liquidity_score > 0.0
    # intrinsic spread ~0.0278 BTC, net_debit=0.0201, minus half-spread cost
    assert selection.edge_after_cost_bps == pytest.approx(3782.0, abs=5.0)
    assert selection.edge_after_cost_bps != 10.0


def test_edge_after_cost_bps_from_quotes() -> None:
    edge = _edge_after_cost_bps(
        underlying=72_000.0,
        low_strike=70_000.0,
        high_strike=75_000.0,
        net_debit=0.04,
        low_spread_bps=181.8,
        high_spread_bps=400.0,
    )
    assert edge == pytest.approx(-3346.0, abs=5.0)


def test_select_rejects_empty_chain() -> None:
    selector = DeribitStructureSelector(underlying_symbol="BTC", expiry="2026-05-19")
    chain = MagicMock()
    chain.is_empty.return_value = True

    assert (
        selector.select_from_chain(
            chain,
            strike_width=5_000,
            min_edge_after_cost_bps=0.0,
            min_liquidity_score=0.0,
        )
        is None
    )
