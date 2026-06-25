from __future__ import annotations

from nautilus_zerodte.config.schema import FeeScheduleConfig
from nautilus_zerodte.models.enums import VenueAdapter
from nautilus_zerodte.strategies.selectors.base import StructureSelector
from nautilus_zerodte.strategies.selectors.deribit import DeribitStructureSelector


def resolve_structure_selector(
    selector_name: str,
    *,
    venue_adapter: VenueAdapter,
    underlying_symbol: str,
    option_series_expiry: str | None,
    settlement_currency: str = "BTC",
    fee_schedule: FeeScheduleConfig | None = None,
) -> StructureSelector | None:
    """Resolve a structure selector from config or venue adapter."""
    resolved = selector_name.strip().lower()
    if resolved in {"", "auto"}:
        resolved = venue_adapter.value.lower()

    if resolved == VenueAdapter.DERIBIT.value.lower():
        if option_series_expiry is None:
            msg = "option_series_expiry is required for Deribit structure selection"
            raise ValueError(msg)
        return DeribitStructureSelector(
            underlying_symbol=underlying_symbol,
            expiry=option_series_expiry,
            settlement_currency=settlement_currency,
            fee_schedule=fee_schedule,
        )
    return None
