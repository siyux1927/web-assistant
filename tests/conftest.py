"""Shared pytest fixtures and configuration for the test suite."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def mock_get_llm():
    """Patch get_llm globally so tests don't require ANTHROPIC_API_KEY."""
    mock_llm = MagicMock()
    with patch("backend.agent_manager.get_llm", return_value=mock_llm):
        yield mock_llm
