"""Persisted active strategy selection for the switcher and live node."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

DEFAULT_STATE_PATH = Path("data/state/active_strategy.json")


class ActiveStrategyState(BaseModel):
    suite: str
    active_profile: str
    selected_at: datetime
    metric: str
    metric_value: float
    run_id: str

    @classmethod
    def load(cls, path: Path = DEFAULT_STATE_PATH) -> ActiveStrategyState | None:
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return cls.model_validate(data)

    def save(self, path: Path = DEFAULT_STATE_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, default=str),
        )

    @classmethod
    def write(
        cls,
        *,
        suite: str,
        active_profile: str,
        metric: str,
        metric_value: float,
        run_id: str,
        path: Path = DEFAULT_STATE_PATH,
    ) -> ActiveStrategyState:
        state = cls(
            suite=suite,
            active_profile=active_profile,
            selected_at=datetime.now(UTC),
            metric=metric,
            metric_value=metric_value,
            run_id=run_id,
        )
        state.save(path)
        return state
