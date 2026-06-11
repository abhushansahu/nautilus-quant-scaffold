"""Option contract selection helpers.

Options strategies subclass `BaseSignalStrategy` like any other strategy; what
differs is instrument selection. These helpers pick contracts from a universe
(e.g. `self.cache.instruments(venue)`) by underlying, kind, expiry, and strike.
"""

from __future__ import annotations

from datetime import datetime

from nautilus_trader.model.enums import OptionKind
from nautilus_trader.model.instruments import Instrument, OptionContract


def select_option_contract(
    instruments: list[Instrument],
    underlying: str,
    option_kind: OptionKind,
    target_strike: float,
    expires_after: datetime | None = None,
) -> OptionContract | None:
    """Pick the contract matching underlying/kind with the nearest expiry, then nearest strike.

    Returns None when no contract matches the filters.
    """
    candidates = [
        inst
        for inst in instruments
        if isinstance(inst, OptionContract)
        and inst.underlying == underlying
        and inst.option_kind == option_kind
        and (expires_after is None or inst.expiration_utc >= expires_after)
    ]
    if not candidates:
        return None

    nearest_expiry = min(c.expiration_ns for c in candidates)
    same_expiry = [c for c in candidates if c.expiration_ns == nearest_expiry]
    return min(same_expiry, key=lambda c: abs(c.strike_price.as_double() - target_strike))
