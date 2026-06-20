# Ingestion tiers — HOT / WARM / COLD

Data fidelity tiers map to **NautilusTrader subscriptions**, not a custom fetch pipeline.
There is no `IngestionService`, hourly scheduler, or `MarketSnapshot` aggregate for live options.

Optional `IngestionPlannerActor` constrains *what* to subscribe to (API budget) — not *how* NT fetches.

## Tier overview

| Tier | NT mechanism | Fidelity | Cost | Default use |
| --- | --- | --- | --- | --- |
| **HOT** | `subscribe_quote_ticks`, raw `subscribe_option_chain`, per-leg `subscribe_option_greeks` | Tick-level | Highest | Underlying + open position legs |
| **WARM** | `subscribe_option_chain(snapshot_interval_ms=60_000–300_000)` | Snapshot (1–5 min) | Medium | ATM ± N strikes for signal generation |
| **COLD** | IB `build_options_chain` on demand; catalog backfill | On-demand / historical | Lowest | Full chain, OI, pin research, offline analysis |

## Default subscription profile (0DTE equity)

| Concern | NT subscription | Tier | Rationale |
| --- | --- | --- | --- |
| Underlying | `subscribe_quote_ticks(underlying)` | HOT | Delta band / hedge triggers |
| Chain (signals) | `subscribe_option_chain`, `snapshot_interval_ms=60_000` | WARM | Vol/skew without full-chain tick rate |
| Full chain | On-demand `build_options_chain` | COLD | Pin research, not every evaluation |
| Open positions | `subscribe_option_greeks` per leg | HOT | Risk gate on every greek update |
| Hedge check | `on_quote_tick` on underlying | HOT | Gamma management |
| New entries | Blocked by `SessionActor` T-30m to close | — | Pin / assignment risk |

## Venue-specific notes

### Interactive Brokers (primary — SPX/SPY 0DTE)

- Chain build via IB instrument provider; spreads as BAG `InstrumentId`.
- Greeks computed locally via `GreeksCalculator` (no venue-streamed greeks).
- WARM tier recommended for signal chain — full tick-level chain is expensive on IB API.
- COLD: load full chain at session open; refresh on demand for pin/OI research.

### Deribit / OKX / Bybit (secondary — crypto options)

- Venue-streamed `OptionGreeks` via `subscribe_option_greeks` — prefer HOT for open legs.
- Combos and IV orders supported natively.
- WARM snapshot interval can be shorter (30–60s) due to richer streaming infrastructure.

### Binance

- Spot/perp hedging only — not US equity options.
- Use `subscribe_quote_ticks` on hedge instrument (HOT).

## Cost vs fidelity tradeoffs

| Scenario | Recommended tier | Why |
| --- | --- | --- |
| Signal generation (ATM ± 5 strikes) | WARM (60s snapshots) | Enough for vol/skew; avoids tick-rate API cost |
| Open position risk monitoring | HOT (per-leg greeks + underlying ticks) | Greek gates need timely updates |
| Entry evaluation | WARM chain + HOT underlying | Chain for structure selection; underlying for delta context |
| End-of-day pin research | COLD (on-demand full chain) | OI and far strikes not needed every minute |
| Backtest replay | Catalog (COLD equivalent) | Same Strategy code; data from NT catalog |

## IngestionPlannerActor (optional)

Introduce when IB API cost becomes measurable. The actor:

1. Reads `IngestionBudget` (max subscriptions, max snapshot frequency).
2. Emits a subscription plan: which series, strike ranges, and tiers.
3. Publishes plan to Strategies via MessageBus — Strategies call NT subscribe methods accordingly.

Does **not** implement fetch logic — only plans what NT `DataEngine` should subscribe to.

## What not to build

- `IngestionScheduler` with 1h interval driving live trading
- `IngestionService.collect()` returning `IngestedDataset`
- Custom `OptionsChainSnapshot` or `MarketSnapshot` mirroring NT cache
- Batch OHLCV pull as the primary data path for 0DTE
