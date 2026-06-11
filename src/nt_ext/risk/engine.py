"""Maps project risk settings onto NautilusTrader's RiskEngine configuration."""

from __future__ import annotations

from nautilus_trader.config import RiskEngineConfig

from core.config import RiskSettings


def build_risk_engine_config(
    risk: RiskSettings,
    instrument_ids: list[str],
) -> RiskEngineConfig:
    """Build the platform-level RiskEngine config from project risk settings.

    `max_notional_per_order` is enforced by NautilusTrader per instrument; the
    softer strategy-level rules live in `nt_ext.risk.rules`.
    """
    return RiskEngineConfig(
        max_notional_per_order={
            instrument_id: int(risk.max_notional_per_order) for instrument_id in instrument_ids
        },
    )
