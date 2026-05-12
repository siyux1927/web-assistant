# WebSearchPilot（Web Agent自动查找）— 设计规格文档

**日期**：2026-05-12  
**状态**：已确认  
**作者**：siyux1927

---

## 一、项目定位

**Web Assistant** 是一个以简历项目为出发点的 Web Agent demo，展示"理解开源框架架构 + 工程化封装 + 可演示的 AI 能力"的综合能力。

分两个阶段：
- **V0（当前规格）**：用 browser-use 封装，实现"信息搜集"场景，快速可演示
- **V1（后续规划）**：研究 browser-use 后选择性借鉴，自实现核心模块，展示工程深度

---

## 二、V0 功能边界

### 核心 Use Case

用户输入一个**信息搜集任务**（自然语言），Web Assistant 启动浏览器 Agent 自动执行，返回搜集结果。

**示例任务**：
- "帮我找 GitHub 上最近 30 天 star 增长最快的 Python AI 项目，列出 top 5"
- "搜索 Claude 3.7 的最新评测文章，总结优缺点"
- "在 Hacker News 上找今天关于 LLM agent 的讨论，提取主要观点"

### 不在 V0 范围内

- 表单填写、登录、购物等操作类任务（→ V1）
- 多 Agent 并发（→ V1）
- 用户账号系统
- 任务历史持久化（内存中 session 级别即可）

---

## 三、技术栈

### V0 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| LLM | Claude claude-sonnet-4-6 via Anthropic API | 结构化输出稳定，支持 prompt cache |
| Web Agent | browser-use | 工程完整度高，直接封装 |
| 浏览器 | Playwright + Chromium | browser-use 底层依赖 |
| 后端 | FastAPI + Python 3.11+ | 异步支持好，与 browser-use 生态一致 |
| 前端 | 单文件 HTML + vanilla JS | 无构建步骤，快速演示 |
| 实时通信 | WebSocket | Agent 逐步返回结果，流式展示 |

### 为什么不用 Next.js / React

V0 的目标是**快速可演示**，不是前端工程展示。单文件 HTML 零配置、零构建，直接打开即用，录 gif 效果更直观。V1 可以升级为 React。

---

## 四、系统架构

```
用户浏览器
  │  WebSocket 连接
  ▼
┌──────────────────────────────────┐
│         FastAPI 后端              │
│                                  │
│  POST /task    → 创建 Agent 任务 │
│  WS   /ws/{id} → 实时推送步骤   │
│                                  │
│  ┌────────────────────────────┐  │
│  │     AgentManager           │  │
│  │  ├─ 创建 browser-use Agent │  │
│  │  ├─ 注册 step callback     │  │
│  │  └─ 任务状态管理（内存）   │  │
│  └────────────────────────────┘  │
└──────────────────┬───────────────┘
                   │ 调用
┌──────────────────▼───────────────┐
│       browser-use Agent          │
│  └─ BrowserSession（Chromium）   │
└──────────────────────────────────┘
```

### 数据流

1. 用户在前端输入任务，点击"开始"
2. 前端建立 WebSocket 连接
3. 后端创建 browser-use Agent，注册 `step_callback`
4. 每完成一步，`step_callback` 通过 WebSocket 推送：
   - 当前步骤截图（base64）
   - Agent 的 `next_goal`（在做什么）
   - 步骤序号
5. Agent 完成后推送最终结果（extracted content）
6. 前端展示截图时间轴 + 最终答案

---

## 五、后端接口设计

### REST API

```
POST /api/task
Body: { "task": "用户输入的任务描述" }
Response: { "task_id": "uuid" }

GET /api/task/{task_id}
Response: { "status": "running|done|failed", "result": "..." }
```

### WebSocket

```
WS /ws/{task_id}

Server → Client 消息格式:
{
  "type": "step",
  "step": 3,
  "goal": "正在搜索 GitHub trending 页面",
  "screenshot": "base64...",   // 可选，每步不一定有
}

{
  "type": "done",
  "result": "找到以下项目：\n1. ...\n2. ..."
}

{
  "type": "error",
  "message": "任务执行失败：..."
}
```

---

## 六、browser-use 封装层

封装重点在于：

1. **自定义 step callback**：把 agent 每步的 `model_output.next_goal` 和截图推送到 WebSocket

2. **任务超时控制**：设置 `max_steps=20`，防止失控

3. **结果提取**：监听 `done` action 的 `extracted_content` 作为最终结果

```python
# 核心封装示意
agent = Agent(
    task=user_task,
    llm=claude_llm,
    max_steps=20,
)

@agent.register_new_step_callback
async def on_step(state, output, step_num):
    screenshot = await browser_session.get_screenshot()
    await ws.send_json({
        "type": "step",
        "step": step_num,
        "goal": output.next_goal,
        "screenshot": screenshot_to_base64(screenshot)
    })
```

---

## 七、前端设计

单文件 `index.html`，三个区域：

```
┌─────────────────────────────┐
│  Web Assistant              │
│  [任务输入框]  [开始按钮]   │
├─────────────────────────────┤
│  执行过程                   │
│  Step 1: 正在打开 GitHub... │
│  [截图缩略图]               │
│  Step 2: 正在搜索...        │
│  [截图缩略图]               │
├─────────────────────────────┤
│  最终结果                   │
│  1. repo-name: ★ 2.3k ...  │
└─────────────────────────────┘
```

---

## 八、V1 规划（参考）

V1 基于对 browser-use 源码的深度理解，选择性自实现以下模块：

| 模块 | V1 方向 | 动机 |
|------|---------|------|
| DOM 提取 | 保留三协议策略 + 加 Vision 兜底 | 处理 canvas/WebGL 页面 |
| Action 系统 | 接入 MCP，动态发现工具 | 不绑定预注册 action |
| 多 tab 并发 | Orchestrator + Executor 双层 | 并发信息搜集，提速 |
| 前端 | React + 可视化 Agent 执行图 | 更好的 demo 效果 |
| 任务类型 | 新增表单操作、登录流程 | 展示操作类 agent 能力 |

---

## 九、目录结构规划

```
web-assistant/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── agent_manager.py     # browser-use 封装层
│   ├── models.py            # Pydantic 数据模型
│   └── config.py            # LLM 配置、环境变量
├── frontend/
│   └── index.html           # 单文件前端
├── docs/
│   ├── browser-use-deep-dive.md   # 研究文章（GitHub 发布）
│   └── superpowers/specs/...
├── examples/
│   └── demo_tasks.md        # 适合录 gif 的示例任务
├── pyproject.toml
└── README.md
```

---

## 十、简历展示要点

完成后可以在简历 / GitHub README 中展示：

1. **技术深度**：附 browser-use 源码分析文章链接，体现"不只是会用，还看懂了源码"
2. **工程能力**：FastAPI + WebSocket + 异步 Agent 调度，不是玩具代码
3. **可演示性**：录制执行 gif（截图时间轴 + 最终结果），视觉冲击力强
4. **演进规划**：V1 设计体现系统思维，不是一次性 demo
