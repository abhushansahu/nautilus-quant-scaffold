---
name: backtest-worflow
description: Backtest & Experiment Workflow
When to use:
  - Running a new backtest.
  - Adding or updating experiment configurations.
  - Comparing strategies or parameter sets.
---

Instructions for the skill go here. Provide relative paths to other resources in the skill directory as needed.

Goals:
  - Ensure every experiment is reproducible and discoverable.
  - Keep experiment code separate from core engine logic.

Workflow:
1. Identify or create a configuration entry for the experiment:
   - Strategy class and parameters.
   - Asset universe, time range, and data sources.
   - Risk settings and execution assumptions.
2. Implement or update the backtest runner (e.g., in `src/apps/backtester/main.py` or equivalent) to:
   - Load the experiment configuration.
   - Instantiate the engine, strategy, and risk components.
   - Run the backtest and capture detailed metrics.
3. Persist results to the standard location:
   - Store raw trade and PnL data as Parquet.
   - Store summary statistics and metadata in JSON/YAML.
4. Add or update tests that:
   - Verify that the backtest runs end‑to‑end.
   - Optionally assert basic sanity checks (e.g., PnL not NaN, trades exist).
5. When tuning parameters, prefer batch/grid experiments over manual tweaks; keep configuration‑driven tunings in code, not in notebooks only.