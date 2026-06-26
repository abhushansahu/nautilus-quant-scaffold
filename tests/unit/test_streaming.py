from __future__ import annotations

from nautilus_zerodte.config.schema import StreamCaptureConfig
from nautilus_zerodte.node.streaming import build_nt_streaming_config, resolve_data_type


def test_resolve_quote_tick_type() -> None:
    data_cls = resolve_data_type("nautilus_trader.model.data:QuoteTick")
    assert data_cls.__name__ == "QuoteTick"


def test_build_nt_streaming_config_from_yaml_defaults() -> None:
    capture = StreamCaptureConfig(enabled=True, stream_path="data/streaming/test")
    nt_config = build_nt_streaming_config(capture)
    assert nt_config.catalog_path == "data/streaming/test"
    assert len(nt_config.include_types) == 2


def test_stream_capture_disabled_by_default() -> None:
    capture = StreamCaptureConfig()
    assert capture.enabled is False
