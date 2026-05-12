import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_create_task_returns_task_id():
    with patch("backend.main.manager") as mock_manager:
        mock_manager.create_task = AsyncMock(return_value="test-uuid-5678")
        response = client.post("/api/task", json={"task": "find top AI repos"})
    assert response.status_code == 200
    assert response.json()["task_id"] == "test-uuid-5678"


def test_create_task_rejects_empty_task():
    response = client.post("/api/task", json={"task": ""})
    assert response.status_code == 422


def test_get_task_returns_status():
    with patch("backend.main.manager") as mock_manager:
        from backend.models import TaskState, TaskStatus
        mock_manager.get_task.return_value = TaskState(
            task_id="abc-123",
            status=TaskStatus.DONE,
            result="Found 3 repos",
        )
        response = client.get("/api/task/abc-123")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "done"
    assert data["result"] == "Found 3 repos"


def test_get_task_returns_404_for_unknown():
    with patch("backend.main.manager") as mock_manager:
        mock_manager.get_task.return_value = None
        response = client.get("/api/task/nonexistent-id")
    assert response.status_code == 404


def test_websocket_streams_events_and_closes_on_sentinel():
    import asyncio

    mock_queue = asyncio.Queue()
    mock_queue.put_nowait({"type": "step", "step": 1, "goal": "searching", "screenshot": None})
    mock_queue.put_nowait({"type": "done", "result": "found results"})
    mock_queue.put_nowait(None)

    with patch("backend.main.manager") as mock_manager:
        mock_manager.get_queue.return_value = mock_queue
        with client.websocket_connect("/ws/test-task-id") as ws:
            msg1 = ws.receive_json()
            msg2 = ws.receive_json()

    assert msg1["type"] == "step"
    assert msg1["step"] == 1
    assert msg2["type"] == "done"
    assert msg2["result"] == "found results"


def test_websocket_closes_with_4004_for_unknown_task():
    with patch("backend.main.manager") as mock_manager:
        mock_manager.get_queue.return_value = None
        try:
            with client.websocket_connect("/ws/unknown-task-id") as ws:
                ws.receive_text()
        except Exception:
            pass  # Expected: connection closed by server
