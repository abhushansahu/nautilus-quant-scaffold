# trade_baby_trade

Personal trading project. [NautilusTrader](https://nautilustrader.io/) is the engine — this repo
is a thin extension layer we build incrementally as needed.

## Install

```bash
make setup
```

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14+.

Verify the engine is available:

```bash
uv run python -c "import nautilus_trader; print('ok')"
```

## What's here

Empty placeholders only. No strategies, configs, or CLI yet — add them one at a time when ready.

| Path | Purpose |
| --- | --- |
| `src/` | Extension code (strategies, adapters) |
| `config/` | Environment and strategy configs |
| `tests/` | Tests alongside features |
| `data/` | Local market data and run state (gitignored) |

## Archived scaffold

The full multi-package scaffold (backtester, live trading, models, suites, etc.) is preserved on
branch `archive/full-scaffold`. Cherry-pick from there when you want a specific piece back.

## Next

You decide what to add first.
