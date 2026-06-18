"""Reusable test doubles for protocol-based components."""

from tests.fakes.data import FakeBarLoader
from tests.fakes.models import FakeSignalModel
from tests.fakes.risk import FakeOrderRiskRule

__all__ = ["FakeBarLoader", "FakeOrderRiskRule", "FakeSignalModel"]
