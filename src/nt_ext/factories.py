"""Factories building strategies, risk rules, and models from config entries.

Both the backtester and the live node construct components exclusively through
this module, guaranteeing backtest/live parity.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from core.config import RiskSettings
from core.experiment import StrategySpec
from nt_ext.risk.rules import (
    DrawdownTracker,
    MaxNotionalPerOrderRule,
    MaxOpenPositionsRule,
    OrderRiskRule,
)
from nt_ext.strategies.base import BaseSignalStrategy
from nt_ext.strategies.multi_asset.ema_cross import EMACross, EMACrossConfig

if TYPE_CHECKING:
    from models.inference import SignalModel

# Registry key -> (config class, strategy class). New strategies register here.
STRATEGY_REGISTRY: dict[str, tuple[type, type]] = {
    "ema_cross": (EMACrossConfig, EMACross),
}

# Config params coerced to Decimal before constructing the strategy config.
_DECIMAL_PARAMS = {"trade_size"}


class UnknownStrategyError(KeyError):
    def __init__(self, key: str) -> None:
        super().__init__(
            f"Unknown strategy key '{key}'. Registered: {sorted(STRATEGY_REGISTRY)}. "
            f"Register new strategies in nt_ext.factories.STRATEGY_REGISTRY."
        )


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
    config_cls, strategy_cls = STRATEGY_REGISTRY[spec.key]

    params: dict[str, Any] = dict(spec.params)
    for name in _DECIMAL_PARAMS & params.keys():
        params[name] = Decimal(str(params[name]))

    config = config_cls(
        instrument_id=InstrumentId.from_str(spec.instrument_id),
        bar_type=BarType.from_str(spec.bar_type),
        **params,
    )
    return strategy_cls(
        config=config,
        risk_rules=build_risk_rules(risk) if risk else [],
        drawdown_tracker=DrawdownTracker(risk.max_drawdown_pct) if risk else None,
        signal_model=signal_model,
    )
