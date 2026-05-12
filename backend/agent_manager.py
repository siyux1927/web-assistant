import asyncio
import base64
import uuid
from browser_use import Agent

from .config import get_llm
from .models import TaskState, TaskStatus, StepEvent, DoneEvent, ErrorEvent


class AgentManager:
    def __init__(self):
        self._tasks: dict[str, TaskState] = {}
        self._queues: dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def create_task(self, task: str) -> str:
        task_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
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

        async def on_step(browser_state, agent_output, step_num: int) -> None:
            screenshot_b64: str | None = None
            try:
                if isinstance(browser_state.screenshot, bytes):
                    screenshot_b64 = base64.b64encode(browser_state.screenshot).decode()
            except Exception:
                pass

            goal = ""
            try:
                goal = agent_output.next_goal or ""
            except Exception:
                pass

            event = StepEvent(step=step_num, goal=goal, screenshot=screenshot_b64)
            await queue.put(event.model_dump())

        agent = Agent(
            task=task,
            llm=llm,
            max_steps=20,
            register_new_step_callback=on_step,
        )

        try:
            history = await agent.run()
            result = history.final_result() or "任务完成，未提取到结果"
            async with self._lock:
                self._tasks[task_id] = TaskState(
                    task_id=task_id, status=TaskStatus.DONE, result=result
                )
            await queue.put(DoneEvent(result=result).model_dump())
        except Exception as exc:
            async with self._lock:
                self._tasks[task_id] = TaskState(
                    task_id=task_id, status=TaskStatus.FAILED
                )
            await queue.put(ErrorEvent(message=str(exc)).model_dump())
        finally:
            await queue.put(None)
