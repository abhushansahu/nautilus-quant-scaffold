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
