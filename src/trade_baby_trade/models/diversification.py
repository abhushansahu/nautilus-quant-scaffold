from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DiversificationPolicy(BaseModel):
    """Multi-strategy capital allocation rules — Phase 4."""

    model_config = ConfigDict(frozen=True)

    top_n: int = 3
    max_per_instrument: int = 1
    max_per_strategy: float = 0.5
    max_gross_risk_pct: float = 1.0
