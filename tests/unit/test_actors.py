from __future__ import annotations

from datetime import UTC, datetime

from nautilus_zerodte.actors.regime import compute_regime_tag
from nautilus_zerodte.actors.session import (
    minutes_to_close,
    parse_close_time,
    session_allows_entry,
    session_phase_label,
)
from nautilus_zerodte.models.enums import RegimeTag


def test_session_allows_entry_outside_blackout() -> None:
    close = parse_close_time("21:00")
    now = datetime(2024, 1, 2, 14, 30, 0, tzinfo=UTC)
    assert minutes_to_close(now, close) == 390
    assert session_allows_entry(now, close, blackout_minutes_before_close=30) is True
    assert session_phase_label(True) == "NORMAL"


def test_session_blocks_entry_in_blackout() -> None:
    close = parse_close_time("14:45")
    now = datetime(2024, 1, 2, 14, 30, 0, tzinfo=UTC)
    assert minutes_to_close(now, close) == 15
    assert session_allows_entry(now, close, blackout_minutes_before_close=30) is False
    assert session_phase_label(False) == "BLACKOUT"


def test_regime_trend_on_large_move() -> None:
    tag = compute_regime_tag(
        402.5,
        open_price=400.0,
        recent_prices=[400.0, 401.0, 402.0, 402.5],
        trend_move_pct=0.005,
        chop_range_pct=0.002,
        pin_strike_proximity_pct=0.0001,
    )
    assert tag == RegimeTag.TREND


def test_regime_chop_on_tight_range() -> None:
    tag = compute_regime_tag(
        400.05,
        open_price=400.0,
        recent_prices=[400.0, 400.1, 400.05, 400.08, 400.02],
        trend_move_pct=0.05,
        chop_range_pct=0.002,
        pin_strike_proximity_pct=0.0001,
    )
    assert tag == RegimeTag.CHOP


def test_regime_zero_mid_skips_chop_without_error() -> None:
    tag = compute_regime_tag(
        0.0,
        open_price=None,
        recent_prices=[0.0, 0.0, 0.0, 0.0, 0.0],
        trend_move_pct=0.005,
        chop_range_pct=0.002,
        pin_strike_proximity_pct=0.001,
    )
    assert tag == RegimeTag.UNKNOWN
