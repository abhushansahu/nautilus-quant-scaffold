from __future__ import annotations

import os

from nautilus_zerodte.config.schema import AppConfig
from nautilus_zerodte.node.adapters.registry import VenueClientWiring


def ib_adapter_available() -> bool:
    try:
        import ibapi  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("IB_HOST"))


def build_ib_wiring(config: AppConfig, *, dry_run: bool) -> VenueClientWiring:
    """Build Interactive Brokers client wiring when credentials are available."""
    if dry_run or not ib_adapter_available():
        return VenueClientWiring()

    from nautilus_trader.adapters.interactive_brokers.common import IB
    from nautilus_trader.adapters.interactive_brokers.config import (
        InteractiveBrokersDataClientConfig,
        InteractiveBrokersExecClientConfig,
        InteractiveBrokersInstrumentProviderConfig,
    )
    from nautilus_trader.adapters.interactive_brokers.factories import (
        InteractiveBrokersLiveDataClientFactory,
        InteractiveBrokersLiveExecClientFactory,
    )

    ib_config = {
        "host": config.ib.host,
        "port": config.ib.port,
        "client_id": config.ib.client_id,
    }
    instrument_provider = InteractiveBrokersInstrumentProviderConfig(
        load_all=False,
        load_ids=frozenset(),
    )
    return VenueClientWiring(
        data_clients={
            IB: InteractiveBrokersDataClientConfig(
                ib_gateway=ib_config,
                instrument_provider=instrument_provider,
            ),
        },
        exec_clients={
            IB: InteractiveBrokersExecClientConfig(
                ib_gateway=ib_config,
                instrument_provider=instrument_provider,
            ),
        },
        data_client_factories={IB: InteractiveBrokersLiveDataClientFactory},
        exec_client_factories={IB: InteractiveBrokersLiveExecClientFactory},
    )
