# Minimal Deribit NT Parquet catalog fixture for Phase 5 backtests.

Committed slice for BacktestNode integration — no secrets, no live data.

## Contents

- `BTC-PERPETUAL.DERIBIT` perpetual
- `BTC-19MAY26-70000-C` / `BTC-19MAY26-75000-C` call options
- `BTC-CS-19MAY26-70000_75000.DERIBIT` call spread combo
- 50 `QuoteTick` records per instrument (2026-05-19 06:00 UTC, 1s intervals)
- 50 `OptionGreeks` records per option leg

## Regenerate

```bash
uv run python scripts/build_deribit_catalog_fixture.py
```

Re-run after changing instrument or tick parameters. Commit the updated parquet files.
