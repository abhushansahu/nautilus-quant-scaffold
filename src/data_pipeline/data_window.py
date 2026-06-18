"""Shared data window types for bar loading."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class DataWindow:
    """Optional override for bar loading window (orchestrator / watcher)."""

    mode: Literal["full", "incremental", "rolling"] = "full"
    start: datetime | None = None
    end: datetime | None = None
    watermark: datetime | None = None
    lookback_bars: int = 500
