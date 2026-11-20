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
    HOMEWORK = "homework"
    READING = "reading"
    BACKPACK = "backpack"
    SPORT = "sport"
    MUSIC = "music"
    MORNING = "morning"
    SLEEP = "sleep"
    TEETH = "teeth"
    WALK = "walk"
    CALL = "call"
    BABY = "baby"


class TaskAction(StrEnum):
    TAKE = "take"
    MARK = "mark"
    CONFIRM = "confirm"
    REJECT = "reject"
    REVOKE = "revoke"
