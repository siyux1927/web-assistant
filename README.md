# Web Assistant

> **Natural language → Browser agent → Real-time results**

[中文版](README_CN.md) | English

Type a task. Watch the agent browse the web step by step, with live screenshots streamed to your browser. Get structured results.

---

## Deep Dive

Before building this, I read through the browser-use source and wrote a detailed breakdown:

**[→ browser-use internals: how a Web Agent framework actually works](docs/browser-use-deep-dive.md)** (Chinese)

Covers: the 3-phase Agent Loop, parallel DOM extraction via 3 CDP protocols, token compression, infinite-loop detection, structured output reliability, and multi-tab race conditions.

---

## Things I Learned Building This

**browser-use 0.12.6 migrated away from LangChain** to its own LLM abstraction layer (`browser_use/llm/`). The `Agent.__init__` validates `llm.provider == "browser-use"` — LangChain's `ChatAnthropic` has no `provider` attribute, causing a cryptic `AttributeError`. Fix: use `browser_use.llm.anthropic.chat.ChatAnthropic` instead.

**`BrowserStateSummary.screenshot` is already base64**, not raw bytes. Wrapping it in `base64.b64encode()` double-encodes and produces a blank image in the browser.

**`max_steps` belongs in `agent.run()`**, not `Agent.__init__()`. Passing it to the constructor silently succeeds (absorbed by `**kwargs`) but has no effect.

---

![Web Assistant completing a GitHub trending search — step timeline with live screenshots and final result](assets/pre-result.GIF)
*End-to-end demo: task input → agent browses GitHub → step timeline with live screenshots → structured result.*

---

## What It Does

```
You:    "Find the top 5 fastest-growing Python AI repos on GitHub trending today"

Step 1  Opening github.com/trending?l=python      [screenshot]
Step 2  Locating trending list items              [screenshot]
Step 3  Extracting names, stars, descriptions     [screenshot]

Result:
  1. browser-use — Make websites accessible for AI agents  ★48.2k (+2.1k today)
  2. ...
```

The agent runs in a real Chromium browser (via Playwright), controlled by Claude Sonnet. Every step is streamed live over WebSocket — no polling, no refresh.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI decision-making | Claude Sonnet via Anthropic API |
| Browser control | [browser-use](https://github.com/browser-use/browser-use) + Playwright + Chromium |
| Backend | FastAPI + uvicorn |
| Real-time streaming | WebSocket + `asyncio.Queue` |
| Frontend | Single-file HTML + Vanilla JS |

No React. No Redux. No build step. Clone and run.

---

## Quick Start

**Requirements:** Python 3.11+, an [Anthropic API key](https://console.anthropic.com/)

```bash
# 1. Install
pip install -e ".[dev]"
playwright install chromium

# 2. Configure
cp .env.example .env
# Edit .env → ANTHROPIC_API_KEY=sk-ant-...

# 3. Run
uvicorn backend.main:app --reload --port 8000

# 4. Open
open http://localhost:8000
```

---

## Architecture

```
Browser (you)
  │  POST /api/task  → create task, get task_id
  │  WS   /ws/{id}  → receive live events
  ▼
FastAPI  (backend/main.py)
  │
  ├── AgentManager  (backend/agent_manager.py)
  │     ├── asyncio.Queue  per task  ← producer/consumer decoupling
  │     ├── asyncio.Lock   protects task state writes
  │     └── register_new_step_callback → streams StepEvent to queue
  │
  └── WebSocket handler  →  consumes queue, pushes JSON to client

browser-use Agent  →  Chromium (CDP)
```

**Key design decisions:**

- `asyncio.Queue` as producer/consumer: WebSocket can connect after task starts without missing events
- Immutable `TaskState` object replacement (not mutation) under `asyncio.Lock` — no partial-state reads
- `None` sentinel in queue signals clean task end to WebSocket handler
- `register_new_step_callback` wired at `Agent()` init, not as a decorator
- `agent.run(max_steps=20)` — `max_steps` lives in `run()`, not `Agent.__init__()` (a common browser-use pitfall)

---

## WebSocket Event Contract

```
Server → Client

{ "type": "step",  "step": 3, "goal": "clicking search button", "screenshot": "<base64>" }
{ "type": "done",  "result": "Here are the top 5 repos: ..." }
{ "type": "error", "message": "..." }
```

All `type` fields are `Literal["step"|"done"|"error"]` — Pydantic rejects anything else at construction time.

---

## REST API

```
POST /api/task
  Body:    { "task": "your task description" }
  Returns: { "task_id": "uuid" }

GET /api/task/{task_id}
  Returns: { "task_id": "...", "status": "running|done|failed", "result": "..." }
```

---

![Typing a task and clicking start — agent initializes in the background](assets/pre-call-browser.GIF)
*Task submission: type in natural language, click start. The agent spins up a Chromium session and begins immediately.*

![Claude navigating GitHub Trending in a real Chromium window via Playwright CDP](assets/pre-scroll.GIF)
*The agent browsing live — real Chromium controlled by Claude Sonnet over Chrome DevTools Protocol.*

---

## Project Structure

```
web-assistant/
├── backend/
│   ├── agent_manager.py   # browser-use wrapper + asyncio.Queue event stream
│   ├── config.py          # LLM client factory (singleton via lru_cache)
│   ├── main.py            # FastAPI: REST + WebSocket + frontend serving
│   └── models.py          # Pydantic models: task state + WebSocket events
├── frontend/
│   └── index.html         # Task input + live step timeline + result display
├── tests/
│   ├── conftest.py        # pytest fixtures (mock LLM — no real API key needed)
│   ├── test_agent_manager.py
│   ├── test_api.py
│   └── test_models.py
├── docs/
│   └── browser-use-deep-dive.md   # Deep dive into browser-use internals (CN)
└── pyproject.toml
```

**Run tests (no API key needed):**

```bash
pytest tests/ -v   # 20 tests
```

---

## Roadmap

**V0 (current)**
- [x] Information gathering tasks
- [x] Live step screenshots streamed over WebSocket
- [x] FastAPI + WebSocket backend
- [x] Zero-build HTML frontend

**V1 (planned)**
- [ ] Multi-tab concurrent search (Orchestrator + Executor architecture)
- [ ] Form interactions and login flows
- [ ] Task history persistence
- [ ] React frontend with agent execution graph
- [ ] MCP integration for dynamic tool discovery
- [ ] Vision model fallback when DOM extraction fails

---

## License

MIT
