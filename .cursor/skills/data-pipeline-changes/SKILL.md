---
name: data-pipeline-changes
description: Data Pipeline Changes
When to use:
  - Adding a new data source (broker/exchange).
  - Changing how raw data is ingested, normalized, or stored.
  - Adding or modifying feature engineering.
---

Instructions for the skill go here. Provide relative paths to other resources in the skill directory as needed.

Goals:
  - Maintain a consistent, documented schema for all datasets.
  - Avoid breaking downstream consumers (models, backtests, live trading).

Workflow:
1. Identify the existing ingestion and storage pattern in `src/data_pipeline/`:
   - Where raw data is fetched.
   - How it is normalized (columns, dtypes, timezone).
   - How it is stored (Parquet/Arrow, directory layout, partitioning).
2. When adding a new source:
   - Implement an ingestion module that outputs the same normalized schema as existing sources.
   - Add validation code (and tests) that check schema and basic data quality.
3. When changing schemas or features:
   - Update schema definitions and docs.
   - Add migration or compatibility code if existing data is expected.
4. Update any model feature extraction code that depends on the changed schema and add tests for it.
5. Run:
   - Unit tests for the data pipeline.
   - A small end‑to‑end flow (ingestion → storage → backtest/model) to ensure nothing breaks.

SOLID checklist (see `.cursor/rules/design-principles.mdc`):
- New sources implement the existing normalized schema; do not fork storage layouts.
- Keep ingestion, caching, and bar resolution in separate modules (`bar_sources`, `bar_cache`, `instrument_resolver`).
- Expose narrow protocols (`CatalogBarSource`, `SyntheticBarSource`) rather than bloating `BarDataLoader`.
- Run `make lint test` for changed pipeline modules.

PR checklist:
- [ ] New sources implement the existing normalized schema
- [ ] Loader, cache, and bar resolution stay in separate modules
- [ ] Unit test uses fake protocol implementation where applicable
- [ ] `make lint test` passes for changed modules