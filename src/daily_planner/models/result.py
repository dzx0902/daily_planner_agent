from __future__ import annotations

from pydantic import BaseModel, Field

from daily_planner.models.task import Task


class ActionResult(BaseModel):
    success: bool
    message: str
    task: Task | None = None
    candidates: list[Task] = Field(default_factory=list)


class PlanResult(BaseModel):
    success: bool
    message: str
    scheduled_tasks: list[Task] = Field(default_factory=list)
    unscheduled_tasks: list[Task] = Field(default_factory=list)
