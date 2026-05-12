# Web Assistant

> 基于 browser-use + FastAPI + WebSocket 的 Web Agent demo，用自然语言驱动浏览器执行信息搜集任务，实时推送执行截图和步骤。

---

## 演示

用户输入任务 → Agent 自动浏览器操作 → 实时推送每步截图 → 返回提取结果

```
任务输入: "在 GitHub trending 找今天 Python 类目 top 3 项目，给出项目名和简介"

Step 1  正在打开 GitHub trending 页面        [截图]
Step 2  切换到 Python 类目过滤               [截图]
Step 3  提取项目列表信息                      [截图]
...
结果:
  1. browser-use — Make websites accessible for AI agents (★ 48.2k)
  2. ...
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| AI 决策 | Claude Sonnet 4.6 via Anthropic API |
| Web Agent | [browser-use](https://github.com/browser-use/browser-use) |
| 浏览器控制 | Playwright + Chromium (CDP 协议) |
| 后端 | FastAPI + uvicorn |
| 实时通信 | WebSocket (asyncio.Queue 事件流) |
| 前端 | 单文件 HTML + Vanilla JS |

---

## 架构

```
用户浏览器
  │  POST /api/task → 创建任务，返回 task_id
  │  WS  /ws/{id}  → 建立 WebSocket，接收实时事件
  ▼
FastAPI 后端 (backend/main.py)
  │
  ├── AgentManager (backend/agent_manager.py)
  │     ├── 每个任务一个 asyncio.Queue
  │     ├── browser-use Agent 注册 step callback
  │     └── callback 将 StepEvent / DoneEvent / ErrorEvent 压入 Queue
  │
  └── WebSocket handler 消费 Queue，推送 JSON 到前端

browser-use Agent
  └── BrowserSession → Chromium (CDP)
```

**关键设计决策：**
- `asyncio.Queue` 作为 producer/consumer 解耦层，支持 WebSocket 连接晚于任务创建
- `asyncio.Lock` 保护任务状态写入，避免并发竞态
- `Literal["step"|"done"|"error"]` 类型约束 WebSocket 事件契约
- `agent.run(max_steps=20)` 控制最大执行步数，防止失控

---

## 快速开始

**环境要求：** Python 3.11+

```bash
# 1. 安装依赖
pip install -e ".[dev]"
playwright install chromium

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填写 ANTHROPIC_API_KEY=sk-ant-...

# 3. 启动服务
uvicorn backend.main:app --reload --port 8000

# 4. 打开浏览器
open http://localhost:8000
```

**运行测试：**

```bash
pytest tests/ -v  # 20 个测试，无需真实 API Key
```

---

## 项目结构

```
web-assistant/
├── backend/
│   ├── agent_manager.py   # browser-use 封装 + asyncio.Queue 事件流
│   ├── config.py          # LLM 客户端工厂（单例 + lru_cache）
│   ├── main.py            # FastAPI: REST API + WebSocket + 前端服务
│   └── models.py          # Pydantic 数据模型（任务状态 + WebSocket 事件）
├── frontend/
│   └── index.html         # 单文件 UI：任务输入 + 步骤时间轴 + 结果展示
├── tests/
│   ├── conftest.py        # pytest fixtures（mock LLM，无需真实 API Key）
│   ├── test_agent_manager.py
│   ├── test_api.py
│   └── test_models.py
├── docs/
│   └── browser-use-deep-dive.md  # browser-use 源码深度解析
├── pyproject.toml
└── .env.example
```

---

## API

```
POST /api/task
  Body:    { "task": "你的信息搜集任务描述" }
  Returns: { "task_id": "uuid" }

GET /api/task/{task_id}
  Returns: { "task_id": "...", "status": "running|done|failed", "result": "..." }

WS /ws/{task_id}
  Server → Client events:
    { "type": "step", "step": 3, "goal": "正在搜索...", "screenshot": "base64..." }
    { "type": "done", "result": "找到以下项目：..." }
    { "type": "error", "message": "..." }
```

---

## 深度阅读

在动手做这个项目之前，我深度阅读了 browser-use 的源码，整理了一篇分析文章：

**[→ browser-use 源码深度解析：一个 Web Agent 框架的工程落地实践](docs/browser-use-deep-dive.md)**

覆盖：Agent Loop 三阶段模型、DOM 三协议并行提取、Token 压缩机制、死循环检测、结构化输出可靠性、多标签页竞态处理。

---

## 路线图

**V0（当前）**
- [x] 信息搜集任务
- [x] 实时步骤截图推送
- [x] FastAPI + WebSocket 后端
- [x] 单文件 HTML 前端

**V1（计划中）**
- [ ] 多 tab 并发信息搜集（Orchestrator + Executor 双层架构）
- [ ] 表单操作、登录流程
- [ ] 任务历史持久化
- [ ] React 前端 + 可视化 Agent 执行图
- [ ] 接入 MCP，动态发现外部工具
- [ ] DOM 提取失败时降级到 Vision 模型兜底

---

## License

MIT
