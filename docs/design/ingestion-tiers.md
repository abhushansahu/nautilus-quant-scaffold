# Ingestion tiers — HOT / WARM / COLD

Data fidelity tiers map to **NautilusTrader subscriptions**, not a custom fetch pipeline.
There is no `IngestionService`, hourly scheduler, or `MarketSnapshot` aggregate for live options.

Optional `IngestionPlannerActor` constrains *what* to subscribe to (API budget) — not *how* NT fetches.

## Tier overview

| Tier | NT mechanism | Fidelity | Cost | Default use |
| --- | --- | --- | --- | --- |
| **HOT** | `subscribe_quote_ticks`, raw `subscribe_option_chain`, per-leg `subscribe_option_greeks` | Tick-level | Highest | Underlying/perp + open position legs |
| **WARM** | `subscribe_option_chain(snapshot_interval_ms=30_000–300_000)` | Snapshot (30s–5 min) | Medium | ATM ± N strikes for signal generation |
| **COLD** | On-demand full chain; catalog backfill | On-demand / historical | Lowest | Full chain / OI, pin research, offline analysis |

## Default subscription profile (crypto 0DTE — Deribit)

| Concern | NT subscription | Tier | Rationale |
| --- | --- | --- | --- |
| Underlying | `subscribe_quote_ticks(underlying)` or perp | HOT | Delta band / hedge triggers |
| Chain (signals) | `subscribe_option_chain`, `snapshot_interval_ms=30_000–60_000` | WARM | Vol/skew; Deribit supports shorter snapshots |
| Full chain | On-demand instrument load / catalog backfill | COLD | Pin research, not every evaluation |
| Open positions | `subscribe_option_greeks` per leg | HOT | **Venue-streamed greeks** — prefer over calculator-only |
| Hedge check | `on_quote_tick` on underlying/perp | HOT | Gamma management |
| New entries | Blocked by `SessionActor` T-30m to expiry | — | Daily UTC expiry risk (configurable) |

Config overlay: `configs/session/crypto_deribit.yaml`. Operator profile: `configs/profiles/paper_btc.yaml`.

## Secondary subscription profile (equity 0DTE — IB)

| Concern | NT subscription | Tier | Rationale |
| --- | --- | --- | --- |
| Underlying | `subscribe_quote_ticks(underlying)` | HOT | Delta band / hedge triggers |
| Chain (signals) | `subscribe_option_chain`, `snapshot_interval_ms=60_000` | WARM | Vol/skew without full-chain tick rate |
| Full chain | On-demand `build_options_chain` | COLD | Pin research, not every evaluation |
| Open positions | `subscribe_option_greeks` per leg | HOT | Local greeks via `GreeksCalculator` |
| Hedge check | `on_quote_tick` on underlying | HOT | Gamma management |
| New entries | Blocked by `SessionActor` T-30m to US close | — | Pin / assignment risk |

Config overlay: `configs/session/us_equity.yaml`. Operator profile: `configs/profiles/paper_spy.yaml`.

## Venue-specific notes

### Deribit (primary — BTC/ETH crypto 0DTE)

- Default production venue; NT Deribit adapter for data + execution.
- Venue-streamed `OptionGreeks` via `subscribe_option_greeks` — prefer HOT for open legs.
- Combos and IV orders supported natively; spreads as `CryptoOptionSpread` / combo `InstrumentId`.
- WARM snapshot interval **30–60s** (shorter than IB due to richer streaming).
- Hedge via Deribit perpetual (`BTC-PERPETUAL`, etc.) on delta band breach.
- COLD: catalog backfill for offline research; on-demand full chain when needed.

### Interactive Brokers (secondary — SPX/SPY equity 0DTE)

- Chain build via IB instrument provider; spreads as BAG `InstrumentId`.
- Greeks computed locally via `GreeksCalculator` (no venue-streamed greeks).
- WARM tier recommended for signal chain — full tick-level chain is expensive on IB API.
- COLD: `build_options_chain` at session open; refresh on demand for pin/OI research.

### OKX / Bybit (later — crypto options)

- Same subscription pattern as Deribit after primary path is proven.
- Venue-streamed greeks, combos; adapter registry pattern from Phase 4.

### Binance (later — hedge only)

- Spot/perp hedging only — not a crypto options venue.
- Use `subscribe_quote_ticks` on hedge instrument (HOT) when underlying hedge is on Binance.

## Cost vs fidelity tradeoffs

| Scenario | Recommended tier | Why |
| --- | --- | --- |
| Signal generation (ATM ± 5 strikes) | WARM (30–60s Deribit; 60s IB) | Enough for vol/skew; avoids tick-rate API cost |
| Open position risk monitoring | HOT (per-leg greeks + underlying ticks) | Greek gates need timely updates |
| Entry evaluation | WARM chain + HOT underlying | Chain for structure selection; underlying for delta context |
| End-of-day / pre-expiry pin research | COLD (on-demand full chain) | OI and far strikes not needed every minute |
| Backtest replay | Catalog (COLD equivalent) | Same Strategy code; data from NT catalog |

## Trading fees (backtest alignment)

Fee schedules are venue-specific and must align pre-trade edge estimates with backtest `FeeModel`:

| Venue | Backtest model | Config |
| --- | --- | --- |
| Deribit | `MakerTakerFeeModel` | `configs/fees/deribit_options.yaml` |
| IB | `FixedFeeModel` (per-contract) | `configs/fees/ib_options.yaml` |

Live path uses venue-reported `OrderFilled.commission` — no `FeeModel` on `TradingNode`.

## IngestionPlannerActor (optional)

Introduce when subscription API cost becomes measurable (any venue). The actor:

1. Reads `IngestionBudget` (max subscriptions, max snapshot frequency).
2. Emits a subscription plan: which series, strike ranges, and tiers.
3. Publishes plan to Strategies via MessageBus — Strategies call NT subscribe methods accordingly.

Does **not** implement fetch logic — only plans what NT `DataEngine` should subscribe to.

## What not to build

- `IngestionScheduler` with 1h interval driving live trading
- `IngestionService.collect()` returning `IngestedDataset`
- Custom `OptionsChainSnapshot` or `MarketSnapshot` mirroring NT cache
- Batch OHLCV pull as the primary data path for 0DTE
