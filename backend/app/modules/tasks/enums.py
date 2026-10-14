from enum import StrEnum


class TaskStatus(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    MARKED = "marked"
    CONFIRMED = "confirmed"


class TaskIcon(StrEnum):
    TOYS = "toys"
    CAT = "cat"
    PLANT = "plant"
    TRASH = "trash"
    DISHES = "dishes"
    SOCKS = "socks"
    BED = "bed"
    LAUNDRY = "laundry"
    SHOPPING = "shopping"
    MOP = "mop"
    IRON = "iron"
    TOOLS = "tools"
    VACUUM = "vacuum"
    COOKING = "cooking"


class TaskAction(StrEnum):
    TAKE = "take"
    MARK = "mark"
    CONFIRM = "confirm"
    REJECT = "reject"
