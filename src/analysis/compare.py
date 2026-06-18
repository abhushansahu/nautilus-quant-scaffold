"""Run comparison and best-profile selection from the run index."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.run_profile import RunProfile, RunSuite

INDEX_FILENAME = "index.jsonl"


def index_path(results_dir: Path) -> Path:
    return results_dir / INDEX_FILENAME


def load_run_index(results_dir: Path) -> list[dict[str, Any]]:
    path = index_path(results_dir)
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def rank_runs(
    entries: list[dict[str, Any]],
    metric: str,
    profile_filter: str | None = None,
) -> list[dict[str, Any]]:
    filtered = entries
    if profile_filter is not None:
        filtered = [e for e in entries if e.get("profile_name") == profile_filter]
    return sorted(
        filtered,
        key=lambda e: e.get("metrics", {}).get(metric, float("-inf")),
        reverse=True,
    )


def select_best_profile(suite: RunSuite, results_dir: Path) -> tuple[RunProfile, dict[str, Any]]:
    """Pick the profile with the best recent run on the suite selection metric."""
    entries = load_run_index(results_dir)
    best_entry: dict[str, Any] | None = None
    best_profile: RunProfile | None = None
    best_value = float("-inf")

    for profile in suite.profiles:
        ranked = rank_runs(entries, suite.selection_metric, profile_filter=profile.name)
        recent = ranked[: suite.lookback_runs]
        if not recent:
            continue
        profile_best = max(
            recent,
            key=lambda e: e.get("metrics", {}).get(suite.selection_metric, float("-inf")),
        )
        value = profile_best.get("metrics", {}).get(suite.selection_metric, float("-inf"))
        if value > best_value:
            best_value = value
            best_entry = profile_best
            best_profile = profile

    if best_profile is None or best_entry is None:
        raise ValueError(f"No indexed runs found for suite '{suite.name}' in {results_dir}")

    return best_profile, best_entry
