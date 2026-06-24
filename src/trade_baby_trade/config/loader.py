from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from trade_baby_trade.config.schema import AppConfig
from trade_baby_trade.models.enums import VenueAdapter


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


def _session_overlay_name(merged: dict[str, Any]) -> str:
    if overlay := merged.get("session_overlay"):
        return str(overlay)
    adapter = merged.get("venue", {}).get("adapter", VenueAdapter.IB.value)
    if str(adapter).upper() == VenueAdapter.DERIBIT.value:
        return "crypto_deribit"
    return "us_equity"


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Overlay connection settings from environment."""
    data = dict(data)

    ib = dict(data.get("ib", {}))
    if host := os.environ.get("IB_HOST"):
        ib["host"] = host
    if port := os.environ.get("IB_PORT"):
        ib["port"] = int(port)
    if client_id := os.environ.get("IB_CLIENT_ID"):
        ib["client_id"] = int(client_id)
    if ib:
        data["ib"] = ib

    deribit = dict(data.get("deribit", {}))
    if testnet := os.environ.get("DERIBIT_TESTNET"):
        deribit["testnet"] = testnet.lower() in {"1", "true", "yes"}
    if deribit:
        data["deribit"] = deribit

    if dry_run := os.environ.get("DRY_RUN"):
        data["dry_run"] = dry_run.lower() in {"1", "true", "yes"}
    return data


def load_config(profile_path: Path | str) -> AppConfig:
    """Load layered YAML: base → risk → strategy → profile → session → profile."""
    profile = Path(profile_path).resolve()
    configs_root = profile.parent.parent

    pre_session_layers = [
        configs_root / "base.yaml",
        configs_root / "risk" / "default.yaml",
        configs_root / "strategies" / "reference.yaml",
        profile,
    ]

    merged: dict[str, Any] = {}
    for layer in pre_session_layers:
        if layer.exists():
            merged = _deep_merge(merged, _load_yaml(layer))

    session_overlay = _session_overlay_name(merged)
    session_path = configs_root / "session" / f"{session_overlay}.yaml"
    if session_path.exists():
        merged = _deep_merge(merged, _load_yaml(session_path))

    # Profile wins over session defaults (e.g. backtest_reference session overrides).
    if profile.exists():
        merged = _deep_merge(merged, _load_yaml(profile))

    merged.pop("session_overlay", None)
    merged = _apply_env_overrides(merged)
    return AppConfig.model_validate(merged)
