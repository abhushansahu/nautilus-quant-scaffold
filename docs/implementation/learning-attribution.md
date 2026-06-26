# Learning attribution (Phase 6)

Rule-based PnL decomposition on 0DTE fills. No ML — `LearningModule.calibrate()` is a
placeholder hook for future policy tuning.

## Scope

| Term | Source | Notes |
| --- | --- | --- |
| `commission` | `OrderFilled.commission` | Backtest via NT `MakerTakerFeeModel`; live from venue |
| `slippage_bps` | Fill price vs quote mid at submit | Separate from spread cost in pre-trade edge |
| `theta_pnl` | Rule: `theta * hold_hours / 24` | 0DTE — small; uses portfolio greeks at fill |
| `gamma_pnl` | Rule: `0.5 * gamma * (dS)^2` | `dS` = underlying move since entry quote |
| `vega_pnl` | Rule: `vega * dIV` | `dIV` from leg greeks delta when available |
| `edge_predicted_bps` | `TradeIntent.edge_after_cost_bps` | Pre-trade estimate from fee schedule + quotes |
| `edge_realized_bps` | Realized PnL vs entry notional | `(realized_pnl / entry_notional) * 10_000` |

## Pre-trade vs post-trade alignment

```
edge_after_cost_bps = edge_before_cost_bps
                    - half_spread_bps
                    - expected_slippage_bps
                    - expected_commission_bps
```

`expected_commission_bps` uses `configs/fees/deribit_options.yaml` (`taker_fee` for IOC
entries). The same rates are wired into `BacktestVenueConfig.fee_model` so backtest
`OrderFilled.commission` matches the edge gate.

## Journal

`LearningModule` writes `GateStage.LEARNING` with a serialized `LearningRecord` payload.
Grep: `"event": "LEARNING_RECORD"`.

## Non-goals (Phase 6)

- IB per-contract `FixedFeeModel` — Phase 8 ✓
- ML calibration — `calibrate()` returns empty adjustments
- Multi-strategy attribution fan-in — Phase 7
