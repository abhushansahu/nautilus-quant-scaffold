"""Layered configuration: config/base.yaml deep-merged with the env-specific YAML.

Environment selection order: explicit argument > TRADE_ENV env var (via `.env`) > "backtest".
Config files reference secret env var *names* only; resolution happens in `core.secrets`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from core.experiment import ExperimentConfig
    from core.run_profile import RunProfile

TradeEnv = Literal["backtest", "paper", "live"]

SECRET_FIELD_NAMES = frozenset({"api_key", "api_secret", "password", "token"})

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

    @model_validator(mode="before")
    @classmethod
    def reject_literal_secrets(cls, data: object) -> object:
        if isinstance(data, dict):
            found = SECRET_FIELD_NAMES & data.keys()
            if found:
                names = ", ".join(sorted(found))
                raise ValueError(
                    f"Literal secret fields not allowed in config: {names}. "
                    "Use *_env name fields instead."
                )
        return data


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


def _resolve_experiment_path(experiment: Path, config_dir: Path) -> Path:
    if experiment.is_absolute():
        return experiment
    return config_dir / experiment


def resolve_run(
    profile: RunProfile,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> tuple[AppConfig, ExperimentConfig]:
    """Load app + experiment config for a run profile, applying per-profile overrides."""
    from core.experiment import load_experiment

    app_cfg = load_config(profile.environment, config_dir=config_dir)
    exp = load_experiment(_resolve_experiment_path(profile.experiment, config_dir))

    overrides: dict[str, Path] = {}
    if profile.catalog_path is not None:
        overrides["catalog_path"] = profile.catalog_path
    if profile.results_dir is not None:
        overrides["results_dir"] = profile.results_dir
    if overrides:
        app_cfg = app_cfg.model_copy(update=overrides)
    return app_cfg, exp


def profile_from_cli(
    experiment: Path,
    env: str | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> RunProfile:
    """Build a synthetic run profile from legacy `--config` / `--env` CLI flags."""
    from core.run_profile import RunProfile

    exp_path = _resolve_experiment_path(experiment, config_dir)
    return RunProfile(
        name=exp_path.stem,
        experiment=exp_path,
        environment=resolve_env(env),
    )
