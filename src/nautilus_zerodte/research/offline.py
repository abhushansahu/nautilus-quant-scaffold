from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog


def list_quote_tick_partitions(catalog_path: Path | str) -> list[str]:
    """List instrument ids with quote ticks in a catalog."""
    catalog = ParquetDataCatalog(str(catalog_path))
    instrument_ids: set[str] = set()
    for instrument in catalog.instruments():
        instrument_ids.add(str(instrument.id))
    if instrument_ids:
        return sorted(instrument_ids)

    if "quote_tick" not in set(catalog.list_data_types()):
        return []
    return sorted(catalog.list_instruments(data_cls="quote_tick"))


def _quote_tick_count(args: tuple[str, str]) -> dict[str, Any]:
    catalog_path, instrument_id = args
    catalog = ParquetDataCatalog(catalog_path)
    ticks = catalog.quote_ticks(instrument_ids=[InstrumentId.from_str(instrument_id)])
    return {"instrument_id": instrument_id, "quote_tick_count": len(ticks)}


def run_catalog_partitions(
    catalog_path: Path | str,
    research_fn: Callable[[tuple[str, str]], dict[str, Any]] | None = None,
    *,
    max_workers: int | None = None,
) -> list[dict[str, Any]]:
    """Offline ProcessPool map over catalog partitions — never on the order path."""
    catalog_path = Path(catalog_path)
    partitions = list_quote_tick_partitions(catalog_path)
    if not partitions:
        return []

    worker = research_fn or _quote_tick_count
    tasks = [(str(catalog_path), instrument_id) for instrument_id in partitions]
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(worker, tasks))
