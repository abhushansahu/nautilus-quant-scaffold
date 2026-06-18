"""Parallel run orchestration across suite profiles."""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.backtester.results import RunArtifacts
from core.config import DEFAULT_CONFIG_DIR, resolve_run
from core.run_profile import RunProfile, RunSuite
from data_pipeline.loader import DataWindow


@dataclass(frozen=True)
class ProfileRunResult:
    profile_name: str
    artifacts: RunArtifacts
    data_range: dict[str, Any]


def _isolated_results_dir(base: Path, profile: RunProfile) -> Path:
    if profile.results_dir is not None:
        return profile.results_dir
    return base / profile.name


def run_profile_worker(
    profile_dict: dict[str, Any],
    data_window_dict: dict[str, Any] | None,
    config_dir: str,
    suite_name: str | None = None,
    index_results_dir: str | None = None,
) -> dict[str, Any]:
    """Worker entry point for process-pool execution (fresh NT log guard per process)."""
    from apps.backtester.runner import run_experiment

    profile = RunProfile.model_validate(profile_dict)
    app_cfg, exp = resolve_run(profile, config_dir=Path(config_dir))
    index_dir = Path(index_results_dir) if index_results_dir else app_cfg.results_dir
    app_cfg = app_cfg.model_copy(
        update={"results_dir": _isolated_results_dir(app_cfg.results_dir, profile)}
    )
    data_window = DataWindow(**data_window_dict) if data_window_dict else None
    artifacts = run_experiment(
        exp,
        app_cfg,
        data_window=data_window,
        profile_name=profile.name,
        suite_name=suite_name or profile.name,
        cache_key=profile.cache_key,
        index_dir=index_dir,
    )
    data_range = artifacts.summary.get("data_range", {})
    return {
        "profile_name": profile.name,
        "artifacts": {
            "run_id": artifacts.run_id,
            "run_dir": str(artifacts.run_dir),
            "summary": artifacts.summary,
        },
        "data_range": data_range,
    }


class RunOrchestrator:
    """Dispatch suite profiles in parallel (backtest) or sequentially (paper/live)."""

    def __init__(
        self,
        suite: RunSuite,
        config_dir: Path = DEFAULT_CONFIG_DIR,
    ) -> None:
        self.suite = suite
        self.config_dir = config_dir

    def run_all(
        self,
        data_window: DataWindow | None = None,
    ) -> list[ProfileRunResult]:
        backtest_profiles = [p for p in self.suite.profiles if p.environment == "backtest"]
        other_profiles = [p for p in self.suite.profiles if p.environment != "backtest"]

        from core.config import load_config

        base_results = load_config("backtest", config_dir=self.config_dir).results_dir
        index_dir = str(base_results)
        suite_name = self.suite.name

        results: list[ProfileRunResult] = []
        if backtest_profiles:
            results.extend(
                self._run_backtest_pool(backtest_profiles, data_window, index_dir, suite_name)
            )
        for profile in other_profiles:
            results.append(self._run_blocking(profile, data_window, index_dir, suite_name))
        return results

    def _run_backtest_pool(
        self,
        profiles: list[RunProfile],
        data_window: DataWindow | None,
        index_dir: str,
        suite_name: str,
    ) -> list[ProfileRunResult]:
        window_dict = data_window.__dict__ if data_window else None
        config_dir = str(self.config_dir)
        payload = [
            (p.model_dump(mode="json"), window_dict, config_dir, suite_name, index_dir)
            for p in profiles
        ]

        if self.suite.parallelism <= 1 or len(profiles) == 1:
            raw = [run_profile_worker(*args) for args in payload]
        else:
            try:
                with concurrent.futures.ProcessPoolExecutor(
                    max_workers=self.suite.parallelism,
                ) as pool:
                    futures = [pool.submit(run_profile_worker, *args) for args in payload]
                    raw = [f.result() for f in futures]
            except (PermissionError, NotImplementedError):
                raw = [run_profile_worker(*args) for args in payload]

        return [self._deserialize_result(item) for item in raw]

    def _run_blocking(
        self,
        profile: RunProfile,
        data_window: DataWindow | None,
        index_dir: str,
        suite_name: str,
    ) -> ProfileRunResult:
        window_dict = data_window.__dict__ if data_window else None
        raw = run_profile_worker(
            profile.model_dump(mode="json"),
            window_dict,
            str(self.config_dir),
            suite_name,
            index_dir,
        )
        return self._deserialize_result(raw)

    @staticmethod
    def _deserialize_result(raw: dict[str, Any]) -> ProfileRunResult:
        artifacts_data = raw["artifacts"]
        artifacts = RunArtifacts(
            run_id=artifacts_data["run_id"],
            run_dir=Path(artifacts_data["run_dir"]),
            summary=artifacts_data["summary"],
        )
        return ProfileRunResult(
            profile_name=raw["profile_name"],
            artifacts=artifacts,
            data_range=raw.get("data_range", {}),
        )
