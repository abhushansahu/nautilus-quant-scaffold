from pathlib import Path

import pytest
from pydantic import ValidationError

from core.config import VenueSettings, load_config, profile_from_cli, resolve_run
from core.run_profile import RunProfile, load_run_suite

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class TestRunSuite:
    def test_loads_ema_eval_suite(self):
        suite = load_run_suite(CONFIG_DIR / "suites" / "ema_eval.yaml")
        assert suite.name == "ema_eval"
        assert len(suite.profiles) == 2
        assert suite.parallelism == 2
        assert suite.selection_metric == "sharpe_ratio"

    def test_profiles_have_names_and_experiments(self):
        suite = load_run_suite(CONFIG_DIR / "suites" / "ema_eval.yaml")
        names = {p.name for p in suite.profiles}
        assert names == {"ema_fast", "ema_slow"}


class TestResolveRun:
    def test_resolves_profile_experiment_and_environment(self):
        suite = load_run_suite(CONFIG_DIR / "suites" / "ema_eval.yaml")
        profile = suite.profiles[0]
        app_cfg, exp = resolve_run(profile, config_dir=CONFIG_DIR)
        assert app_cfg.environment == "backtest"
        assert exp.name == "ema_cross_demo"

    def test_applies_path_overrides(self, tmp_path):
        profile = RunProfile(
            name="custom",
            experiment=Path("strategies/ema_cross_demo.yaml"),
            environment="backtest",
            catalog_path=tmp_path / "cat",
            results_dir=tmp_path / "res",
        )
        app_cfg, _ = resolve_run(profile, config_dir=CONFIG_DIR)
        assert app_cfg.catalog_path == tmp_path / "cat"
        assert app_cfg.results_dir == tmp_path / "res"

    def test_profile_from_cli_matches_legacy_flags(self):
        profile = profile_from_cli(
            CONFIG_DIR / "strategies" / "ema_cross_demo.yaml",
            env="backtest",
        )
        assert profile.name == "ema_cross_demo"
        assert profile.environment == "backtest"

    def test_profile_from_cli_resolves_via_resolve_run(self):
        profile = profile_from_cli(
            Path("config/strategies/ema_cross_demo.yaml"),
            env="backtest",
        )
        _, exp = resolve_run(profile, config_dir=CONFIG_DIR)
        assert exp.name == "ema_cross_demo"


class TestSecretGuardrails:
    def test_literal_api_key_rejected(self):
        with pytest.raises(ValidationError, match="Literal secret fields"):
            VenueSettings(name="BINANCE", api_key="sk-live-abcdef")

    def test_env_name_fields_allowed(self):
        venue = VenueSettings(
            name="BINANCE",
            api_key_env="BINANCE_API_KEY",
            api_secret_env="BINANCE_API_SECRET",
        )
        assert venue.api_key_env == "BINANCE_API_KEY"

    def test_live_config_still_loads(self):
        cfg = load_config("live", config_dir=CONFIG_DIR)
        assert any(v.name == "BINANCE" for v in cfg.venues)
