"""Model promotion gate: challenger must beat incumbent on the selection metric."""

from __future__ import annotations


def should_promote(
    incumbent_metrics: dict[str, float],
    challenger_metrics: dict[str, float],
    metric: str,
) -> bool:
    """Return True when the challenger strictly beats the incumbent on `metric`."""
    incumbent_value = incumbent_metrics.get(metric)
    challenger_value = challenger_metrics.get(metric)
    if incumbent_value is None:
        return challenger_value is not None
    if challenger_value is None:
        return False
    return challenger_value > incumbent_value
