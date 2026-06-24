from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from nautilus_trader.model.data import nautilus_pyo3

from trade_baby_trade.strategies.selectors.base import SpreadStructure


def deribit_expiry_ns(expiry: str, *, expiry_time_utc: str = "08:00") -> int:
    """Convert YYYY-MM-DD + HH:MM UTC to nanoseconds for OptionSeriesId."""
    hour, minute = expiry_time_utc.split(":")
    dt = datetime.strptime(expiry, "%Y-%m-%d").replace(
        hour=int(hour),
        minute=int(minute),
        tzinfo=UTC,
    )
    return int(dt.timestamp() * 1_000_000_000)


def deribit_option_series_id(
    *,
    underlying: str,
    settlement_currency: str,
    expiry: str,
    expiry_time_utc: str = "08:00",
):
    """Build OptionSeriesId aligned with Deribit daily option expiry."""
    from nautilus_trader.model.data import nautilus_pyo3

    return nautilus_pyo3.OptionSeriesId(
        "DERIBIT",
        underlying,
        settlement_currency,
        deribit_expiry_ns(expiry, expiry_time_utc=expiry_time_utc),
    )


def deribit_expiry_label(expiry: str) -> str:
    """Convert YYYY-MM-DD to Deribit combo symbol segment (e.g. 19MAY26)."""
    parsed = datetime.strptime(expiry, "%Y-%m-%d")
    return parsed.strftime("%d%b%y").upper()


def deribit_call_spread_id(
    *,
    underlying: str,
    expiry_label: str,
    low_strike: int,
    high_strike: int,
) -> str:
    """Build Deribit call-spread combo instrument id."""
    return f"{underlying}-CS-{expiry_label}-{low_strike}_{high_strike}.DERIBIT"


def _quote_liquidity(quote) -> tuple[float, float]:  # noqa: ANN001
    bid = float(getattr(quote, "bid_price", 0) or 0)
    ask = float(getattr(quote, "ask_price", 0) or 0)
    if bid <= 0 or ask <= 0:
        return 0.0, 100.0
    mid = (bid + ask) / 2
    spread_bps = ((ask - bid) / mid) * 10_000 if mid > 0 else 100.0
    liquidity = max(0.0, min(1.0, 1.0 - spread_bps / 100.0))
    return liquidity, spread_bps


def _edge_after_cost_bps(
    *,
    underlying: float,
    low_strike: float,
    high_strike: float,
    net_debit: float,
    low_spread_bps: float,
    high_spread_bps: float,
) -> float:
    """Intrinsic spread value vs executable debit, minus half-spread cost (bps of debit)."""
    if net_debit <= 0 or underlying <= 0:
        return 0.0
    spread_intrinsic_usd = max(0.0, underlying - low_strike) - max(0.0, underlying - high_strike)
    theoretical_value_btc = spread_intrinsic_usd / underlying
    edge_before_cost_bps = ((theoretical_value_btc - net_debit) / net_debit) * 10_000
    spread_cost_bps = (low_spread_bps + high_spread_bps) / 2
    return edge_before_cost_bps - spread_cost_bps


def _underlying_price(option_chain_slice, atm: float) -> float:  # noqa: ANN001
    greeks = option_chain_slice.get_call_greeks(_strike_price(atm))
    if greeks is not None and getattr(greeks, "underlying_price", None):
        return float(greeks.underlying_price)
    return atm


def _strike_price(strike: float):
    return nautilus_pyo3.Price.from_str(f"{strike:.2f}")


def _strike_float(strike) -> float:  # noqa: ANN001
    return float(strike)


class DeribitStructureSelector:
    """Select ATM call vertical spreads as Deribit CryptoOptionSpread combos."""

    def __init__(
        self,
        *,
        underlying_symbol: str = "BTC",
        expiry: str,
        settlement_currency: str = "BTC",
    ) -> None:
        self._underlying_symbol = underlying_symbol
        self._expiry = expiry
        self._expiry_label = deribit_expiry_label(expiry)
        self._settlement_currency = settlement_currency

    @property
    def expiry_label(self) -> str:
        return self._expiry_label

    def select_from_chain(
        self,
        option_chain_slice,
        *,
        strike_width: int,
        min_edge_after_cost_bps: float,
        min_liquidity_score: float,
    ) -> SpreadStructure | None:
        if option_chain_slice.is_empty():
            return None

        atm = float(option_chain_slice.atm_strike)
        strikes = sorted(_strike_float(s) for s in option_chain_slice.strikes())
        if not strikes:
            return None

        low_strike = min(strikes, key=lambda strike: abs(strike - atm))
        target_high = low_strike + strike_width
        high_strike = min(strikes, key=lambda strike: abs(strike - target_high))
        if high_strike <= low_strike:
            return None

        low_quote = option_chain_slice.get_call_quote(_strike_price(low_strike))
        high_quote = option_chain_slice.get_call_quote(_strike_price(high_strike))
        if low_quote is None or high_quote is None:
            return None

        low_liq, low_spread_bps = _quote_liquidity(low_quote)
        high_liq, high_spread_bps = _quote_liquidity(high_quote)
        liquidity = min(low_liq, high_liq)
        if liquidity < min_liquidity_score:
            return None

        low_bid = float(getattr(low_quote, "bid_price", 0) or 0)
        low_ask = float(getattr(low_quote, "ask_price", 0) or 0)
        high_bid = float(getattr(high_quote, "bid_price", 0) or 0)
        high_ask = float(getattr(high_quote, "ask_price", 0) or 0)
        net_debit = (low_ask - high_bid) if low_ask and high_bid else 0.0
        if net_debit <= 0:
            return None

        underlying = _underlying_price(option_chain_slice, low_strike)
        edge_after_cost_bps = _edge_after_cost_bps(
            underlying=underlying,
            low_strike=low_strike,
            high_strike=high_strike,
            net_debit=net_debit,
            low_spread_bps=low_spread_bps,
            high_spread_bps=high_spread_bps,
        )

        spread_id = deribit_call_spread_id(
            underlying=self._underlying_symbol,
            expiry_label=self._expiry_label,
            low_strike=int(low_strike),
            high_strike=int(high_strike),
        )
        rationale: dict[str, Any] = {
            "source": "deribit_option_chain",
            "structure": "call_vertical",
            "low_spread_bps": low_spread_bps,
            "high_spread_bps": high_spread_bps,
            "net_debit": net_debit,
            "underlying": underlying,
            "edge_after_cost_bps": edge_after_cost_bps,
            "min_edge_after_cost_bps": min_edge_after_cost_bps,
            "expiry": self._expiry,
            "settlement_currency": self._settlement_currency,
        }
        low_call = option_chain_slice.get_call(_strike_price(low_strike))
        high_call = option_chain_slice.get_call(_strike_price(high_strike))
        leg_ids: list[str] = []
        for leg in (low_call, high_call):
            if leg is not None and hasattr(leg, "instrument_id"):
                leg_ids.append(str(leg.instrument_id))

        return SpreadStructure(
            spread_instrument_id=spread_id,
            low_strike=low_strike,
            high_strike=high_strike,
            edge_after_cost_bps=edge_after_cost_bps,
            liquidity_score=liquidity,
            leg_instrument_ids=tuple(leg_ids),
            rationale=rationale,
        )
