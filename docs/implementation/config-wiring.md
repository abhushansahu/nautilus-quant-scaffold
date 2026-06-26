# Config wiring — single source of truth

Phases 1–8 introduced venue-specific defaults in selectors, reference strategy, and schema as vertical-slice shortcuts. Phase 9 aligns runtime behavior with layered YAML.

## Rule

**YAML profile → `load_config()` → `node/factory.py` → strategy / selector**

Code defaults in Pydantic models are fallbacks for partial loads and unit tests only. Production paths must receive resolved values from `AppConfig` helpers:

| Resolved field | Helper | Fallback chain |
| --- | --- | --- |
| `settlement_currency` | `resolved_settlement_currency()` | `reference.settlement_currency` → `venue.base_currency` |
| `option_series_expiry_time_utc` | `resolved_option_expiry_time()` | `reference.option_series_expiry_time_utc` → `session.market_close_utc` |
| `option_venue` | `resolved_option_venue()` | `reference.option_venue` → `venue.name` |
| `option_multiplier` | `resolved_option_multiplier()` | `reference.option_multiplier` → IB `100.0`, else `1.0` |
| `option_series_id` | `resolved_option_series_id()` | `reference.option_series_id` → derive from `underlying` |
| Fee schedule | `config.fees` | `configs/fees/{venue}.yaml` via loader |

## What changed

- `ReferenceStrategyConfig` no longer carries crypto-first defaults (`BTC`, `08:00`).
- `IbStructureSelector` / `DeribitStructureSelector` require `fee_schedule` from config — no duplicate fee constants in `__init__`.
- `resolve_structure_selector()` threads venue, session close, and multiplier from factory wiring.
- `ReferenceZeroDteStrategy` fails closed if factory does not supply resolved reference fields when structure selection is enabled.

## When code defaults are allowed

- Unit tests with explicit constructor arguments.
- `AppConfig()` bare defaults for non-reference strategies (skeleton, gated_skeleton).
- `backtest_plumbing: true` paths that skip structure selection.

## Non-goals

- Do not read committed catalog fixture constants in production code.
- Do not remove all Pydantic defaults — partial YAML and tests still need safe fallbacks.
