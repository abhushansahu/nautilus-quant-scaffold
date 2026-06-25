from __future__ import annotations

from datetime import UTC, datetime, time

from nautilus_trader.common.actor import Actor
from nautilus_trader.config import ActorConfig
from nautilus_trader.model.identifiers import InstrumentId

from nautilus_zerodte.actors.data_types import SESSION_PHASE_TOPIC, SessionPhaseSnapshot


class SessionActorConfig(ActorConfig, frozen=True):
    blackout_minutes_before_close: int = 30
    market_close_utc: str = "21:00"
    underlying: str = "SPY.NYSE"


def parse_close_time(market_close_utc: str) -> time:
    hour, minute = market_close_utc.split(":")
    return time(int(hour), int(minute), tzinfo=UTC)


def minutes_to_close(now: datetime, close_time: time) -> int:
    close_dt = datetime.combine(now.date(), close_time, tzinfo=UTC)
    if now >= close_dt:
        return 0
    return int((close_dt - now).total_seconds() // 60)


def session_allows_entry(
    now: datetime,
    close_time: time,
    *,
    blackout_minutes_before_close: int,
) -> bool:
    return minutes_to_close(now, close_time) > blackout_minutes_before_close


def session_phase_label(allows_entry: bool) -> str:
    return "NORMAL" if allows_entry else "BLACKOUT"


class SessionActor(Actor):
    """Publishes session phase and blackout state on the MessageBus."""

    def __init__(self, config: SessionActorConfig) -> None:
        super().__init__(config)
        self._close_time = parse_close_time(config.market_close_utc)

    def on_start(self) -> None:
        instrument_id = InstrumentId.from_str(self.config.underlying)
        self.subscribe_quote_ticks(instrument_id)

    def on_quote_tick(self, tick) -> None:  # noqa: ANN001
        self._publish_phase()

    def minutes_to_expiry(self) -> int:
        return minutes_to_close(self.clock.utc_now(), self._close_time)

    def session_phase(self) -> str:
        return session_phase_label(self.allows_entry())

    def allows_entry(self) -> bool:
        return session_allows_entry(
            self.clock.utc_now(),
            self._close_time,
            blackout_minutes_before_close=self.config.blackout_minutes_before_close,
        )

    def flatten_signal(self) -> bool:
        return not self.allows_entry()

    def _publish_phase(self) -> None:
        minutes = self.minutes_to_expiry()
        allows = self.allows_entry()
        phase = session_phase_label(allows)
        self.msgbus.publish(
            SESSION_PHASE_TOPIC,
            SessionPhaseSnapshot(
                allows_entry=allows,
                session_phase=phase,
                minutes_to_expiry=minutes,
                flatten_signal=not allows,
            ),
        )
