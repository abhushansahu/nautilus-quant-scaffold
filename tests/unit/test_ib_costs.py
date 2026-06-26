from __future__ import annotations

import pytest

from nautilus_zerodte.config.schema import FeeScheduleConfig
from nautilus_zerodte.costs.ib import ib_commission_usd, ib_edge_after_cost_bps


def test_ib_commission_usd_two_legs() -> None:
    schedule = FeeScheduleConfig(
        model="fixed_per_contract",
        commission_per_contract=0.65,
        contracts_per_spread=2,
    )
    assert ib_commission_usd(fee_schedule=schedule) == pytest.approx(1.30)


def test_ib_edge_negative_when_debit_exceeds_intrinsic() -> None:
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
        low_spread_bps=0.0,
        high_spread_bps=0.0,
        fee_schedule=schedule,
    )
    assert edge < 0.0
