# WebSearchPilot V0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable Web Assistant demo where users input a search task, a browser-use Agent executes it with real-time step visualization via WebSocket, and returns extracted results.

**Architecture:** FastAPI backend exposes a REST endpoint to create tasks and a WebSocket endpoint to stream execution events; an AgentManager wraps browser-use Agent, buffers events via asyncio.Queue, and pushes step screenshots + goals to connected WebSocket clients; a single-file HTML frontend connects over WebSocket and renders the step timeline.

**Tech Stack:** Python 3.11+, browser-use, langchain-anthropic, FastAPI, uvicorn, pytest, httpx, vanilla HTML/JS (no build step)

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Dependencies + project metadata |
| `.env.example` | Required env vars template |
| `backend/__init__.py` | Package marker |
| `backend/models.py` | Pydantic models: task state, WebSocket events |
| `backend/config.py` | LLM client factory (singleton) |
| `backend/agent_manager.py` | browser-use wrapper, asyncio.Queue per task |
| `backend/main.py` | FastAPI app: POST /api/task, GET /api/task/{id}, WS /ws/{id} |
| `frontend/index.html` | Single-file UI: input, step timeline, result |
| `tests/__init__.py` | Package marker |
| `tests/test_models.py` | Model serialization + validation |
| `tests/test_agent_manager.py` | AgentManager unit tests with mocked Agent |
| `tests/test_api.py` | FastAPI endpoint tests with TestClient |

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `backend/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "web-assistant"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "browser-use>=0.1.0",
    "langchain-anthropic>=0.3.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "python-dotenv>=1.0.0",
    "websockets>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]
```

- [ ] **Step 2: Create .env.example**

```
ANTHROPIC_API_KEY=sk-ant-...
# Optional: control browser visibility (true = show browser window)
BROWSER_HEADLESS=true
```

- [ ] **Step 3: Create package markers and install**

```bash
touch backend/__init__.py tests/__init__.py
pip install -e ".[dev]"
playwright install chromium
```

Expected: no errors, chromium downloaded.

- [ ] **Step 4: Commit**

```bash
git init
git add pyproject.toml .env.example backend/__init__.py tests/__init__.py
git commit -m "chore: project scaffold with dependencies"
```

---

## Task 2: Data Models

**Files:**
- Create: `backend/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py -v
```

Expected: `ImportError: cannot import name 'TaskStatus' from 'backend.models'`

- [ ] **Step 3: Implement models**

Create `backend/models.py`:

```python
from enum import Enum
from pydantic import BaseModel


class TaskStatus(str, Enum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TaskCreate(BaseModel):
    task: str


class TaskResponse(BaseModel):
    task_id: str


class TaskState(BaseModel):
    task_id: str
    status: TaskStatus
    result: str | None = None


class StepEvent(BaseModel):
    type: str = "step"
    step: int
    goal: str
    screenshot: str | None = None


class DoneEvent(BaseModel):
    type: str = "done"
    result: str


class ErrorEvent(BaseModel):
    type: str = "error"
    message: str
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/models.py tests/test_models.py
git commit -m "feat: add task and event data models"
```

---

## Task 3: LLM Config

**Files:**
- Create: `backend/config.py`

- [ ] **Step 1: Verify callback signature against browser-use source**

Before writing config, confirm the browser-use `register_new_step_callback` signature by checking locally:

```bash
python -c "
from browser_use import Agent
import inspect
# Print the signature of the register_new_step_callback method
print(inspect.signature(Agent.register_new_step_callback))
"
```

If the output shows `(callback)` or similar, note the actual callback parameter types from the source:

```bash
python -c "
import browser_use.agent.service as s
import inspect
src = inspect.getsource(s.Agent.run)
# Find where step callback is invoked
for i, line in enumerate(src.split('\n')):
    if 'new_step_callback' in line:
        print(i, line)
"
```

Record the actual signature. It will be one of:
- `async def callback(history: AgentHistoryList, agent: Agent) -> None`
- `async def callback(state, output, step_num: int) -> None`

Use this signature in Task 4.

- [ ] **Step 2: Create config.py**

Create `backend/config.py`:

```python
import os
from functools import lru_cache
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def get_llm() -> ChatAnthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=api_key,
    )


def is_headless() -> bool:
    return os.environ.get("BROWSER_HEADLESS", "true").lower() == "true"
```

- [ ] **Step 3: Smoke-test config loads**

```bash
ANTHROPIC_API_KEY=test-key python -c "from backend.config import get_llm; print('ok')"
```

Expected: `ok` (no error; does not call Anthropic API).

- [ ] **Step 4: Commit**

```bash
git add backend/config.py
git commit -m "feat: add LLM config factory with env loading"
```

---

## Task 4: Agent Manager

**Files:**
- Create: `backend/agent_manager.py`
- Create: `tests/test_agent_manager.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_agent_manager.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_agent_manager.py -v
```

Expected: `ImportError: cannot import name 'AgentManager' from 'backend.agent_manager'`

- [ ] **Step 3: Implement AgentManager**

Create `backend/agent_manager.py`:

```python
import asyncio
import base64
import uuid
from browser_use import Agent
from browser_use.browser.browser import BrowserConfig

from .config import get_llm, is_headless
from .models import TaskState, TaskStatus, StepEvent, DoneEvent, ErrorEvent


class AgentManager:
    def __init__(self):
        self._tasks: dict[str, TaskState] = {}
        self._queues: dict[str, asyncio.Queue] = {}

    async def create_task(self, task: str) -> str:
        task_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue()
        self._tasks[task_id] = TaskState(task_id=task_id, status=TaskStatus.RUNNING)
        self._queues[task_id] = queue
        asyncio.create_task(self._run_agent(task_id, task, queue))
        return task_id

    def get_task(self, task_id: str) -> TaskState | None:
        return self._tasks.get(task_id)

    def get_queue(self, task_id: str) -> asyncio.Queue | None:
        return self._queues.get(task_id)

    async def _run_agent(self, task_id: str, task: str, queue: asyncio.Queue) -> None:
        llm = get_llm()
        step_counter = 0

        agent = Agent(
            task=task,
            llm=llm,
            max_steps=20,
        )

        # NOTE: Verify the actual callback signature from Task 3 Step 1.
        # The implementation below uses the most common pattern.
        # If the signature differs, adjust the parameters accordingly.
        @agent.register_new_step_callback
        async def on_step(agent_output, history) -> None:
            nonlocal step_counter
            step_counter += 1

            screenshot_b64: str | None = None
            try:
                # AgentHistoryList.screenshots() returns list of base64 strings
                screenshots = history.screenshots()
                if screenshots:
                    screenshot_b64 = screenshots[-1]
            except Exception:
                pass

            goal = ""
            try:
                goal = agent_output.next_goal or ""
            except Exception:
                pass

            event = StepEvent(step=step_counter, goal=goal, screenshot=screenshot_b64)
            await queue.put(event.model_dump())

        try:
            history = await agent.run()
            result = history.final_result() or "任务完成，未提取到结果"
            self._tasks[task_id].status = TaskStatus.DONE
            self._tasks[task_id].result = result
            await queue.put(DoneEvent(result=result).model_dump())
        except Exception as exc:
            self._tasks[task_id].status = TaskStatus.FAILED
            await queue.put(ErrorEvent(message=str(exc)).model_dump())
        finally:
            await queue.put(None)  # sentinel: tells WebSocket handler to close
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_agent_manager.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/agent_manager.py tests/test_agent_manager.py
git commit -m "feat: add AgentManager wrapping browser-use with asyncio.Queue event streaming"
```

---

## Task 5: FastAPI Backend

**Files:**
- Create: `backend/main.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api.py -v
```

Expected: `ImportError: cannot import name 'app' from 'backend.main'`

- [ ] **Step 3: Implement FastAPI app**

Create `backend/main.py`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import field_validator

from .models import TaskCreate, TaskResponse, TaskState, TaskStatus
from .agent_manager import AgentManager


manager = AgentManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Web Assistant", lifespan=lifespan)


class TaskCreateValidated(TaskCreate):
    @field_validator("task")
    @classmethod
    def task_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("task must not be empty")
        return v.strip()


@app.post("/api/task", response_model=TaskResponse)
async def create_task(body: TaskCreateValidated) -> TaskResponse:
    task_id = await manager.create_task(body.task)
    return TaskResponse(task_id=task_id)


@app.get("/api/task/{task_id}", response_model=TaskState)
async def get_task(task_id: str) -> TaskState:
    state = manager.get_task(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return state


@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str) -> None:
    queue = manager.get_queue(task_id)
    if queue is None:
        await websocket.close(code=4004)
        return

    await websocket.accept()
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()


@app.get("/")
async def serve_frontend() -> FileResponse:
    return FileResponse("frontend/index.html")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py tests/test_api.py
git commit -m "feat: add FastAPI backend with task REST API and WebSocket streaming"
```

---

## Task 6: Frontend

**Files:**
- Create: `frontend/index.html`

No unit tests for the frontend (vanilla JS in a single file). Tested manually in Task 7.

- [ ] **Step 1: Create frontend/index.html**

```bash
mkdir -p frontend
```

Create `frontend/index.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Web Assistant</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #0f0f0f; color: #e0e0e0; min-height: 100vh; padding: 24px; }
    h1 { font-size: 1.5rem; font-weight: 600; margin-bottom: 24px; color: #fff; }
    .input-row { display: flex; gap: 12px; margin-bottom: 32px; }
    textarea { flex: 1; padding: 12px 16px; border-radius: 8px; border: 1px solid #333;
               background: #1a1a1a; color: #e0e0e0; font-size: 14px; resize: vertical;
               min-height: 60px; }
    textarea:focus { outline: none; border-color: #555; }
    button { padding: 0 24px; border-radius: 8px; border: none; cursor: pointer;
             background: #2563eb; color: #fff; font-size: 14px; font-weight: 500; }
    button:disabled { background: #333; color: #666; cursor: not-allowed; }
    #steps { margin-bottom: 32px; }
    .step-card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px;
                 padding: 16px; margin-bottom: 12px; }
    .step-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
    .step-badge { background: #2563eb; color: #fff; font-size: 11px; font-weight: 600;
                  padding: 2px 8px; border-radius: 4px; }
    .step-goal { font-size: 14px; color: #ccc; }
    .step-screenshot img { width: 100%; border-radius: 4px; max-height: 300px;
                           object-fit: contain; background: #111; }
    #result-section { display: none; background: #1a1a1a; border: 1px solid #2a2a2a;
                      border-radius: 8px; padding: 20px; }
    #result-section h2 { font-size: 1rem; font-weight: 600; margin-bottom: 12px;
                         color: #fff; }
    #result-text { font-size: 14px; line-height: 1.7; color: #ccc;
                   white-space: pre-wrap; word-break: break-word; }
    #status-bar { font-size: 13px; color: #888; margin-bottom: 16px; }
    .error { color: #f87171; }
  </style>
</head>
<body>
  <h1>Web Assistant</h1>

  <div class="input-row">
    <textarea id="task-input" placeholder="描述你的信息搜集任务，例如：找 GitHub 上最近 star 增长最快的 Python AI 项目，列出 top 5"></textarea>
    <button id="start-btn" onclick="startTask()">开始</button>
  </div>

  <div id="status-bar"></div>
  <div id="steps"></div>
  <div id="result-section">
    <h2>最终结果</h2>
    <div id="result-text"></div>
  </div>

  <script>
    let ws = null;

    async function startTask() {
      const task = document.getElementById('task-input').value.trim();
      if (!task) return;

      document.getElementById('start-btn').disabled = true;
      document.getElementById('steps').innerHTML = '';
      document.getElementById('result-section').style.display = 'none';
      document.getElementById('result-text').textContent = '';
      setStatus('正在启动任务...');

      let taskId;
      try {
        const res = await fetch('/api/task', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        taskId = data.task_id;
      } catch (err) {
        setStatus('创建任务失败: ' + err.message, true);
        document.getElementById('start-btn').disabled = false;
        return;
      }

      setStatus('Agent 已启动，正在执行...');
      connectWebSocket(taskId);
    }

    function connectWebSocket(taskId) {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      ws = new WebSocket(`${proto}://${location.host}/ws/${taskId}`);

      ws.onmessage = (e) => {
        const event = JSON.parse(e.data);
        if (event.type === 'step') handleStep(event);
        else if (event.type === 'done') handleDone(event);
        else if (event.type === 'error') handleError(event);
      };

      ws.onerror = () => setStatus('WebSocket 连接错误', true);
      ws.onclose = () => document.getElementById('start-btn').disabled = false;
    }

    function handleStep(event) {
      setStatus(`执行中... 第 ${event.step} 步`);
      const card = document.createElement('div');
      card.className = 'step-card';
      card.innerHTML = `
        <div class="step-header">
          <span class="step-badge">Step ${event.step}</span>
          <span class="step-goal">${escapeHtml(event.goal)}</span>
        </div>
        ${event.screenshot
          ? `<div class="step-screenshot"><img src="data:image/png;base64,${event.screenshot}" alt="step screenshot"/></div>`
          : ''}
      `;
      document.getElementById('steps').appendChild(card);
      card.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }

    function handleDone(event) {
      setStatus('任务完成');
      document.getElementById('result-section').style.display = 'block';
      document.getElementById('result-text').textContent = event.result;
      document.getElementById('result-section').scrollIntoView({ behavior: 'smooth' });
    }

    function handleError(event) {
      setStatus('任务失败: ' + event.message, true);
    }

    function setStatus(msg, isError = false) {
      const el = document.getElementById('status-bar');
      el.textContent = msg;
      el.className = isError ? 'error' : '';
    }

    function escapeHtml(str) {
      return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add single-file frontend with WebSocket step timeline"
```

---

## Task 7: Run All Tests & Integration Smoke Test

**Files:** (no new files)

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected:
```
tests/test_models.py::test_task_create_requires_task_field PASSED
tests/test_models.py::test_task_state_defaults PASSED
tests/test_models.py::test_step_event_serializes_screenshot_as_none PASSED
tests/test_models.py::test_step_event_with_screenshot PASSED
tests/test_models.py::test_done_event_serializes PASSED
tests/test_models.py::test_error_event_serializes PASSED
tests/test_agent_manager.py::test_create_task_returns_uuid_string PASSED
tests/test_agent_manager.py::test_get_task_returns_none_for_unknown_id PASSED
tests/test_agent_manager.py::test_get_queue_returns_none_for_unknown_id PASSED
tests/test_agent_manager.py::test_done_event_pushed_to_queue_on_completion PASSED
tests/test_agent_manager.py::test_error_event_pushed_on_agent_exception PASSED
tests/test_api.py::test_create_task_returns_task_id PASSED
tests/test_api.py::test_create_task_rejects_empty_task PASSED
tests/test_api.py::test_get_task_returns_status PASSED
tests/test_api.py::test_get_task_returns_404_for_unknown PASSED
15 passed
```

- [ ] **Step 2: Copy .env.example and set real API key**

```bash
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY=sk-ant-<your-key>
```

- [ ] **Step 3: Start the server**

```bash
uvicorn backend.main:app --reload --port 8000
```

Expected: `INFO: Uvicorn running on http://127.0.0.1:8000`

- [ ] **Step 4: Manual integration test**

Open browser to `http://localhost:8000`.

Test with task: `"在 GitHub trending 页面找今天 Python 类目的 top 3 项目，给出项目名和简介"`

Expected behavior:
1. Step cards appear one by one as Agent executes
2. Each card shows the goal text (e.g., "正在打开 GitHub trending 页面")
3. Screenshots render in cards (if Agent captured them)
4. Final result card shows extracted repo names and descriptions

- [ ] **Step 5: Verify callback signature worked**

If screenshots are `None` in all steps, re-check `agent_manager.py`'s `on_step` callback. Adjust the `history.screenshots()` call based on findings from Task 3 Step 1. The two most likely fixes:

```python
# Fix A: screenshots are on the state object
screenshot_b64 = history[-1].state.screenshot

# Fix B: history exposes a method returning latest screenshot bytes
screenshot_bytes = history.last_screenshot()
screenshot_b64 = base64.b64encode(screenshot_bytes).decode() if screenshot_bytes else None
```

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "feat: Web Assistant V0 complete — browser-use Agent with FastAPI + WebSocket + HTML frontend"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Information search use case → Task 4 (AgentManager runs browser-use on user task)
- [x] Real-time step visualization → Task 4 (step callback) + Task 5 (WebSocket) + Task 6 (frontend)
- [x] POST /api/task → Task 5
- [x] GET /api/task/{id} → Task 5
- [x] WS /ws/{task_id} → Task 5
- [x] max_steps=20 → Task 4 (Agent instantiation)
- [x] Screenshots base64 → Task 4 (on_step callback)
- [x] Single-file frontend → Task 6
- [x] .env with ANTHROPIC_API_KEY → Task 1

**Placeholder scan:** None found.

**Type consistency:**
- `TaskStatus` defined in Task 2, used in Tasks 4, 5 ✓
- `StepEvent`, `DoneEvent`, `ErrorEvent` defined in Task 2, used in Task 4 ✓
- `AgentManager` defined in Task 4, imported in Task 5 as `from .agent_manager import AgentManager` ✓
- `TaskCreateValidated` extends `TaskCreate` in Task 5 — no external references ✓
- `queue.put(None)` sentinel in Task 4 matched by `if event is None: break` in Task 5 ✓
