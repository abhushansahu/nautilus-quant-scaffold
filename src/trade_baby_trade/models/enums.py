from enum import StrEnum


class ActorKind(StrEnum):
    HUMAN = "HUMAN"
    AUTOMATION = "AUTOMATION"


class RegimeTag(StrEnum):
    CHOP = "CHOP"
    TREND = "TREND"
    PIN_RISK = "PIN_RISK"
    UNKNOWN = "UNKNOWN"


class GateStage(StrEnum):
    EDGE = "EDGE"
    LIQUIDITY = "LIQUIDITY"
    REGIME = "REGIME"
    SESSION = "SESSION"
    GREEK = "GREEK"
    OPERATIONAL = "OPERATIONAL"
    RISK_ENGINE = "RISK_ENGINE"
    LIFECYCLE = "LIFECYCLE"
    FILL = "FILL"
    PNL = "PNL"
