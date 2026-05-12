import pathlib
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from pydantic import field_validator

from .models import TaskCreate, TaskResponse, TaskState
from .agent_manager import AgentManager

FRONTEND_PATH = pathlib.Path(__file__).parent.parent / "frontend" / "index.html"

manager = AgentManager()

app = FastAPI(title="WebSearchPilot")


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
    if not FRONTEND_PATH.exists():
        raise HTTPException(status_code=503, detail="Frontend not yet deployed")
    return FileResponse(FRONTEND_PATH)
