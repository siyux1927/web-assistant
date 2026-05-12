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
