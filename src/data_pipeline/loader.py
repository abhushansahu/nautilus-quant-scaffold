"""Bar data loading with in-process LRU and optional disk cache."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.instruments import Instrument

from core.config import AppConfig
from core.experiment import ExperimentConfig
from data_pipeline.bar_cache import BarCache
from data_pipeline.bar_cache import cache_key as make_cache_key
from data_pipeline.bar_sources import CatalogBarSource, SyntheticBarSource
from data_pipeline.catalog import MarketDataCatalog
from data_pipeline.data_window import DataWindow
from data_pipeline.instrument_resolver import resolve_instrument

DEFAULT_CACHE_DIR = Path("data/cache")

# Re-export for backward compatibility.
__all__ = ["BarDataLoader", "DataWindow", "default_loader", "resolve_instrument"]


class BarDataLoader:
    """Load bars for experiments with memory and optional disk caching."""

    def __init__(
        self,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        use_disk_cache: bool = True,
        catalog_source: CatalogBarSource | None = None,
        synthetic_source: SyntheticBarSource | None = None,
    ) -> None:
        self._cache = BarCache(cache_dir=cache_dir, use_disk_cache=use_disk_cache)
        self._catalog_source = catalog_source or CatalogBarSource()
        self._synthetic_source = synthetic_source or SyntheticBarSource()

    def resolve_instrument(self, exp: ExperimentConfig, app_cfg: AppConfig) -> Instrument:
        return resolve_instrument(exp, app_cfg)

    def load_bars(
        self,
        exp: ExperimentConfig,
        app_cfg: AppConfig,
        instrument: Instrument,
        data_window: DataWindow | None = None,
        cache_key: str | None = None,
    ) -> list[Bar]:
        bar_type = BarType.from_str(exp.strategy.bar_type)
        data = exp.data

        if data.source == "synthetic":
            return self._synthetic_source.generate_bars(bar_type, instrument, data)

        catalog = MarketDataCatalog(app_cfg.catalog_path)
        from data_pipeline.bar_sources import resolve_window

        start, end, _ = resolve_window(data, data_window, catalog, bar_type)
        key = make_cache_key(
            app_cfg.catalog_path,
            str(bar_type),
            start,
            end,
            data.source,
            data.seed,
            data.num_bars,
            cache_key,
        )

        cached = self._cache.get_memory(key)
        if cached is not None:
            return cached

        disk_bars = self._cache.get_disk(key, bar_type, instrument)
        if disk_bars is not None:
            self._cache.put(key, disk_bars)
            return disk_bars

        bars = self._catalog_source.read_bars(catalog, bar_type, data, data_window)
        self._cache.put(key, bars)
        return bars


@lru_cache(maxsize=1)
def default_loader() -> BarDataLoader:
    return BarDataLoader()
