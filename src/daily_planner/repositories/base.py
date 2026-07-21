from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from daily_planner.models.task import Task, TaskStatus


class TaskRepository(ABC):
    @abstractmethod
    async def create_task(self, task: Task) -> Task:
        raise NotImplementedError

    async def create_tasks(self, tasks: list[Task]) -> list[Task]:
        return [await self.create_task(task) for task in tasks]

    @abstractmethod
    async def get_task(self, task_id: str) -> Task | None:
        raise NotImplementedError

    @abstractmethod
    async def list_tasks_by_date(
        self,
        plan_date: date,
        status: TaskStatus | None = None,
        user_id: str = "default",
    ) -> list[Task]:
        raise NotImplementedError

    @abstractmethod
    async def search_open_tasks(
        self,
        keyword: str,
        plan_date: date | None = None,
        user_id: str = "default",
    ) -> list[Task]:
        raise NotImplementedError

    @abstractmethod
    async def update_status(self, task_id: str, status: TaskStatus) -> Task | None:
        raise NotImplementedError

    @abstractmethod
    async def update_schedule(self, task_id: str, start: datetime, end: datetime) -> Task | None:
        raise NotImplementedError

    @abstractmethod
    async def append_result_note(self, task_id: str, note: str) -> Task | None:
        raise NotImplementedError
