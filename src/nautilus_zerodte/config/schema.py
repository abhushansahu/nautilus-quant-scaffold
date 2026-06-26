from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from nautilus_zerodte.models.diversification import DiversificationPolicy
from nautilus_zerodte.models.enums import SessionExpiryMode, VenueAdapter
from nautilus_zerodte.models.risk import RiskPolicy


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


class FeeScheduleConfig(BaseModel):
    """Venue fee schedule — single source for edge gate and BacktestVenueConfig FeeModel."""

    model: str = "maker_taker"
    maker_fee: float = 0.0003
    taker_fee: float = 0.0003
    entry_liquidity: str = "taker"
    commission_per_contract: float = 0.65
    contracts_per_spread: int = 2
    expected_slippage_bps: float = 0.0


class OperationalConfig(BaseModel):
    max_underlying_quote_age_secs: float = 30.0
    max_chain_snapshot_age_secs: float = 90.0
    require_chain_snapshot: bool = True


class StrategyRuntimeConfig(BaseModel):
    strategy_id: str = "skeleton-001"
    strategy_class: str = "skeleton"
    underlying: str = "SPY.NYSE"
    min_edge_after_cost_bps: float | None = None
    min_liquidity_score: float | None = None
    blocked_regimes: list[str] | None = None
    reference: ReferenceStrategyConfig | None = None


class DiversificationConfig(BaseModel):
    enabled: bool = False
    top_n: int = 3
    max_per_instrument: int = 1
    max_per_strategy: float = 0.5
    max_gross_risk_pct: float = 1.0
    batch_interval_ms: int = 100

    def to_policy(self) -> DiversificationPolicy:
        return DiversificationPolicy(
            top_n=self.top_n,
            max_per_instrument=self.max_per_instrument,
            max_per_strategy=self.max_per_strategy,
            max_gross_risk_pct=self.max_gross_risk_pct,
        )


class ApprovalConfig(BaseModel):
    human_notional_threshold: float = 10_000.0
    human_edge_bps_threshold: float = 50.0


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
    fees: FeeScheduleConfig = Field(default_factory=FeeScheduleConfig)
    operational: OperationalConfig = Field(default_factory=OperationalConfig)
    strategy: StrategyRuntimeConfig = Field(default_factory=StrategyRuntimeConfig)
    strategies: list[StrategyRuntimeConfig] | None = None
    diversification: DiversificationConfig = Field(default_factory=DiversificationConfig)
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
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

    def resolved_strategies(self) -> list[StrategyRuntimeConfig]:
        if self.strategies:
            return self.strategies
        return [self.strategy]

    def selector_enabled(self) -> bool:
        strategies = self.resolved_strategies()
        return self.diversification.enabled or len(strategies) > 1
