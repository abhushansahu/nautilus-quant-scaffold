# Minimal NT Parquet catalog fixture

Committed slice for BacktestNode smoke tests — no secrets, no live data.

## Contents

- `SPY.NYSE` equity instrument
- 100 `QuoteTick` records (2024-01-02 14:30–14:35 UTC, 100ms intervals)

## Regenerate

```bash
uv run python scripts/build_catalog_fixture.py
```

Re-run after changing instrument or tick parameters. Commit the updated parquet files.
