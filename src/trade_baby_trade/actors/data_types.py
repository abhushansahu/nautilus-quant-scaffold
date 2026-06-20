"""MessageBus topics and payloads for cross-cutting actor context."""

from __future__ import annotations

from dataclasses import dataclass

SESSION_PHASE_TOPIC = "data.session.phase"
REGIME_TAG_TOPIC = "data.regime.tag"


@dataclass(frozen=True, slots=True)
class SessionPhaseSnapshot:
    allows_entry: bool
    session_phase: str
    minutes_to_expiry: int
    flatten_signal: bool


@dataclass(frozen=True, slots=True)
class RegimeTagSnapshot:
    regime_tag: str
