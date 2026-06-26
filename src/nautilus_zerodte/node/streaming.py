from __future__ import annotations

import importlib
from pathlib import Path

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
from nautilus_trader.persistence.config import StreamingConfig as NtStreamingConfig
from nautilus_trader.persistence.writer import RotationMode

from nautilus_zerodte.config.schema import StreamCaptureConfig

_ROTATION_MODES = {
    "NO_ROTATION": RotationMode.NO_ROTATION,
    "SIZE": RotationMode.SIZE,
    "INTERVAL": RotationMode.INTERVAL,
    "SCHEDULED_DATES": RotationMode.SCHEDULED_DATES,
}


def resolve_data_type(type_path: str) -> type:
    """Resolve a fully-qualified NT data class path from YAML."""
    module_path, _, class_name = type_path.partition(":")
    if not class_name:
        msg = f"Invalid include_types entry (expected module:Class): {type_path}"
        raise ValueError(msg)
    module = importlib.import_module(module_path)
    data_cls = getattr(module, class_name, None)
    if data_cls is None:
        msg = f"Data class not found: {type_path}"
        raise ValueError(msg)
    return data_cls


def resolve_include_types(include_types: list[str]) -> list[type]:
    return [resolve_data_type(path) for path in include_types]


def build_nt_streaming_config(streaming: StreamCaptureConfig) -> NtStreamingConfig:
    """Build NT StreamingConfig from operator YAML."""
    rotation = _ROTATION_MODES.get(streaming.rotation_mode.upper(), RotationMode.NO_ROTATION)
    return NtStreamingConfig(
        catalog_path=streaming.stream_path,
        include_types=resolve_include_types(streaming.include_types),
        rotation_mode=rotation,
        flush_interval_ms=streaming.flush_interval_ms,
    )


def resolve_stream_instance_id(
    stream_base: Path,
    run_id: str,
    *,
    instance_id: str | None = None,
) -> str:
    """Locate the NT kernel instance id under a captured live stream."""
    live_dir = stream_base / run_id / "live"
    if not live_dir.is_dir():
        msg = f"No live stream directory at {live_dir}"
        raise FileNotFoundError(msg)

    instances = sorted(path.name for path in live_dir.iterdir() if path.is_dir())
    if instance_id:
        if instance_id not in instances:
            msg = f"Instance {instance_id} not found under {live_dir}"
            raise FileNotFoundError(msg)
        return instance_id
    if len(instances) == 1:
        return instances[0]
    if not instances:
        msg = f"No instance directories under {live_dir}"
        raise FileNotFoundError(msg)
    msg = f"Multiple instance directories under {live_dir}; pass --instance-id"
    raise ValueError(msg)


def convert_stream_catalog(
    *,
    stream_base: Path,
    run_id: str,
    catalog_out: Path,
    include_types: list[str],
    instance_id: str | None = None,
) -> Path:
    """Convert feather stream capture to a permanent Parquet catalog."""
    stream_path = stream_base / run_id
    resolved_instance = resolve_stream_instance_id(stream_base, run_id, instance_id=instance_id)
    source = ParquetDataCatalog(str(stream_path))
    catalog_out.mkdir(parents=True, exist_ok=True)
    destination = ParquetDataCatalog(str(catalog_out))

    for data_cls in resolve_include_types(include_types):
        source.convert_stream_to_data(
            resolved_instance,
            data_cls,
            other_catalog=destination,
            subdirectory="live",
        )
    return catalog_out
