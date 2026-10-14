from enum import StrEnum


class PurchaseStatus(StrEnum):
    PENDING = "pending"
    GIVEN = "given"
    CANCELLED = "cancelled"
