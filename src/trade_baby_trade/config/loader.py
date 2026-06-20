from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from trade_baby_trade.config.schema import AppConfig


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Overlay IB connection settings from environment."""
    ib = dict(data.get("ib", {}))
    if host := os.environ.get("IB_HOST"):
        ib["host"] = host
    if port := os.environ.get("IB_PORT"):
        ib["port"] = int(port)
    if client_id := os.environ.get("IB_CLIENT_ID"):
        ib["client_id"] = int(client_id)
    if ib:
        data = dict(data)
        data["ib"] = ib
    if dry_run := os.environ.get("DRY_RUN"):
        data = dict(data)
        data["dry_run"] = dry_run.lower() in {"1", "true", "yes"}
    return data


def load_config(profile_path: Path | str) -> AppConfig:
    """Load layered YAML: base → risk → session → strategy → profile."""
    profile = Path(profile_path).resolve()
    configs_root = profile.parent.parent

    layers = [
        configs_root / "base.yaml",
        configs_root / "risk" / "default.yaml",
        configs_root / "session" / "us_equity.yaml",
        configs_root / "strategies" / "reference.yaml",
        profile,
    ]

    merged: dict[str, Any] = {}
    for layer in layers:
        if layer.exists():
            merged = _deep_merge(merged, _load_yaml(layer))

    merged = _apply_env_overrides(merged)
    return AppConfig.model_validate(merged)
