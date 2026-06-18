"""Build a NautilusTrader TradingNode config from project configuration.

Pure construction (no connections) so it stays unit-testable; secrets are
resolved from env vars at build time and passed straight into client configs —
never logged or persisted.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nautilus_trader.adapters.binance import (
    BINANCE,
    BinanceAccountType,
    BinanceDataClientConfig,
    BinanceExecClientConfig,
)
from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment
from nautilus_trader.config import LoggingConfig, TradingNodeConfig
from nautilus_trader.model.identifiers import TraderId

from core.config import AppConfig, VenueSettings
from core.secrets import resolve_secret

VenueClientFactory = Callable[[VenueSettings, bool], tuple[Any, Any]]


class UnknownVenueError(KeyError):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"No client factory wired for venue '{name}'. "
            f"Registered: {sorted(VENUE_CLIENT_FACTORIES)}. "
            "Add a factory in apps.live.node.VENUE_CLIENT_FACTORIES."
        )


def _is_truthy(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _binance_client_factory(
    venue: VenueSettings,
    default_testnet: bool,
) -> tuple[BinanceDataClientConfig, BinanceExecClientConfig]:
    if venue.api_key_env is None or venue.api_secret_env is None:
        raise ValueError(f"Venue '{venue.name}' config must set api_key_env and api_secret_env")
    api_key = resolve_secret(venue.api_key_env)
    api_secret = resolve_secret(venue.api_secret_env)
    testnet = _is_truthy(
        resolve_secret(venue.testnet_env, required=False) if venue.testnet_env else None,
        default=default_testnet,
    )
    environment = BinanceEnvironment.TESTNET if testnet else BinanceEnvironment.LIVE
    data_cfg = BinanceDataClientConfig(
        api_key=api_key,
        api_secret=api_secret,
        account_type=BinanceAccountType.SPOT,
        environment=environment,
    )
    exec_cfg = BinanceExecClientConfig(
        api_key=api_key,
        api_secret=api_secret,
        account_type=BinanceAccountType.SPOT,
        environment=environment,
    )
    return data_cfg, exec_cfg


VENUE_CLIENT_FACTORIES: dict[str, VenueClientFactory] = {
    "BINANCE": _binance_client_factory,
}

VENUE_CLIENT_KEYS: dict[str, str] = {
    "BINANCE": BINANCE,
}


def build_trading_node_config(app_cfg: AppConfig) -> TradingNodeConfig:
    """Map config/<env>.yaml venues onto live data/exec client configs."""
    if app_cfg.environment == "backtest":
        raise ValueError("TradingNode is for paper/live; use the backtester for backtests")
    if not app_cfg.venues:
        raise ValueError(f"No venues configured for environment '{app_cfg.environment}'")

    default_testnet = app_cfg.environment == "paper"

    data_clients: dict[str, Any] = {}
    exec_clients: dict[str, Any] = {}
    for venue in app_cfg.venues:
        if venue.name not in VENUE_CLIENT_FACTORIES:
            raise UnknownVenueError(venue.name)
        data_cfg, exec_cfg = VENUE_CLIENT_FACTORIES[venue.name](venue, default_testnet)
        client_key = VENUE_CLIENT_KEYS[venue.name]
        data_clients[client_key] = data_cfg
        exec_clients[client_key] = exec_cfg

    return TradingNodeConfig(
        trader_id=TraderId(f"TRADER-{app_cfg.environment.upper()}"),
        logging=LoggingConfig(log_level=app_cfg.logging.level),
        data_clients=data_clients,
        exec_clients=exec_clients,
    )
