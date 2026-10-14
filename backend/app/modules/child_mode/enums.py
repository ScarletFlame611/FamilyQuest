from enum import StrEnum


class ChildEventType(StrEnum):
    SCREEN_OPENED = "screen_opened"
    TASK_OPENED = "task_opened"
    BUTTON_PRESSED = "button_pressed"
    TASK_TAKEN = "task_taken"
    TASK_MARKED = "task_marked"
    REWARD_BOUGHT = "reward_bought"
    WRONG_PIN = "wrong_pin"
    PIN_LOCKED = "pin_locked"
    PIN_EXIT = "pin_exit"
    PASSWORD_EXIT = "password_exit"


# Эти события пишет сервер сам, когда проходит соответствующий запрос; от клиента
# они не принимаются, чтобы журнал теста нельзя было дополнить вручную
SERVER_EVENTS = {
    ChildEventType.TASK_TAKEN,
    ChildEventType.TASK_MARKED,
    ChildEventType.REWARD_BOUGHT,
    ChildEventType.WRONG_PIN,
    ChildEventType.PIN_LOCKED,
    ChildEventType.PIN_EXIT,
    ChildEventType.PASSWORD_EXIT,
}
