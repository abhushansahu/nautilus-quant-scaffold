# Gate boundary — pure vs NT greek gate split

**Status:** Accepted (Phase 2)

## Context

0DTE trade gates span both pure policy logic and NautilusTrader runtime APIs. The greek gate
requires NT's `GreeksCalculator.portfolio_greeks()` and cannot live entirely in a pure evaluator.

## Decision

Split gate responsibilities into three layers:

| Layer | Module | Pure? | Responsibility |
| --- | --- | --- | --- |
| Pre-greek gates | `gates/evaluator.py` → `evaluate_pre_greek()` | Yes | edge → liquidity → regime → session → operational |
| Greek snapshots | `BaseZeroDteStrategy` (Phase 3) | No | `self.greeks.portfolio_greeks(spot_shock=..., vol_shock=...)` |
| Greek policy | `gates/evaluator.py` → `check_risk_policy()` | Yes | Limit math on `current_greeks` + `projected_greeks` |
| NT pre-trade | NT `RiskEngine` | No | notional, rate, qty/price — always on, not reimplemented |

## Strategy orchestration pattern (Phase 3)

```
intent = build_intent(slice)
result = evaluate_pre_greek(intent, context)   # pure
if not result.passed: journal + return
projected = self.greeks.portfolio_greeks(...)  # NT
assessment = check_risk_policy(policy, current, projected)  # pure
if not assessment.passed: journal + return
submit_order_list(...)                         # NT RiskEngine → ExecutionEngine
```

## Operational gate checklist

Implemented in `config/schema.py` (`OperationalConfig`) and evaluated in `gates/evaluator.py`:

| Check | GateContext field | Default |
| --- | --- | --- |
| Trading state active | `trading_state_active` | Must be `True` |
| Underlying quote freshness | `underlying_quote_fresh` | Must be `True` (< 30s configurable) |
| Chain snapshot freshness | `chain_snapshot_fresh` | Required when `require_chain_snapshot=True` |
| Daily loss budget | `daily_loss_breached` | Optional; block when `True` |
| Feed / adapter health | `feed_healthy` | Fail closed when `False` |

Default: **no trade** until all checks pass. Each failure → journal at the matching `GateStage`.

## Actor → gate → journal path (Phase 2)

```
SessionActor / RegimeActor
  → msgbus.publish(SessionPhaseSnapshot / RegimeTagSnapshot)
GatedSkeletonStrategy (Phase 2) / BaseZeroDteStrategy (Phase 3)
  → msgbus.subscribe + build GateContext from actor snapshots
  → evaluate_pre_greek(intent, context)
  → journal GATE_REJECT or proceed to greek check
```

Note: NT `publish_data` requires `Data` subclasses; actor context uses MessageBus topics with plain dataclass payloads instead.

## Consequences

- Pure gate unit tests do not require NT runtime (`tests/unit/test_gates.py`).
- Greek policy tests use fixture dict snapshots via `check_risk_policy()`.
- `RiskPolicy.check()` remains on the model; call site is `gates/evaluator.check_risk_policy()`.
- Phase 3 `BaseZeroDteStrategy` owns NT greek calls; evaluator stays importable without NT.

## Phase 3 handoff

1. Implement `strategies/base.py` — FSM with gate orchestration pattern above.
2. Implement `ReferenceZeroDteStrategy` — subscriptions, intent, `OrderList` submit.
3. Wire `--dry-run` to journal intent and skip submit.
4. On `on_order_filled`: journal `FILL` + realized PnL from NT `Portfolio`.
5. Replace `GatedSkeletonStrategy` in factory via config-driven `strategy_class: reference`.
6. Integration test: full journal trail gates → order → fill → PnL.
