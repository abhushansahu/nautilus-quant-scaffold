"""Integration: suite fan-out produces isolated per-profile result directories."""

import json
from pathlib import Path

import pytest

from core.config import load_config
from core.orchestrator import RunOrchestrator
from core.run_profile import load_run_suite

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"

pytestmark = pytest.mark.integration


@pytest.fixture
def suite_config(tmp_path, monkeypatch):
    base_results = tmp_path / "results"
    suite = load_run_suite(CONFIG_DIR / "suites" / "ema_eval.yaml")
    profiles = []
    for p in suite.profiles:
        profiles.append(
            p.model_copy(update={"results_dir": base_results / p.name}),
        )
    suite = suite.model_copy(update={"profiles": profiles, "parallelism": 1})
    app_cfg = load_config("backtest", config_dir=CONFIG_DIR).model_copy(
        update={
            "logging": load_config("backtest", config_dir=CONFIG_DIR)
            .logging.model_copy(update={"level": "ERROR"}),
            "results_dir": base_results,
        }
    )
    monkeypatch.setattr(
        "core.config.load_config",
        lambda env, config_dir=CONFIG_DIR: app_cfg,
    )
    return suite, base_results


def test_suite_runs_all_profiles(suite_config):
    suite, base_results = suite_config
    results = RunOrchestrator(suite, config_dir=CONFIG_DIR).run_all()
    assert len(results) == 2
    profile_dirs = {r.profile_name: r.artifacts.run_dir for r in results}
    assert profile_dirs["ema_fast"].parent == base_results / "ema_fast"
    assert profile_dirs["ema_slow"].parent == base_results / "ema_slow"
    for result in results:
        assert (result.artifacts.run_dir / "summary.json").exists()
        metrics = result.artifacts.summary["metrics"]
        assert metrics["n_fills"] > 0
        assert "sharpe_ratio" in metrics


def test_suite_writes_index(suite_config):
    suite, base_results = suite_config
    RunOrchestrator(suite, config_dir=CONFIG_DIR).run_all()
    index_path = base_results / "index.jsonl"
    assert index_path.exists()
    lines = [json.loads(line) for line in index_path.read_text().splitlines() if line.strip()]
    assert len(lines) == 2
    profiles = {entry["profile_name"] for entry in lines}
    assert profiles == {"ema_fast", "ema_slow"}
