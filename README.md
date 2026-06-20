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

| Path | Purpose |
| --- | --- |
| `docs/design/` | Design documents, puml, and model |

