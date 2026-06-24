from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from trade_baby_trade.models.enums import SessionExpiryMode, VenueAdapter
from trade_baby_trade.models.risk import RiskPolicy


class JournalConfig(BaseModel):
    path: str = "runs/latest.jsonl"


class VenueConfig(BaseModel):
    name: str = "NYSE"
    adapter: VenueAdapter = VenueAdapter.IB
    base_currency: str = "USD"
    account_type: str = "MARGIN"


class DeribitConfig(BaseModel):
    api_key_env: str = "DERIBIT_API_KEY"
    api_secret_env: str = "DERIBIT_API_SECRET"
    testnet: bool = False


class SessionConfig(BaseModel):
    blackout_minutes_before_close: int = 30
    market_close_utc: str = "21:00"
    expiry_mode: SessionExpiryMode = SessionExpiryMode.US_EQUITY_CLOSE


class RegimeConfig(BaseModel):
    trend_move_pct: float = 0.005
    chop_range_pct: float = 0.002
    pin_strike_proximity_pct: float = 0.001
    blocked_regimes: list[str] = Field(default_factory=lambda: ["PIN_RISK"])


class GateThresholdsConfig(BaseModel):
    min_edge_after_cost_bps: float = 5.0
    min_liquidity_score: float = 0.5


class OperationalConfig(BaseModel):
    max_underlying_quote_age_secs: float = 30.0
    max_chain_snapshot_age_secs: float = 90.0
    require_chain_snapshot: bool = True


class StrategyRuntimeConfig(BaseModel):
    strategy_id: str = "skeleton-001"
    strategy_class: str = "skeleton"
    underlying: str = "SPY.NYSE"


class SubscriptionConfig(BaseModel):
    chain_snapshot_interval_ms: int = 60_000


class InteractiveBrokersConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1


class ReferenceStrategyConfig(BaseModel):
    backtest_plumbing: bool = False
    structure_selector: str = "auto"
    option_series_id: str | None = None
    option_series_expiry: str | None = None
    option_series_expiry_time_utc: str = "08:00"
    settlement_currency: str = "BTC"
    strike_width: int = 5
    order_qty: float = 1.0
    take_profit_pct: float = 0.25
    stop_loss_pct: float = 0.50
    hedge_perp_instrument: str | None = None
    hedge_delta_band: float = 0.30


class AppConfig(BaseModel):
    """Merged runtime configuration for backtest and live nodes."""

    trader_id: str = "TRADER-001"
    dry_run: bool = False
    venue: VenueConfig = Field(default_factory=VenueConfig)
    journal: JournalConfig = Field(default_factory=JournalConfig)
    risk: RiskPolicy = Field(default_factory=RiskPolicy)
    session: SessionConfig = Field(default_factory=SessionConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    gates: GateThresholdsConfig = Field(default_factory=GateThresholdsConfig)
    operational: OperationalConfig = Field(default_factory=OperationalConfig)
    strategy: StrategyRuntimeConfig = Field(default_factory=StrategyRuntimeConfig)
    reference: ReferenceStrategyConfig = Field(default_factory=ReferenceStrategyConfig)
    subscriptions: SubscriptionConfig = Field(default_factory=SubscriptionConfig)
    ib: InteractiveBrokersConfig = Field(default_factory=InteractiveBrokersConfig)
    deribit: DeribitConfig = Field(default_factory=DeribitConfig)

    def resolved_journal_path(self, runs_dir: Path | None = None) -> Path:
        path = Path(self.journal.path)
        if path.is_absolute():
            return path
        base = runs_dir or Path("runs")
        relative = path
        if path.parts and path.parts[0] == "runs":
            relative = Path(*path.parts[1:]) if len(path.parts) > 1 else Path("latest.jsonl")
        return base / relative
