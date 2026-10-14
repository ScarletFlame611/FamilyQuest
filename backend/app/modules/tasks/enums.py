from enum import StrEnum


class TaskStatus(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    MARKED = "marked"
    CONFIRMED = "confirmed"
