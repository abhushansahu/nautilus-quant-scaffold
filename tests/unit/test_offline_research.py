from __future__ import annotations

from pathlib import Path

from nautilus_zerodte.research.offline import _quote_tick_count, list_quote_tick_partitions


def test_list_quote_tick_partitions_on_spy_fixture() -> None:
    catalog = Path("tests/fixtures/catalog")
    partitions = list_quote_tick_partitions(catalog)
    assert "SPY.NYSE" in partitions


def test_quote_tick_count_worker_on_spy_fixture() -> None:
    catalog = Path("tests/fixtures/catalog")
    result = _quote_tick_count((str(catalog), "SPY.NYSE"))
    assert result["instrument_id"] == "SPY.NYSE"
    assert result["quote_tick_count"] > 0
