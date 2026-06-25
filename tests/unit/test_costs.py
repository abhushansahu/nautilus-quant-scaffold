from __future__ import annotations

import pytest

from nautilus_zerodte.config.schema import FeeScheduleConfig
from nautilus_zerodte.costs.deribit import deribit_edge_after_cost_bps, expected_commission_bps


def test_expected_commission_bps_taker() -> None:
    schedule = FeeScheduleConfig(taker_fee=0.0003, entry_liquidity="taker")
    assert expected_commission_bps(notional=0.04, fee_schedule=schedule) == pytest.approx(3.0)


def test_deribit_edge_after_cost_includes_commission() -> None:
    schedule = FeeScheduleConfig(taker_fee=0.0003, entry_liquidity="taker")
    edge = deribit_edge_after_cost_bps(
        underlying=72_000.0,
        low_strike=70_000.0,
        high_strike=75_000.0,
        net_debit=0.04,
        low_spread_bps=181.8,
        high_spread_bps=400.0,
        fee_schedule=schedule,
    )
    # Previous half-spread-only edge was ~-3346; minus 3 bps commission
    assert edge == pytest.approx(-3349.0, abs=5.0)
