# Design — trade_baby_trade

NT-first architecture for **institutional-grade 0DTE / near-expiry options trading** as a thin
extension layer on [NautilusTrader](https://nautilustrader.io/) 1.229+ (develop channel).

NautilusTrader owns the event loop, subscriptions, instruments, greeks, orders, fills, portfolio,
and backtest replay. This layer owns only what NT lacks: multi-strategy allocation, greek
*policy*, regime/session context, human approval, subscription *planning*, venue adapter wiring,
and learning attribution.

**Primary asset class:** **crypto 0DTE options** (BTC/ETH via **Deribit** first). **Interactive
Brokers** equity index 0DTE (SPX/SPY) is the secondary venue path.

**Venue priority:** Deribit → IB → (later) OKX/Bybit; Binance for perp hedge only; Derive out of
scope until NT adapter is stable.

## Implementation status

Phases 1–3 delivered a **venue-agnostic core** (gates, actors, FSM, journal, reference strategy)
on an SPY catalog scaffold. Phases 4+ pivot to Deribit-first live/backtest paths via a venue
adapter registry — see [implementation plan](../../.cursor/plans/0dte_implementation_plan_5c4f2990.plan.md).

| Layer | Status | Notes |
| --- | --- | --- |
| Gates, journal, FSM, actors | Delivered | No venue-specific logic |
| Factory / adapters | Venue registry delivered | `node/adapters/` — Deribit primary, IB secondary |
| Reference strategy spreads | `backtest_plumbing` on SPY | Phase 5: Deribit combo `OrderList` |
| Fees + attribution | Stubbed | Phase 6: `MakerTakerFeeModel` (Deribit) |

## Design goals

1. **Match institutional 0DTE practice** — continuous cadence, chain-centric data, greek-aware risk,
   defined-risk structures, cost-aware data fidelity, PnL attribution.
2. **Do not reinvent NautilusTrader** — use NT for matching, subscriptions, greeks, orders, and replay.
3. **Keep the custom layer thin** — policy, TopN selection, approval routing, venue profiles, and learning only.
4. **Live/backtest parity** — same Strategy classes and subscription model in `TradingNode` and
   `BacktestNode`, fed from the NT catalog.
5. **Venue logic in config + adapters** — gates, FSM, and journal stay venue-agnostic; spreads,
   session calendar, and fee schedules vary per venue profile.

## Design non-goals

- Rebuilding matching, order books, or the event loop
- A parallel ingestion pipeline (`Pipeline`, `IngestionService`, hourly fetch)
- Custom mirrors of NT types (`GreekBook`, `OptionsChainSnapshot`, `MarketSnapshot` for live options)
- Sub-second market making or HFT-style quoting
- Full stochastic vol engines, dealer-gamma/OI pin models, or ML calibration (deferred)
- A Derive/on-chain adapter (not in NT 1.229)
- Binance as an options venue (spot/perp hedge only, when needed)

## Architecture (NT-first)

```
TradingNode.run()
  ├── Venue adapter (Deribit | IB) — data + exec clients
  ├── SessionActor, RegimeActor, [IngestionPlannerActor]
  ├── Strategy A..N (NT Strategy subclasses)
  ├── [SelectorActor] — when N strategies compete for capital
  └── LearningModule + Journal (cross-cutting)

NT engine (do not reimplement):
  DataEngine, GreeksCalculator, RiskEngine, ExecutionEngine,
  Portfolio, OrderEmulator, OptionChainManager
```

No parallel ingestion layer. No parallel greek book. No hourly scheduler driving the live loop.

Venue-specific spread construction lives in `strategies/selectors/` (Deribit combo vs IB BAG) —
not in gates or the FSM.

## Two control loops

| Loop | Owner | Cadence | Purpose |
| --- | --- | --- | --- |
| **Live loop** | `TradingNode` event loop | Event-driven (ticks, greek updates, chain snapshots) | Signal evaluation, greek gates, entry/exit, hedging, flatten rules |
| **Research loop** (optional) | Offline ProcessPool on NT catalog | Batch (hourly/daily) | Heavy factor research, walk-forward calibration — **never on the order path** |

## NT capability mapping

Use NT directly — do not rebuild.

| Concern | NT API / type | Custom-only? |
| --- | --- | --- |
| Live loop | `TradingNode`, `Actor`, `Strategy` | No |
| Venue connectivity | NT adapter factories (Deribit, IB, …) | **Thin wiring** — `node/adapters/` registry |
| Option chain | `subscribe_option_chain()`, `on_option_chain()`, `OptionChainSlice` | No |
| Per-leg greeks | `OptionGreeks`, `subscribe_option_greeks()`, `on_option_greeks()` | No |
| Portfolio greeks | `GreeksCalculator.portfolio_greeks()` → `PortfolioGreeks` | No |
| Instruments | `OptionContract`, `OptionSpread`, `CryptoOptionSpread` | No |
| Multi-leg orders | `OrderList`, `SubmitOrderList` | No |
| Contingent orders | `order_factory.bracket()`, OCO/OTO via `OrderManager` | No |
| Emulated triggers | `OrderEmulator` | No |
| Pre-trade (basic) | `RiskEngine` — notional, rate limits, qty/price validation | No |
| Portfolio / fills | `Portfolio`, position events, `OrderFilled` | No |
| Backtest parity | `BacktestNode` + catalog | No |
| Greek *policy* | — | **Yes** — `RiskPolicy` in Strategy before submit |
| Trade intent / gates | — | **Yes** — `TradeIntent` with edge, liquidity, regime fields |
| Session / blackout | — | **Yes** — `SessionActor` (config-driven expiry calendar) |
| Regime tags | — | **Yes** — `RegimeActor` |
| TopN / diversification | — | **Yes** — `SelectorActor` + `DiversificationPolicy` |
| Subscription planning | — | **Yes** — `IngestionPlannerActor` (optional) |
| Human approval | — | **Yes** — `ActorClassifier` + `HumanApprovalHandler` |
| PnL attribution | — | **Yes** — `LearningModule` on NT fill events |
| Audit trail | — | **Yes** — `Journal` on NT events |

## Layered trade gates

Every entry passes **all** gates; default state is **no trade**.

| Gate | Source | Mechanism |
| --- | --- | --- |
| Edge | Strategy logic | `TradeIntent.edge_after_cost_bps` |
| Liquidity | Chain slice quotes | `TradeIntent.liquidity_score`, spread width, depth |
| Regime | `RegimeActor` | `TradeIntent.regime_tag` |
| Session | `SessionActor` | Blackout windows, minutes-to-expiry, event flags |
| Greek | `GreeksCalculator` + `RiskPolicy` | `portfolio_greeks()` + scenario shocks; venue-streamed leg greeks on Deribit |
| Operational | NT + config | Trading state, margin, feed health |
| Basic pre-trade | NT `RiskEngine` | Notional, rate limits, qty/price validation |

## Risk architecture (layered)

| Layer | Responsibility | Example limits |
| --- | --- | --- |
| **NT `RiskEngine`** | Hard engine checks on every order | Max notional, order rate, qty/price bounds, trading state |
| **Custom `RiskPolicy`** | Greek and desk rules in Strategy before submit | max_net_delta, max_net_gamma, max_daily_loss, max_concentration_per_strike |
| **`GreeksCalculator`** | Compute current and projected greeks + scenario shocks | `spot_shock=±0.01`, `vol_shock=0.10` |
| **Post-entry** | Continuous monitoring in Strategy handlers | Delta band breach → hedge (perp on Deribit); time stop → flatten |

NT `RiskEngine` is always on. Custom greek policy is an additional gate, not a replacement.

## Venue matrix

| Venue | NT adapter | 0DTE role | Notes |
| --- | --- | --- | --- |
| **Deribit** | Yes | **Primary** — BTC/ETH crypto options 0DTE | Venue-streamed `OptionGreeks`, combos/IV orders; WARM 30–60s |
| **Interactive Brokers** | Yes | Secondary — SPX/SPY equity 0DTE | BAG spreads, local greeks via calculator; WARM 60s+ |
| **OKX / Bybit** | Yes | Later — crypto options 0DTE | Same pattern as Deribit after primary path proven |
| **Binance** | Yes | Later — spot/perp hedging only | Not an options venue |
| **Derive** | In beta (1.229) | Not supported in v2 | Out of scope until adapter is stable |

Default operator profile: `configs/profiles/paper_btc.yaml` (Deribit). IB profile:
`configs/profiles/paper_spy.yaml` (secondary).

## Data fidelity tiers

HOT/WARM/COLD map to NT subscriptions — not custom fetch. See [ingestion-tiers.md](ingestion-tiers.md)
for defaults per venue and subscription profile.

| Tier | NT mechanism | Default use (Deribit) |
| --- | --- | --- |
| **HOT** | `subscribe_quote_ticks(underlying)`; per-leg `subscribe_option_greeks` | Underlying/perp + open legs (venue-streamed greeks) |
| **WARM** | `subscribe_option_chain(snapshot_interval_ms=30_000–60_000)` | ATM ± N strikes for signal generation |
| **COLD** | On-demand full chain; catalog backfill | Full chain / OI, pin research, offline analysis |

## Multi-strategy model

| Stage | Approach |
| --- | --- |
| **One strategy** | Single NT Strategy; full capital; no selector needed |
| **Two+ strategies, uncorrelated** | Fixed capital split in config; each Strategy owns its greek budget |
| **Two+ strategies, competing** | `SelectorActor` on MessageBus: collects `TradeIntent`s, applies `DiversificationPolicy` TopN |
| **Heavy offline research** | ProcessPool over NT catalog snapshots — parallel to live, never blocking the event loop |

## Files

| File | Diagram | Shows |
| --- | --- | --- |
| `data-model.puml` | Class (data) | Custom-only value objects and aggregates |
| `class-diagram.puml` | Class (behavior) | TradingNode, Actors, Strategies, NT engine boundary |
| `state-diagram.puml` | State | Per-strategy lifecycle + SessionActor blackout |
| `sequence-diagram.puml` | Sequence | Live flow: subscribe → gates → order → hedge |
| `concurrency-activity.puml` | Activity | NT event loop (live) + ProcessPool (offline only) |
| `ingestion-tiers.md` | Doc | HOT/WARM/COLD → NT subscription mapping |

## Concurrency model

| Domain | Model |
| --- | --- |
| **Live trading** | Single-threaded NT event loop per node; Strategies and Actors on MessageBus |
| **Offline research** | ProcessPool map-reduce over catalog — optional, separate from live |
| **Multi-strategy selection** | `SelectorActor` join barrier only when N strategies compete for shared capital |

## Render

```bash
# with the plantuml CLI
plantuml docs/design/*.puml

# or via Docker, no local install
docker run --rm -v "$PWD:/work" -w /work plantuml/plantuml docs/design/*.puml
```

Each diagram is also viewable inline in VS Code with the *PlantUML* extension (Alt+D).

## Mapping diagram → design

| Diagram element | Design element |
| --- | --- |
| `TradingNode` | Live/backtest orchestrator — `TradingNode.run()` |
| Venue adapter | `node/adapters/` — Deribit or IB data + exec clients from config |
| `SessionActor` | Blackout windows, session phase, minutes-to-expiry (daily UTC or equity close) |
| `RegimeActor` | Rule-based chop/trend/pin_risk tags |
| Strategy A/B/C/…N | NT `Strategy` subclasses — gates, entry/exit/hedge |
| Structure selector | `strategies/selectors/` — Deribit combo vs IB BAG |
| `GreeksCalculator` + `RiskPolicy` | Greek gate before submit |
| `SelectorActor` + `DiversificationPolicy` | TopN when N strategies compete |
| `ActorClassifier` + handlers | Human vs automation routing |
| `LearningModule` | PnL attribution on NT fill events |
| `Journal` | Cross-cutting audit on every gate, order, fill |
| Deribit / IB / OKX | Primary and secondary venues (see venue matrix) |
