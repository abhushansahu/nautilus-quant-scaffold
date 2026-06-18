"""Signal intent types shared by strategies and the switcher meta-strategy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from nautilus_trader.model.data import Bar, BarType


class SignalIntent(Enum):
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    FLAT = "flat"
    NOOP = "noop"


@dataclass(frozen=True)
class PositionState:
    is_net_long: bool
    is_net_short: bool
    is_flat: bool


class SignalEngine(Protocol):
    def register_indicators(self, bar_type: BarType, register: Any) -> None: ...

    def evaluate(self, bar: Bar, position: PositionState) -> SignalIntent: ...
