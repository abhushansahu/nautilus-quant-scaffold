"""Layered configuration: config/base.yaml deep-merged with the env-specific YAML.

Environment selection order: explicit argument > TRADE_ENV env var (via `.env`) > "backtest".
Config files reference secret env var *names* only; resolution happens in `core.secrets`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

TradeEnv = Literal["backtest", "paper", "live"]

DEFAULT_CONFIG_DIR = Path("config")


class EnvSettings(BaseSettings):
    """Process-level settings sourced from the environment / local `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    trade_env: TradeEnv = "backtest"


class LoggingSettings(BaseModel):
    level: str = "INFO"


class RiskSettings(BaseModel):
    max_notional_per_order: float = Field(gt=0)
    max_open_positions: int = Field(gt=0)
    max_drawdown_pct: float = Field(gt=0, le=1)


class VenueSettings(BaseModel):
    """A venue/broker connection. Secrets are referenced by env var name, never by value."""

    name: str
    api_key_env: str | None = None
    api_secret_env: str | None = None
    testnet_env: str | None = None


class AppConfig(BaseModel):
    environment: TradeEnv
    catalog_path: Path = Path("data/catalog")
    results_dir: Path = Path("experiments/results")
    artifacts_dir: Path = Path("artifacts")
    logging: LoggingSettings = LoggingSettings()
    risk: RiskSettings
    venues: list[VenueSettings] = []


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `overlay` onto `base` (overlay wins; dicts merge, others replace)."""
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_env(env: str | None = None) -> TradeEnv:
    resolved = env or os.environ.get("TRADE_ENV") or EnvSettings().trade_env
    if resolved not in ("backtest", "paper", "live"):
        raise ValueError(f"Unknown TRADE_ENV '{resolved}' (expected backtest|paper|live)")
    return resolved  # type: ignore[return-value]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_config(env: str | None = None, config_dir: Path = DEFAULT_CONFIG_DIR) -> AppConfig:
    """Load `base.yaml` merged with `<env>.yaml` from `config_dir`."""
    resolved = resolve_env(env)
    base = load_yaml(config_dir / "base.yaml")
    overlay = load_yaml(config_dir / f"{resolved}.yaml")
    return AppConfig.model_validate(deep_merge(base, overlay))
