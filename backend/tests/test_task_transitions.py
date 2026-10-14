import pytest

from app.modules.tasks.enums import TaskAction, TaskStatus
from app.modules.tasks.models import Task
from app.modules.tasks.service import TRANSITIONS, TaskTransitionError, _transition

CASES = [(action, status) for action in TaskAction for status in TaskStatus]


@pytest.mark.parametrize(("action", "status"), CASES)
def test_only_listed_transitions_are_allowed(action: TaskAction, status: TaskStatus):
    task = Task(status=status)
    source, target = TRANSITIONS[action]
    if status is source:
        _transition(task, action)
        assert task.status is target
    else:
        with pytest.raises(TaskTransitionError):
            _transition(task, action)
        assert task.status is status
