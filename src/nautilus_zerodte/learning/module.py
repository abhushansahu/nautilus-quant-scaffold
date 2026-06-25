from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.models.enums import GateStage
from nautilus_zerodte.models.learning import LearningRecord
from nautilus_zerodte.models.trade_intent import TradeIntent


def _money_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if hasattr(value, "as_decimal"):
        return Decimal(str(value.as_decimal()))
    return Decimal(str(value))


class LearningModule:
    """Rule-based fill attribution — commission, slippage, greek decomposition."""

    def __init__(self, journal: Journal, *, strategy_id: str) -> None:
        self._journal = journal
        self._strategy_id = strategy_id
        self._entry_mids: dict[UUID, float] = {}
        self._entry_greeks: dict[UUID, dict[str, float]] = {}

    def register_entry(
        self,
        intent: TradeIntent,
        *,
        quote_mid: float | None,
        greeks: dict[str, float] | None = None,
    ) -> None:
        if quote_mid is not None and quote_mid > 0:
            self._entry_mids[intent.intent_id] = quote_mid
        if greeks:
            self._entry_greeks[intent.intent_id] = dict(greeks)

    def on_order_filled(
        self,
        event: Any,
        *,
        intent: TradeIntent | None,
        intent_id: UUID | None,
        realized_pnl: Decimal | None = None,
        underlying_move: float = 0.0,
        iv_move: float = 0.0,
        hold_hours: float = 0.0,
    ) -> LearningRecord | None:
        if intent_id is None and intent is None:
            return None
        resolved_intent_id = intent_id or (intent.intent_id if intent else None)
        if resolved_intent_id is None:
            return None

        fill_px = float(event.last_px)
        fill_qty = float(event.last_qty)
        entry_notional = fill_px * fill_qty if fill_px > 0 and fill_qty > 0 else 0.0

        commission = _money_decimal(getattr(event, "commission", None))

        entry_mid = self._entry_mids.get(resolved_intent_id, fill_px)
        slippage_bps = 0.0
        if entry_mid > 0:
            slippage_bps = abs(fill_px - entry_mid) / entry_mid * 10_000

        greeks = self._entry_greeks.get(resolved_intent_id, {})
        theta = greeks.get("theta", 0.0)
        gamma = greeks.get("gamma", 0.0)
        vega = greeks.get("vega", 0.0)
        theta_pnl = Decimal(str(theta * hold_hours / 24))
        gamma_pnl = Decimal(str(0.5 * gamma * underlying_move * underlying_move))
        vega_pnl = Decimal(str(vega * iv_move))

        realized = realized_pnl if realized_pnl is not None else Decimal("0")
        edge_predicted = intent.edge_after_cost_bps if intent else 0.0
        edge_realized = (
            float(realized / Decimal(str(entry_notional))) * 10_000 if entry_notional > 0 else 0.0
        )

        order_id_raw = getattr(event, "client_order_id", None)
        record = LearningRecord(
            intent_id=resolved_intent_id,
            order_id=str(order_id_raw) if order_id_raw is not None else None,
            realized_pnl=realized,
            theta_pnl=theta_pnl,
            gamma_pnl=gamma_pnl,
            vega_pnl=vega_pnl,
            slippage_bps=slippage_bps,
            commission=commission,
            edge_predicted_bps=edge_predicted,
            edge_realized_bps=edge_realized,
            features={
                "instrument_id": str(getattr(event, "instrument_id", "")),
                "fill_price": fill_px,
                "fill_qty": fill_qty,
                "entry_notional": entry_notional,
            },
        )
        self._journal.record(
            GateStage.LEARNING,
            ref_id=resolved_intent_id,
            payload={
                "event": "LEARNING_RECORD",
                **record.model_dump(mode="json"),
            },
            strategy_id=self._strategy_id,
        )
        return record

    def calibrate(self) -> dict[str, Any]:
        """Rule-based hook for future policy tuning — no ML in Phase 6."""
        return {"adjustments": {}, "note": "calibrate stub — Phase 6"}
