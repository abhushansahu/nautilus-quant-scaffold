# Live catalog capture — Feather vs JSONL journal

Phase 9 closes the COLD-tier catalog backfill gap using NautilusTrader-native persistence. This is **not** a custom ingestion pipeline and **not** a replacement for the JSONL `Journal`.

## Two tracks

| Track | Location | Purpose |
| --- | --- | --- |
| CI / regression | `tests/fixtures/catalog*`, `catalog_deribit/` | Deterministic synthetic slices — no network |
| Operator capture | `data/streaming/<run-id>/` → `data/catalogs/<run-id>/` | Paper/live replay from real sessions |

Operator captures are gitignored. Never commit live Parquet to the repo.

## Responsibilities

| Layer | Mechanism | Purpose |
| --- | --- | --- |
| Decision audit | Custom `Journal` (JSONL) | Gates, intents, `ref_id` — unchanged |
| Market replay | NT `StreamingFeatherWriter` | `QuoteTick`, `OptionGreeks` the strategy subscribed to |
| Attribution | `LearningModule` | `LearningRecord` on fills — does not require streaming |

## Operator workflow

```bash
# 1. Capture (Deribit testnet or IB paper)
nautilus-zerodte paper --config configs/profiles/paper_btc.yaml --streaming

# 2. Stop node (Ctrl+C), then convert feather → Parquet
nautilus-zerodte catalog convert --run-id <run-id>

# 3. Replay
nautilus-zerodte backtest --config configs/profiles/backtest_btc.yaml \
  --catalog data/catalogs/<run-id>
```

NT writes feathers to `{stream_path}/live/{instance_id}/`. The convert command calls `ParquetDataCatalog.convert_stream_to_data()` with `subdirectory="live"`.

## Default stream types (HOT/WARM)

Configured in `configs/streaming/default.yaml`:

- `QuoteTick` — underlying/perp + option legs
- `OptionGreeks` — open-leg greeks (Deribit venue-streamed path)

Order events are optional; the JSONL journal already covers decision audit.

## Non-goals

- No streaming in CI.
- No custom Feather/Parquet writers — NT writer + `convert_stream_to_data` only.
- No duplication of gate audit in Feather files.
