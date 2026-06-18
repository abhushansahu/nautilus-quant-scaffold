import json
from pathlib import Path

import pytest

from analysis.compare import load_run_index, rank_runs, select_best_profile
from core.run_profile import RunProfile, RunSuite


def _write_index(results_dir: Path, entries: list[dict]) -> None:
    path = results_dir / "index.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class TestCompare:
    def test_rank_runs_descending_by_metric(self):
        entries = [
            {"profile_name": "a", "metrics": {"sharpe_ratio": 0.5}},
            {"profile_name": "b", "metrics": {"sharpe_ratio": 1.2}},
            {"profile_name": "a", "metrics": {"sharpe_ratio": 0.8}},
        ]
        ranked = rank_runs(entries, "sharpe_ratio", profile_filter="a")
        assert ranked[0]["metrics"]["sharpe_ratio"] == 0.8

    def test_load_run_index(self, tmp_path):
        _write_index(
            tmp_path,
            [{"profile_name": "x", "metrics": {"sharpe_ratio": 1.0}, "run_id": "x_1"}],
        )
        loaded = load_run_index(tmp_path)
        assert len(loaded) == 1
        assert loaded[0]["run_id"] == "x_1"

    def test_select_best_profile(self, tmp_path):
        _write_index(
            tmp_path,
            [
                {
                    "profile_name": "ema_fast",
                    "metrics": {"sharpe_ratio": 1.5},
                    "run_id": "fast_1",
                },
                {
                    "profile_name": "ema_slow",
                    "metrics": {"sharpe_ratio": 0.5},
                    "run_id": "slow_1",
                },
            ],
        )
        suite = RunSuite(
            name="ema_eval",
            profiles=[
                RunProfile(
                    name="ema_fast",
                    experiment=Path("strategies/ema_cross_demo.yaml"),
                    environment="backtest",
                ),
                RunProfile(
                    name="ema_slow",
                    experiment=Path("strategies/ema_cross_slow.yaml"),
                    environment="backtest",
                ),
            ],
            bar_types=[],
            selection_metric="sharpe_ratio",
        )
        profile, entry = select_best_profile(suite, tmp_path)
        assert profile.name == "ema_fast"
        assert entry["run_id"] == "fast_1"

    def test_select_best_profile_raises_when_empty(self, tmp_path):
        suite = RunSuite(
            name="empty",
            profiles=[
                RunProfile(
                    name="a",
                    experiment=Path("strategies/ema_cross_demo.yaml"),
                    environment="backtest",
                ),
            ],
            bar_types=[],
        )
        with pytest.raises(ValueError, match="No indexed runs"):
            select_best_profile(suite, tmp_path)
