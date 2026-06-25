from __future__ import annotations

from nautilus_zerodte.config.schema import FeeScheduleConfig


def expected_commission_bps(
    *,
    notional: float,
    fee_schedule: FeeScheduleConfig,
) -> float:
    """Expected commission in bps of *notional* (combo fill) using venue fee schedule."""
    if notional <= 0:
        return 0.0
    rate = (
        fee_schedule.taker_fee
        if fee_schedule.entry_liquidity == "taker"
        else fee_schedule.maker_fee
    )
    return rate * 10_000


def deribit_edge_after_cost_bps(
    *,
    underlying: float,
    low_strike: float,
    high_strike: float,
    net_debit: float,
    low_spread_bps: float,
    high_spread_bps: float,
    fee_schedule: FeeScheduleConfig,
) -> float:
    """Intrinsic spread value vs executable debit, minus spread, slippage, and commission."""
    if net_debit <= 0 or underlying <= 0:
        return 0.0
    spread_intrinsic_usd = max(0.0, underlying - low_strike) - max(0.0, underlying - high_strike)
    theoretical_value_btc = spread_intrinsic_usd / underlying
    edge_before_cost_bps = ((theoretical_value_btc - net_debit) / net_debit) * 10_000
    half_spread_bps = (low_spread_bps + high_spread_bps) / 2
    commission_bps = expected_commission_bps(notional=net_debit, fee_schedule=fee_schedule)
    return (
        edge_before_cost_bps
        - half_spread_bps
        - fee_schedule.expected_slippage_bps
        - commission_bps
    )
