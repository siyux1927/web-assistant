import pytest
from backend.models import (
    TaskStatus, TaskCreate, TaskResponse, TaskState,
    StepEvent, DoneEvent, ErrorEvent,
)


def test_task_create_requires_task_field():
    t = TaskCreate(task="find top AI repos on GitHub")
    assert t.task == "find top AI repos on GitHub"


def test_task_state_defaults():
    state = TaskState(task_id="abc-123", status=TaskStatus.RUNNING)
    assert state.result is None
    assert state.status == TaskStatus.RUNNING


def test_step_event_serializes_screenshot_as_none():
    event = StepEvent(step=1, goal="Navigating to GitHub")
    data = event.model_dump()
    assert data["type"] == "step"
    assert data["screenshot"] is None


def test_step_event_with_screenshot():
    event = StepEvent(step=2, goal="Reading results", screenshot="base64data==")
    data = event.model_dump()
    assert data["screenshot"] == "base64data=="


def test_done_event_serializes():
    event = DoneEvent(result="Found 5 repos")
    data = event.model_dump()
    assert data["type"] == "done"
    assert data["result"] == "Found 5 repos"


def test_error_event_serializes():
    event = ErrorEvent(message="Connection timeout")
    data = event.model_dump()
    assert data["type"] == "error"
    assert data["message"] == "Connection timeout"
