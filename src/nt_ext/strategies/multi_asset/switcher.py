"""Meta-strategy that delegates to the active child based on evaluation state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nautilus_trader.model.data import Bar, BarType

from core.active_strategy import DEFAULT_STATE_PATH, ActiveStrategyState
from core.config import RiskSettings
from core.experiment import StrategySpec
from nt_ext.strategies.base import BaseSignalStrategy, BaseSignalStrategyConfig


class SwitcherConfig(BaseSignalStrategyConfig):  # type: ignore[misc]
    state_path: str = str(DEFAULT_STATE_PATH)
    reevaluate_every_bars: int = 10
    flatten_on_switch: bool = True


def _wire_child(parent: BaseSignalStrategy, child: BaseSignalStrategy) -> None:
    """Route child order/portfolio calls through the live switcher instance."""
    child.portfolio = parent.portfolio
    child.cache = parent.cache
    child.order_factory = parent.order_factory
    child.log = parent.log
    child.enter_long = parent.enter_long
    child.enter_short = parent.enter_short
    child.flatten = parent.flatten
    child.submit_market_order = parent.submit_market_order


def _profile_name(spec: StrategySpec) -> str:
    return str(spec.params.get("name", spec.key))


class SwitcherStrategy(BaseSignalStrategy):
    """Delegates signal logic to the active child strategy from active_strategy.json."""

    def __init__(
        self,
        config: SwitcherConfig,
        candidates: list[StrategySpec],
        risk: RiskSettings | None = None,
        **kwargs: Any,
    ) -> None:
        from nt_ext.factories import build_strategy

        super().__init__(config, **kwargs)
        self._state_path = Path(config.state_path)
        self._reevaluate_every = config.reevaluate_every_bars
        self._flatten_on_switch = config.flatten_on_switch
        self._children: dict[str, BaseSignalStrategy] = {}
        for spec in candidates:
            child = build_strategy(spec, risk=risk)
            self._children[_profile_name(spec)] = child
        self._active_profile: str | None = None
        self._active_child: BaseSignalStrategy | None = None
        self._bar_count = 0

    def register_indicators(self, bar_type: BarType) -> None:
        for child in self._children.values():
            child.register_indicators(bar_type)
            for attr in ("fast_ema", "slow_ema"):
                indicator = getattr(child, attr, None)
                if indicator is not None:
                    self.register_indicator_for_bars(bar_type, indicator)

    def on_start(self) -> None:
        super().on_start()
        for child in self._children.values():
            _wire_child(self, child)
        self._refresh_active_child(force=True)

    def on_signal_bar(self, bar: Bar) -> None:
        self._bar_count += 1
        if self._bar_count % self._reevaluate_every == 0:
            self._refresh_active_child()
        if self._active_child is not None:
            self._active_child.on_signal_bar(bar)

    def _refresh_active_child(self, force: bool = False) -> None:
        state = ActiveStrategyState.load(self._state_path)
        if state is None:
            if self._active_child is None and self._children:
                self._activate(next(iter(self._children)), force=force)
            return
        if not force and state.active_profile == self._active_profile:
            return
        if state.active_profile in self._children:
            self._activate(state.active_profile, force=force)

    def _activate(self, profile_name: str, force: bool = False) -> None:
        if not force and profile_name == self._active_profile:
            return
        if self._flatten_on_switch and self._active_profile is not None:
            self.flatten()
        self._active_profile = profile_name
        self._active_child = self._children[profile_name]
        self.log.info(f"Switcher activated child profile '{profile_name}'")
