from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from nautilus_trader.model.data import nautilus_pyo3
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue

from nautilus_zerodte.config.schema import FeeScheduleConfig
from nautilus_zerodte.costs.ib import ib_commission_bps, ib_edge_after_cost_bps
from nautilus_zerodte.strategies.selectors.base import SpreadStructure


def ib_expiry_ns(expiry: str, *, market_close_utc: str = "21:00") -> int:
    """Convert YYYY-MM-DD + HH:MM UTC to nanoseconds for OptionSeriesId."""
    hour, minute = market_close_utc.split(":")
    dt = datetime.strptime(expiry, "%Y-%m-%d").replace(
        hour=int(hour),
        minute=int(minute),
        tzinfo=UTC,
    )
    return int(dt.timestamp() * 1_000_000_000)


def ib_option_series_id(
    *,
    underlying: str,
    venue: str = "NYSE",
    settlement_currency: str = "USD",
    expiry: str,
    market_close_utc: str = "21:00",
):
    """Build OptionSeriesId aligned with US equity option expiry."""
    return nautilus_pyo3.OptionSeriesId(
        venue,
        underlying,
        settlement_currency,
        ib_expiry_ns(expiry, market_close_utc=market_close_utc),
    )


def ib_expiry_label(expiry: str) -> str:
    """Convert YYYY-MM-DD to OCC symbol segment (e.g. 20240102)."""
    parsed = datetime.strptime(expiry, "%Y-%m-%d")
    return parsed.strftime("%Y%m%d")


def ib_call_instrument_id(
    *,
    underlying: str,
    expiry_label: str,
    strike: int,
    venue: str = "NYSE",
) -> InstrumentId:
    """Build a single-leg IB call OptionContract instrument id."""
    symbol = f"{underlying}{expiry_label}C{strike:08d}"
    return InstrumentId(symbol=Symbol(symbol), venue=Venue(venue))


def ib_call_spread_id(
    *,
    underlying: str,
    expiry_label: str,
    low_strike: int,
    high_strike: int,
    venue: str = "NYSE",
) -> str:
    """Build IB vertical call spread instrument id (catalog-friendly BAG symbol)."""
    return f"{underlying}-CS-{expiry_label}-{low_strike}_{high_strike}.{venue}"


def _quote_liquidity(quote) -> tuple[float, float]:  # noqa: ANN001
    bid = float(getattr(quote, "bid_price", 0) or 0)
    ask = float(getattr(quote, "ask_price", 0) or 0)
    if bid <= 0 or ask <= 0:
        return 0.0, 100.0
    mid = (bid + ask) / 2
    spread_bps = ((ask - bid) / mid) * 10_000 if mid > 0 else 100.0
    liquidity = max(0.0, min(1.0, 1.0 - spread_bps / 100.0))
    return liquidity, spread_bps


def _strike_price(strike: float):
    return nautilus_pyo3.Price.from_str(f"{strike:.2f}")


def _strike_float(strike) -> float:  # noqa: ANN001
    return float(strike)


def _underlying_price(option_chain_slice, atm: float) -> float:  # noqa: ANN001
    greeks = option_chain_slice.get_call_greeks(_strike_price(atm))
    if greeks is not None and getattr(greeks, "underlying_price", None):
        return float(greeks.underlying_price)
    return atm


class IbStructureSelector:
    """Select ATM call vertical spreads as IB BAG OptionSpread instrument ids."""

    def __init__(
        self,
        *,
        underlying_symbol: str,
        expiry: str,
        venue: str,
        market_close_utc: str,
        fee_schedule: FeeScheduleConfig,
        multiplier: float,
    ) -> None:
        self._underlying_symbol = underlying_symbol
        self._expiry = expiry
        self._expiry_label = ib_expiry_label(expiry)
        self._venue = venue
        self._market_close_utc = market_close_utc
        self._fee_schedule = fee_schedule
        self._multiplier = multiplier

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

        low_ask = float(getattr(low_quote, "ask_price", 0) or 0)
        high_bid = float(getattr(high_quote, "bid_price", 0) or 0)
        net_debit = (low_ask - high_bid) if low_ask and high_bid else 0.0
        if net_debit <= 0:
            return None

        underlying = _underlying_price(option_chain_slice, low_strike)
        edge_after_cost_bps = ib_edge_after_cost_bps(
            underlying=underlying,
            low_strike=low_strike,
            high_strike=high_strike,
            net_debit_per_share=net_debit,
            low_spread_bps=low_spread_bps,
            high_spread_bps=high_spread_bps,
            fee_schedule=self._fee_schedule,
            multiplier=self._multiplier,
        )
        if edge_after_cost_bps < min_edge_after_cost_bps:
            return None

        spread_id = ib_call_spread_id(
            underlying=self._underlying_symbol,
            expiry_label=self._expiry_label,
            low_strike=int(low_strike),
            high_strike=int(high_strike),
            venue=self._venue,
        )
        notional_usd = net_debit * self._multiplier
        rationale: dict[str, Any] = {
            "source": "ib_option_chain",
            "structure": "call_vertical_bag",
            "low_spread_bps": low_spread_bps,
            "high_spread_bps": high_spread_bps,
            "net_debit": net_debit,
            "notional_usd": notional_usd,
            "underlying": underlying,
            "edge_after_cost_bps": edge_after_cost_bps,
            "expected_commission_bps": ib_commission_bps(
                notional_usd=notional_usd,
                fee_schedule=self._fee_schedule,
            ),
            "min_edge_after_cost_bps": min_edge_after_cost_bps,
            "expiry": self._expiry,
            "venue": self._venue,
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
