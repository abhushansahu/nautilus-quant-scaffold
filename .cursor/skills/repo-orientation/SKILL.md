---
name: repo-orientation
description: Repo Orientation & Codebase Search
when to use:
  - When first starting work in this repository.
  - When needing to locate where a particular behavior (e.g., an order type, a risk limit, a data feed) is implemented.
---

Instructions for the skill go here. Provide relative paths to other resources in the skill directory as needed.

Goals:
  - Quickly build a mental model of the repo’s layout.
  - Identify the correct extension points for NautilusTrader integration.
  - Avoid creating duplicate modules when an appropriate one already exists.

Workflow:
1. Read the top-level `README` and any architecture docs to understand the main packages and their responsibilities.
2. Map the core directories:
   - `src/nt_ext/` – NautilusTrader integration layer (strategies, risk, adapters, execution).
   - `src/data_pipeline/` – ingestion, transforms, storage, and catalog of market data.
   - `src/models/` – JAX/RL models, feature extraction, training, and inference.
   - `config/` – environment, connection, strategy, and risk configs.
   - `tests/` – unit and integration tests for the above.
3. Use code search to answer:
   - Where are strategies defined?
   - Where is risk enforced?
   - Where does live trading start?
   - Where do backtests start?
4. Before creating a new module or function, search for similar logic first and reuse or extend it when possible.

Design principles:
- Read `.cursor/rules/design-principles.mdc` for SOLID guidance mapped to this repo.
- Key extension points (registries and protocols):
  - `STRATEGY_REGISTRY` — `src/nt_ext/factories.py`
  - `SignalModel` / `ModelLoader` — `src/models/inference.py`, `src/models/loader.py`
  - `OrderRiskRule` — `src/nt_ext/risk/rules.py`
  - `VENUE_CLIENT_FACTORIES` — `src/apps/live/node.py`