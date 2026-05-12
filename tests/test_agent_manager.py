import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agent_manager import AgentManager
from backend.models import TaskStatus


@pytest.mark.asyncio
async def test_create_task_returns_uuid_string():
    manager = AgentManager()
    with patch("backend.agent_manager.Agent") as MockAgent:
        mock_history = MagicMock()
        mock_history.final_result.return_value = "Found 3 results"
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_history)
        # register_new_step_callback must be a no-op
        mock_agent_instance.register_new_step_callback = MagicMock()
        MockAgent.return_value = mock_agent_instance

        task_id = await manager.create_task("find AI repos")

    assert isinstance(task_id, str)
    assert len(task_id) == 36  # UUID4 format: 8-4-4-4-12


@pytest.mark.asyncio
async def test_get_task_returns_none_for_unknown_id():
    manager = AgentManager()
    assert manager.get_task("nonexistent") is None


@pytest.mark.asyncio
async def test_get_queue_returns_none_for_unknown_id():
    manager = AgentManager()
    assert manager.get_queue("nonexistent") is None


@pytest.mark.asyncio
async def test_done_event_pushed_to_queue_on_completion():
    manager = AgentManager()
    with patch("backend.agent_manager.Agent") as MockAgent:
        mock_history = MagicMock()
        mock_history.final_result.return_value = "Found 5 repos"
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_history)
        mock_agent_instance.register_new_step_callback = MagicMock()
        MockAgent.return_value = mock_agent_instance

        task_id = await manager.create_task("find repos")
        queue = manager.get_queue(task_id)
        assert queue is not None

        # Wait for the background task to complete
        await asyncio.sleep(0.1)

        events = []
        while not queue.empty():
            events.append(await queue.get())

        # Last non-None event should be done type
        non_sentinel = [e for e in events if e is not None]
        assert any(e.get("type") == "done" for e in non_sentinel)
        # Sentinel None signals WebSocket to close
        assert None in events


@pytest.mark.asyncio
async def test_error_event_pushed_on_agent_exception():
    manager = AgentManager()
    with patch("backend.agent_manager.Agent") as MockAgent:
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(side_effect=RuntimeError("browser crashed"))
        mock_agent_instance.register_new_step_callback = MagicMock()
        MockAgent.return_value = mock_agent_instance

        task_id = await manager.create_task("some task")
        queue = manager.get_queue(task_id)
        await asyncio.sleep(0.1)

        events = []
        while not queue.empty():
            events.append(await queue.get())

        non_sentinel = [e for e in events if e is not None]
        assert any(e.get("type") == "error" for e in non_sentinel)
        error_events = [e for e in non_sentinel if e.get("type") == "error"]
        assert "browser crashed" in error_events[0]["message"]
