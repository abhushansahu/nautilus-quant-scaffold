from __future__ import annotations

from dataclasses import dataclass, field

from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode

from trade_baby_trade.config.schema import AppConfig
from trade_baby_trade.models.enums import VenueAdapter


@dataclass(frozen=True, slots=True)
class VenueClientWiring:
    data_clients: dict = field(default_factory=dict)
    exec_clients: dict = field(default_factory=dict)
    data_client_factories: dict[str, type] = field(default_factory=dict)
    exec_client_factories: dict[str, type] = field(default_factory=dict)


def resolve_venue_adapter(config: AppConfig) -> VenueAdapter:
    """Return the configured venue adapter; fail closed on unknown values."""
    adapter = config.venue.adapter
    if isinstance(adapter, VenueAdapter):
        return adapter
    try:
        return VenueAdapter(str(adapter).upper())
    except ValueError as exc:
        msg = f"Unknown venue adapter: {adapter!r} (expected DERIBIT or IB)"
        raise ValueError(msg) from exc


def build_venue_client_wiring(config: AppConfig, *, dry_run: bool) -> VenueClientWiring:
    """Build NT data/exec client wiring for the configured venue adapter."""
    adapter = resolve_venue_adapter(config)
    if adapter is VenueAdapter.DERIBIT:
        from trade_baby_trade.node.adapters.deribit import build_deribit_wiring

        return build_deribit_wiring(config, dry_run=dry_run)
    if adapter is VenueAdapter.IB:
        from trade_baby_trade.node.adapters.ib import build_ib_wiring

        return build_ib_wiring(config, dry_run=dry_run)
    msg = f"Unknown venue adapter: {adapter!r}"
    raise ValueError(msg)


def apply_venue_client_wiring(
    node_config: TradingNodeConfig,
    wiring: VenueClientWiring,
) -> TradingNodeConfig:
    """Return a TradingNodeConfig with venue data/exec clients wired."""
    if not wiring.data_clients and not wiring.exec_clients:
        return node_config
    import msgspec

    return msgspec.structs.replace(
        node_config,
        data_clients=wiring.data_clients,
        exec_clients=wiring.exec_clients,
    )


def register_venue_factories(node: TradingNode, wiring: VenueClientWiring) -> None:
    """Register live client factories on the trading node builder."""
    for name, factory in wiring.data_client_factories.items():
        node.add_data_client_factory(name, factory)
    for name, factory in wiring.exec_client_factories.items():
        node.add_exec_client_factory(name, factory)
