"""Factories building strategies, risk rules, and models from config entries.

Both the backtester and the live node construct components exclusively through
this module, guaranteeing backtest/live parity.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from core.config import RiskSettings
from core.experiment import StrategySpec
from models.inference import SignalModel
from nt_ext.risk.rules import (
    DrawdownTracker,
    MaxNotionalPerOrderRule,
    MaxOpenPositionsRule,
    OrderRiskRule,
)
from nt_ext.strategies.base import BaseSignalStrategy
from nt_ext.strategies.multi_asset.ema_cross import (
    EMACross,
    EMACrossConfig,
    EmaCrossSignalEngine,
)
from nt_ext.strategies.multi_asset.switcher import SwitcherConfig, SwitcherStrategy
from nt_ext.strategies.signals import SignalEngine

# Config params coerced to Decimal before constructing the strategy config.
_DECIMAL_PARAMS = {"trade_size"}


@dataclass(frozen=True)
class StrategyBuildContext:
    spec: StrategySpec
    risk: RiskSettings | None
    signal_model: SignalModel | None
    params: dict[str, Any]


StrategyBuilder = Callable[[type, type, StrategyBuildContext], BaseSignalStrategy]
SignalEngineBuilder = Callable[[StrategySpec, SignalModel | None], SignalEngine]


class UnknownStrategyError(KeyError):
    def __init__(self, key: str) -> None:
        super().__init__(
            f"Unknown strategy key '{key}'. Registered: {sorted(STRATEGY_REGISTRY)}. "
            f"Register new strategies in nt_ext.factories.STRATEGY_REGISTRY."
        )


class UnknownSignalEngineError(KeyError):
    def __init__(self, key: str) -> None:
        super().__init__(
            f"Unknown signal engine key '{key}'. Registered: {sorted(SIGNAL_ENGINE_REGISTRY)}. "
            "Register engines in nt_ext.factories.SIGNAL_ENGINE_REGISTRY."
        )


def _coerce_decimal_params(params: dict[str, Any]) -> dict[str, Any]:
    coerced = dict(params)
    for name in _DECIMAL_PARAMS & coerced.keys():
        coerced[name] = Decimal(str(coerced[name]))
    return coerced


def _make_config(config_cls: type, ctx: StrategyBuildContext) -> Any:
    params = _coerce_decimal_params(ctx.params)
    params.pop("name", None)
    return config_cls(
        instrument_id=InstrumentId.from_str(ctx.spec.instrument_id),
        bar_type=BarType.from_str(ctx.spec.bar_type),
        **params,
    )


def _risk_wiring(risk: RiskSettings | None) -> dict[str, Any]:
    if risk is None:
        return {"risk_rules": [], "drawdown_tracker": None}
    return {
        "risk_rules": build_risk_rules(risk),
        "drawdown_tracker": DrawdownTracker(risk.max_drawdown_pct),
    }


def _default_strategy_builder(
    config_cls: type,
    strategy_cls: type,
    ctx: StrategyBuildContext,
) -> BaseSignalStrategy:
    config = _make_config(config_cls, ctx)
    return strategy_cls(
        config=config,
        signal_model=ctx.signal_model,
        **_risk_wiring(ctx.risk),
    )


def _switcher_strategy_builder(
    config_cls: type,
    strategy_cls: type,
    ctx: StrategyBuildContext,
) -> BaseSignalStrategy:
    params = dict(ctx.params)
    candidates_raw = params.pop("candidates", [])
    candidates = [
        StrategySpec(
            key=c["key"],
            instrument_id=c.get("instrument_id", ctx.spec.instrument_id),
            bar_type=c.get("bar_type", ctx.spec.bar_type),
            params=c.get("params", {}),
            model_artifact=c.get("model_artifact"),
        )
        for c in candidates_raw
    ]
    config = config_cls(
        instrument_id=InstrumentId.from_str(ctx.spec.instrument_id),
        bar_type=BarType.from_str(ctx.spec.bar_type),
        **_coerce_decimal_params(params),
    )
    return strategy_cls(
        config=config,
        candidates=candidates,
        risk=ctx.risk,
        **_risk_wiring(ctx.risk),
    )


# Registry key -> (config class, strategy class, optional custom builder).
STRATEGY_REGISTRY: dict[str, tuple[type, type, StrategyBuilder | None]] = {
    "ema_cross": (EMACrossConfig, EMACross, None),
    "switcher": (SwitcherConfig, SwitcherStrategy, _switcher_strategy_builder),
}


def _build_ema_cross_signal_engine(
    spec: StrategySpec,
    signal_model: SignalModel | None,
) -> EmaCrossSignalEngine:
    params = dict(spec.params)
    fast_period = int(params.get("fast_period", 10))
    slow_period = int(params.get("slow_period", 30))
    return EmaCrossSignalEngine(fast_period, slow_period, signal_model=signal_model)


SIGNAL_ENGINE_REGISTRY: dict[str, SignalEngineBuilder] = {
    "ema_cross": _build_ema_cross_signal_engine,
}


def build_risk_rules(risk: RiskSettings) -> list[OrderRiskRule]:
    return [
        MaxNotionalPerOrderRule(risk.max_notional_per_order),
        MaxOpenPositionsRule(risk.max_open_positions),
    ]


def build_strategy(
    spec: StrategySpec,
    risk: RiskSettings | None = None,
    signal_model: SignalModel | None = None,
) -> BaseSignalStrategy:
    """Build a fully-wired strategy instance from its config spec."""
    if spec.key not in STRATEGY_REGISTRY:
        raise UnknownStrategyError(spec.key)
    config_cls, strategy_cls, builder_fn = STRATEGY_REGISTRY[spec.key]
    ctx = StrategyBuildContext(
        spec=spec,
        risk=risk,
        signal_model=signal_model,
        params=dict(spec.params),
    )
    builder = builder_fn or _default_strategy_builder
    return builder(config_cls, strategy_cls, ctx)


def _resolve_signal_model(spec: StrategySpec) -> SignalModel | None:
    if spec.model_artifact is None:
        return None
    from models.loader import load_signal_model

    return load_signal_model(spec.model_artifact)


def build_signal_engine(
    spec: StrategySpec,
    signal_model: SignalModel | None = None,
) -> SignalEngine:
    """Build a composable signal engine for meta-strategies (e.g. switcher)."""
    if spec.key not in SIGNAL_ENGINE_REGISTRY:
        raise UnknownSignalEngineError(spec.key)
    resolved_model = signal_model if signal_model is not None else _resolve_signal_model(spec)
    return SIGNAL_ENGINE_REGISTRY[spec.key](spec, resolved_model)
