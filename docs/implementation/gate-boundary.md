# Gate boundary — pure vs NT greek gate split

**Status:** Stub ADR — expand before Phase 2 gate implementation.

## Context

0DTE trade gates span both pure policy logic and NautilusTrader runtime APIs. The greek gate
requires NT's `GreeksCalculator.portfolio_greeks()` and cannot live entirely in a pure evaluator.

## Decision

Split gate responsibilities into three layers:

| Layer | Module | Pure? | Responsibility |
| --- | --- | --- | --- |
| Pre-greek gates | `gates/evaluator.py` → `evaluate_pre_greek()` | Yes | edge → liquidity → regime → session → operational |
| Greek snapshots | `BaseZeroDteStrategy` | No | `self.greeks.portfolio_greeks(spot_shock=..., vol_shock=...)` |
| Greek policy | `gates/evaluator.py` → `RiskPolicy.check()` | Yes | Limit math on `current_greeks` + `projected_greeks` |
| NT pre-trade | NT `RiskEngine` | No | notional, rate, qty/price — always on, not reimplemented |

## Strategy orchestration pattern (Phase 3)

```
intent = build_intent(slice)
result = evaluate_pre_greek(intent, context)   # pure
if not result.passed: journal + return
projected = self.greeks.portfolio_greeks(...)  # NT
assessment = RiskPolicy.check(projected, ...)    # pure
if not assessment.passed: journal + return
submit_order_list(...)                         # NT RiskEngine → ExecutionEngine
```

## Operational gate checklist (Phase 2)

Define in `config/schema.py` before implementing operational gates:

| Check | Source | Default |
| --- | --- | --- |
| Trading state active | NT node / config | Must be `ACTIVE` |
| Underlying quote freshness | Last `QuoteTick` ts vs now | < 30s (configurable) |
| Chain snapshot freshness | Last `OptionChainSlice` ts vs now | < WARM interval + buffer |
| Daily loss budget | Desk rule from `RiskPolicy` | Optional; block new entries if breached |
| Feed / adapter health | NT adapter status | Fail closed if disconnected |

Default: **no trade** until all checks pass.

## Consequences

- Pure gate unit tests do not require NT runtime.
- Greek policy tests use fixture dict snapshots.
- Strategy base class owns NT greek calls; evaluator stays importable without NT in test env (optional).

## Phase 2 handoff

1. Implement `gates/context.py` (`GateContext` value object).
2. Implement `gates/evaluator.py` with `evaluate_pre_greek()` and wire `RiskPolicy.check()`.
3. Add `SessionActor` and `RegimeActor`; register in `node/factory.py`.
4. Unit-test each pre-greek stage in isolation.
