from typing import Literal
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
    type: Literal["step"] = "step"
    step: int
    goal: str
    screenshot: str | None = None


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    result: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
