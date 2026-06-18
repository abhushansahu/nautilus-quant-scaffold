from pathlib import Path
from unittest.mock import patch

from core.orchestrator import RunOrchestrator
from core.run_profile import RunProfile, RunSuite

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _fake_worker(
    profile_dict: dict,
    data_window_dict: dict | None,
    config_dir: str,
    suite_name: str | None = None,
    index_results_dir: str | None = None,
) -> dict:
    profile = RunProfile.model_validate(profile_dict)
    return {
        "profile_name": profile.name,
        "artifacts": {
            "run_id": f"{profile.name}_test",
            "run_dir": f"/tmp/{profile.name}",
            "summary": {"metrics": {"pnl": 1.0, "sharpe_ratio": 0.5}},
        },
        "data_range": {},
    }


class TestRunOrchestrator:
    def test_dispatches_all_profiles(self):
        suite = RunSuite(
            name="test_suite",
            profiles=[
                RunProfile(
                    name="a",
                    experiment=Path("strategies/ema_cross_demo.yaml"),
                    environment="backtest",
                ),
                RunProfile(
                    name="b",
                    experiment=Path("strategies/ema_cross_slow.yaml"),
                    environment="backtest",
                ),
            ],
            parallelism=1,
            bar_types=[],
        )
        with patch("core.orchestrator.run_profile_worker", side_effect=_fake_worker):
            results = RunOrchestrator(suite, config_dir=CONFIG_DIR).run_all()
        assert {r.profile_name for r in results} == {"a", "b"}

    def test_parallelism_uses_pool_for_multiple_profiles(self):
        suite = RunSuite(
            name="test_suite",
            profiles=[
                RunProfile(
                    name="a",
                    experiment=Path("strategies/ema_cross_demo.yaml"),
                    environment="backtest",
                ),
                RunProfile(
                    name="b",
                    experiment=Path("strategies/ema_cross_slow.yaml"),
                    environment="backtest",
                ),
            ],
            parallelism=2,
            bar_types=[],
        )
        with patch("core.orchestrator.concurrent.futures.ProcessPoolExecutor") as pool_cls:
            pool = pool_cls.return_value.__enter__.return_value
            pool.submit.side_effect = lambda fn, *args: type(
                "F",
                (),
                {"result": lambda self: _fake_worker(*args)},
            )()
            results = RunOrchestrator(suite, config_dir=CONFIG_DIR).run_all()
        assert pool_cls.called
        assert len(results) == 2
