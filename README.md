# trade_baby_trade

Lightweight, production-ready quant trading platform built as a clean **extension layer over
[NautilusTrader](https://nautilustrader.io/)**. NautilusTrader provides the engine (backtesting,
live trading, order management, risk engine); this repo provides the strategies, data pipeline,
models, analysis, and operational glue.

## Layout

| Path | Responsibility |
| --- | --- |
| `src/core/` | Config loading and secret resolution (env vars only, never literals). |
| `src/nt_ext/` | NautilusTrader extension layer: strategies, risk rules, factories. |
| `src/data_pipeline/` | Ingestion, normalization, and the Parquet data catalog. |
| `src/models/` | JAX models, RL environments, training, and the `SignalModel` inference contract. |
| `src/analysis/` | Pure analytics functions (metrics on dataframes). |
| `src/viz/` | Plotly tearsheets and reusable visual components. |
| `src/apps/` | CLI entrypoints: `backtester`, `live`, `train`, `report`. |
| `config/` | Environment configs (`base`/`backtest`/`paper`/`live`) and strategy configs. |
| `experiments/results/` | Backtest run outputs: Parquet trades/equity + JSON summary (gitignored). |
| `tests/` | Unit and integration tests. |

## Quickstart

```bash
# 1. Install (requires uv, Python 3.14+)
make setup

# 2. Run the smoke backtest (EMA-cross demo on deterministic synthetic data)
make backtest-smoke

# 3. Render the tearsheet for the latest run
make report

# 4. Lint + tests
make lint test
```

## Environments and secrets

- Select the environment with `TRADE_ENV` (`backtest` | `paper` | `live`) or the `--env` CLI flag.
- Config files in `config/` reference environment variable *names*; values come from the
  environment (or a local `.env`, never committed). See `.env.example` for required variables.
- No secrets in source control, configs, or logs. Ever.

## Adding things

- **A strategy**: subclass `nt_ext.strategies.base.BaseSignalStrategy`, place it under
  `src/nt_ext/strategies/multi_asset/` or `src/nt_ext/strategies/options/`, add a YAML config under
  `config/strategies/`, register it in `src/nt_ext/factories.py`, and add unit tests plus a small
  backtest scenario.
- **A venue/data source**: add an ingestion module under `src/data_pipeline/ingestion/` that emits
  the normalized schema in `src/data_pipeline/schemas.py`, document new env vars in `.env.example`.
- **A model**: implement the `SignalModel` protocol (`src/models/inference.py`), train offline via
  `tbt-train` (seeded, params serialized to `artifacts/`), and inject it into a strategy through
  the factory layer. Models never touch venue clients or secrets.

## Dependency groups

- Core install covers backtest/live/analysis.
- `uv sync --group models` adds JAX/Flax/Optax/Gymnasium for model and RL work.
- `uv sync --group viz` adds Plotly for tearsheets.
- `uv sync --group dev` adds pytest, ruff, mypy, pre-commit.
