# Design — trade_baby_trade

NT-first architecture for **institutional-grade 0DTE / near-expiry options trading** as a thin
extension layer on [NautilusTrader](https://nautilustrader.io/) 1.228+.

NautilusTrader owns the event loop, subscriptions, instruments, greeks, orders, fills, portfolio,
and backtest replay. This layer owns only what NT lacks: multi-strategy allocation, greek
*policy*, regime/session context, human approval, subscription *planning*, and learning attribution.

**Primary asset class:** US equity index 0DTE (SPX/SPY via Interactive Brokers). Crypto options
(Deribit/OKX/Bybit) are a secondary venue path.

## Design goals

1. **Match institutional 0DTE practice** — continuous cadence, chain-centric data, greek-aware risk,
   defined-risk structures, cost-aware data fidelity, PnL attribution.
2. **Do not reinvent NautilusTrader** — use NT for matching, subscriptions, greeks, orders, and replay.
3. **Keep the custom layer thin** — policy, TopN selection, approval routing, and learning only.
4. **Live/backtest parity** — same Strategy classes and subscription model in `TradingNode` and
   `BacktestNode`, fed from the NT catalog.
5. **Document before build** — all `docs/design/` artifacts reflect v2 before any code is written.

## Design non-goals

- Rebuilding matching, order books, or the event loop
- A parallel ingestion pipeline (`Pipeline`, `IngestionService`, hourly fetch)
- Custom mirrors of NT types (`GreekBook`, `OptionsChainSnapshot`, `MarketSnapshot` for live options)
- Sub-second market making or HFT-style quoting
- Full stochastic vol engines, dealer-gamma/OI pin models, or ML calibration (deferred)
- A Derive/on-chain adapter (not in NT 1.228)

## Architecture (NT-first)

```
TradingNode.run()
  ├── SessionActor, RegimeActor, [IngestionPlannerActor]
  ├── Strategy A..N (NT Strategy subclasses)
  ├── [SelectorActor] — when N strategies compete for capital
  └── LearningModule + Journal (cross-cutting)

NT engine (do not reimplement):
  DataEngine, GreeksCalculator, RiskEngine, ExecutionEngine,
  Portfolio, OrderEmulator, OptionChainManager
```

No parallel ingestion layer. No parallel greek book. No hourly scheduler driving the live loop.

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
| Session / blackout | — | **Yes** — `SessionActor` |
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
| Greek | `GreeksCalculator` + `RiskPolicy` | `portfolio_greeks()` + scenario shocks |
| Operational | NT + config | Trading state, margin, feed health |
| Basic pre-trade | NT `RiskEngine` | Notional, rate limits, qty/price validation |

## Risk architecture (layered)

| Layer | Responsibility | Example limits |
| --- | --- | --- |
| **NT `RiskEngine`** | Hard engine checks on every order | Max notional, order rate, qty/price bounds, trading state |
| **Custom `RiskPolicy`** | Greek and desk rules in Strategy before submit | max_net_delta, max_net_gamma, max_daily_loss, max_concentration_per_strike |
| **`GreeksCalculator`** | Compute current and projected greeks + scenario shocks | `spot_shock=±0.01`, `vol_shock=0.10` |
| **Post-entry** | Continuous monitoring in Strategy handlers | Delta band breach → hedge; time stop → flatten |

NT `RiskEngine` is always on. Custom greek policy is an additional gate, not a replacement.

## Venue matrix

| Venue | NT adapter | 0DTE role | Notes |
| --- | --- | --- | --- |
| **Interactive Brokers** | Yes | **Primary** — SPX/SPY equity 0DTE | Chain build, BAG spreads, local greeks via calculator; no venue-streamed greeks |
| **Deribit / OKX / Bybit** | Yes | Secondary — crypto options 0DTE | Venue-streamed `OptionGreeks`, IV orders, combos |
| **Binance** | Yes | Spot/perp hedging only | Not US equity options |
| **Derive** | In beta (1.228) | Not supported in v2 | Drop until adapter is stable |

## Data fidelity tiers

HOT/WARM/COLD map to NT subscriptions — not custom fetch. See [ingestion-tiers.md](ingestion-tiers.md)
for defaults per venue and subscription profile.

| Tier | NT mechanism | Default use |
| --- | --- | --- |
| **HOT** | `subscribe_quote_ticks(underlying)`; raw chain or per-leg greeks | Underlying + open position legs |
| **WARM** | `subscribe_option_chain(snapshot_interval_ms=60_000–300_000)` | ATM ± N strikes for signal generation |
| **COLD** | IB `build_options_chain` on demand; catalog backfill | Full chain / OI, pin research, offline analysis |

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
| `SessionActor` | Blackout windows, session phase, minutes-to-expiry |
| `RegimeActor` | Rule-based chop/trend/pin_risk tags |
| Strategy A/B/C/…N | NT `Strategy` subclasses — gates, entry/exit/hedge |
| `GreeksCalculator` + `RiskPolicy` | Greek gate before submit |
| `SelectorActor` + `DiversificationPolicy` | TopN when N strategies compete |
| `ActorClassifier` + handlers | Human vs automation routing |
| `LearningModule` | PnL attribution on NT fill events |
| `Journal` | Cross-cutting audit on every gate, order, fill |
| IB / Deribit / OKX | Primary and secondary venues (see venue matrix) |
