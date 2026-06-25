from __future__ import annotations

from nautilus_trader.adapters.deribit import DERIBIT

from nautilus_zerodte.config.schema import AppConfig
from nautilus_zerodte.models.enums import VenueAdapter
from nautilus_zerodte.node.adapters.registry import build_venue_client_wiring, resolve_venue_adapter


def test_resolve_venue_adapter_deribit() -> None:
    config = AppConfig(venue={"adapter": "DERIBIT"})
    assert resolve_venue_adapter(config) is VenueAdapter.DERIBIT


def test_resolve_venue_adapter_ib() -> None:
    config = AppConfig(venue={"adapter": "IB"})
    assert resolve_venue_adapter(config) is VenueAdapter.IB


def test_build_deribit_wiring_on_dry_run() -> None:
    config = AppConfig(
        venue={"adapter": "DERIBIT", "name": "DERIBIT"},
        deribit={"testnet": True},
    )
    wiring = build_venue_client_wiring(config, dry_run=True)

    assert DERIBIT in wiring.data_clients
    assert DERIBIT in wiring.exec_clients
    assert DERIBIT in wiring.data_client_factories
    assert DERIBIT in wiring.exec_client_factories


def test_build_ib_wiring_skipped_on_dry_run() -> None:
    config = AppConfig(venue={"adapter": "IB"})
    wiring = build_venue_client_wiring(config, dry_run=True)

    assert not wiring.data_clients
    assert not wiring.exec_clients
