from __future__ import annotations

import os

from nautilus_trader.common.config import InstrumentProviderConfig

from trade_baby_trade.config.schema import AppConfig
from trade_baby_trade.node.adapters.registry import VenueClientWiring


def _resolve_api_credentials(config: AppConfig) -> tuple[str | None, str | None]:
    """Read Deribit API credentials from configured env var names."""
    api_key = os.environ.get(config.deribit.api_key_env)
    api_secret = os.environ.get(config.deribit.api_secret_env)
    if config.deribit.testnet:
        api_key = api_key or os.environ.get("DERIBIT_TESTNET_API_KEY")
        api_secret = api_secret or os.environ.get("DERIBIT_TESTNET_API_SECRET")
    return api_key, api_secret


def _deribit_load_ids(config: AppConfig) -> frozenset[str]:
    """Instrument ids to eagerly load at node start."""
    load_ids: set[str] = {config.strategy.underlying}
    if config.reference.hedge_perp_instrument:
        load_ids.add(config.reference.hedge_perp_instrument)
    return frozenset(load_ids)


def build_deribit_wiring(config: AppConfig, *, dry_run: bool) -> VenueClientWiring:
    """Build Deribit live data and execution client wiring."""
    from nautilus_trader.adapters.deribit import DERIBIT
    from nautilus_trader.adapters.deribit.config import (
        DeribitDataClientConfig,
        DeribitExecClientConfig,
    )
    from nautilus_trader.adapters.deribit.factories import (
        DeribitLiveDataClientFactory,
        DeribitLiveExecClientFactory,
    )
    from nautilus_trader.core.nautilus_pyo3.deribit import DeribitEnvironment, DeribitProductType

    environment = (
        DeribitEnvironment.TESTNET if config.deribit.testnet else DeribitEnvironment.MAINNET
    )
    api_key, api_secret = _resolve_api_credentials(config)
    if not dry_run and (api_key is None or api_secret is None):
        msg = (
            "Deribit credentials missing for live trading — set "
            f"{config.deribit.api_key_env} and {config.deribit.api_secret_env}"
        )
        raise ValueError(msg)

    instrument_provider = InstrumentProviderConfig(
        load_all=False,
        load_ids=_deribit_load_ids(config),
    )
    data_kwargs = {
        "api_key": api_key,
        "api_secret": api_secret,
        "environment": environment,
        "product_types": (DeribitProductType.OPTION, DeribitProductType.FUTURE),
        "instrument_provider": instrument_provider,
        "auto_load_missing_instruments": True,
    }
    exec_kwargs = {
        "api_key": api_key,
        "api_secret": api_secret,
        "environment": environment,
        "product_types": (DeribitProductType.OPTION, DeribitProductType.FUTURE),
        "instrument_provider": instrument_provider,
    }
    return VenueClientWiring(
        data_clients={DERIBIT: DeribitDataClientConfig(**data_kwargs)},
        exec_clients={DERIBIT: DeribitExecClientConfig(**exec_kwargs)},
        data_client_factories={DERIBIT: DeribitLiveDataClientFactory},
        exec_client_factories={DERIBIT: DeribitLiveExecClientFactory},
    )
