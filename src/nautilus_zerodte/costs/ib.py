from __future__ import annotations

from nautilus_zerodte.config.schema import FeeScheduleConfig


def ib_commission_usd(*, fee_schedule: FeeScheduleConfig) -> float:
    """Expected round-trip commission in USD for a vertical spread entry."""
    return fee_schedule.commission_per_contract * fee_schedule.contracts_per_spread


def ib_commission_bps(*, notional_usd: float, fee_schedule: FeeScheduleConfig) -> float:
    """Expected commission in bps of spread notional (USD)."""
    if notional_usd <= 0:
        return 0.0
    return (ib_commission_usd(fee_schedule=fee_schedule) / notional_usd) * 10_000


def ib_edge_after_cost_bps(
    *,
    underlying: float,
    low_strike: float,
    high_strike: float,
    net_debit_per_share: float,
    low_spread_bps: float,
    high_spread_bps: float,
    fee_schedule: FeeScheduleConfig,
    multiplier: float = 100.0,
) -> float:
    """Intrinsic spread value vs executable debit, minus spread, slippage, and commission."""
    if net_debit_per_share <= 0 or underlying <= 0:
        return 0.0
    spread_intrinsic = max(0.0, underlying - low_strike) - max(0.0, underlying - high_strike)
    edge_before_cost_bps = ((spread_intrinsic - net_debit_per_share) / net_debit_per_share) * 10_000
    half_spread_bps = (low_spread_bps + high_spread_bps) / 2
    notional_usd = net_debit_per_share * multiplier
    commission_bps = ib_commission_bps(notional_usd=notional_usd, fee_schedule=fee_schedule)
    return (
        edge_before_cost_bps - half_spread_bps - fee_schedule.expected_slippage_bps - commission_bps
    )
