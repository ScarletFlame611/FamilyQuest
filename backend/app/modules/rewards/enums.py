from enum import StrEnum


class PurchaseStatus(StrEnum):
    PENDING = "pending"
    GIVEN = "given"
    CANCELLED = "cancelled"


class RewardIcon(StrEnum):
    ICE_CREAM = "ice_cream"
    CARTOON = "cartoon"
    MARKERS = "markers"
    PUZZLE = "puzzle"
    PARK = "park"
    CONSTRUCTION_SET = "construction_set"
