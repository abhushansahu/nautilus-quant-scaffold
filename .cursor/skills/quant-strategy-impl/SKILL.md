---
name: quant-strategy-impl
description: Strategy Implementation & Changes
When to use:
  - Implementing a new trading strategy.
  - Modifying behavior of an existing strategy (entries, exits, sizing, risk hooks).

---

Instructions for the skill go here. Provide relative paths to other resources in the skill directory as needed.

Goals:
  - Keep strategies small, testable, and reusable across live and backtest.
  - Respect the separation between NautilusTrader engine internals and project extensions.

Workflow:
1. Find the strategy base classes in `src/nt_ext/strategies/` and study an existing, well‑tested example.
2. Confirm that the strategy:
   - Inherits from the correct NautilusTrader strategy type.
   - Uses the project’s standard interfaces for signals, risk, and order routing.
3. If adding a new strategy:
   - Place it in the appropriate subpackage (`multi_asset/`, `options/`, etc.).
   - Define configuration parameters through the project’s config system, not hard‑coded constants.
   - Use dependency injection for any models or external services.
4. Add tests:
   - Unit tests covering decision logic (e.g., signal thresholds, position sizing).
   - A small backtest scenario to validate overall behavior on historical data.
5. Run tests and a representative backtest (or replay) before considering the task complete.