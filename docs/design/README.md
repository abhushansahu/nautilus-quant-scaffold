# Design — trade_baby_trade

Class / state / sequence design derived from `trade_baby_trade.drawio.png`.

The system is an **hourly quant-trading pipeline** built as a thin extension layer over
[NautilusTrader](https://nautilustrader.io/). The engine owns matching, order books, and the
event loop; this layer owns ingestion scheduling, multi-strategy analysis, TopN selection, and
the risk/actor-gated action path. The same workflow runs for **spot, options, and futures**.

## Pipeline (from the diagram)

```
Brokers (IB / Binance / Derive)  ┐
Sentiment + On-chain             ┘─▶ Ingestion (1h) ─▶ Analysis (Strategy A..N)
   ─▶ ResultSet (pick TopN by diversification)
   ─▶ Action (Risk + Portfolio gate · Human/Automation actor)
   ─▶ Learning ─┐  (feeds back into Analysis)
                └─▶ ...
Journaling = logging, cross-cutting on every stage.
```

## Files

| File | Diagram | Shows |
| --- | --- | --- |
| `data-model.puml` | Class (data) | Lower-level entities passed between stages |
| `class-diagram.puml` | Class (behavior) | Services/strategies and how they bind to NautilusTrader |
| `state-diagram.puml` | State | One hourly cycle + order lifecycle |
| `sequence-diagram.puml` | Sequence | End-to-end message flow for one cycle |
| `concurrency-activity.puml` | Activity (fork/join) | Strategy fan-out → incremental reduce → join barrier |

## Concurrency model (Analysis stage)

Strategies A..N are **independent and CPU-bound**, so the Analysis stage is a
**scatter → reduce → join-barrier** (map-reduce):

1. **Scatter** — `AnalysisEngine` submits each `Strategy.evaluate(dataset)` to a
   `StrategyExecutor`. The default is a `ProcessPoolExecutor` (one OS process per worker)
   to **bypass the GIL** for numeric work; the read-only `IngestedDataset` is shared, not
   re-pickled per task. (I/O-bound strategies can use a thread pool instead.)
2. **Incremental reduce** — `ResultSelector.offer()` folds each strategy's signals into a
   bounded heap **via `as_completed`, while other strategies are still running** — this is
   the "ResultSet does work meanwhile" overlap.
3. **Join barrier** — `wait(ALL_COMPLETED, timeout)`. Laggards past the timeout are
   cancelled + journaled (degraded mode). The barrier is *required*: TopN-with-diversification
   is a **global** constraint, so `finalize()` can't pick the top-N until every candidate is in.
   A final **deterministic sort** keeps results reproducible despite non-deterministic
   completion order (important for backtests).

> **Rust analogue:** `rayon`'s `par_iter().map(evaluate)` for the scatter with a `crossbeam`
> channel for the streaming fan-in, joining on the parallel iterator; or `tokio` tasks +
> `JoinSet` if the strategies are async I/O-bound.

## Render

```bash
# with the plantuml CLI
plantuml docs/design/*.puml

# or via Docker, no local install
docker run --rm -v "$PWD:/work" -w /work plantuml/plantuml docs/design/*.puml
```

Each diagram is also viewable inline in VS Code with the *PlantUML* extension (Alt+D).

## Mapping diagram → design

| Diagram box | Design element |
| --- | --- |
| Interactive Broker / Binance / Derive | `DataSource` subclasses |
| Sentiment analysis, On-chain movement | `AltDataSource` subclasses |
| Ingestion every hour | `IngestionScheduler` + `IngestionService` |
| Strategy A/B/C/…N (risk %, certainty) | `Strategy` subclasses → `StrategySignal` |
| Analysis → `{option, strategy, certainty, …}` | `AnalysisEngine` |
| Resultset (TopN, diversify) | `ResultSelector` + `DiversificationPolicy` → `ResultSet` |
| Risk Management + Portfolio management | `RiskManager` + `PortfolioManager` |
| Action · Human / Automation (wallet/balance classifier) | `ActionEngine` + `ActorClassifier` + `ActionHandler` |
| Learning | `LearningModule` → `LearningRecord` |
| Logging is Journaling | `Journal` → `JournalEntry` (cross-cutting) |
