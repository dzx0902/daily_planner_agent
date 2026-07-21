from __future__ import annotations

from datetime import date, datetime
import json

from daily_planner.exceptions import DailyPlannerError
from daily_planner.models.sync import SyncMapping, SyncOperation
from daily_planner.models.task import Task, TaskStatus
from daily_planner.repositories.base import TaskRepository


class HybridTaskRepository(TaskRepository):
    def __init__(self, primary: TaskRepository, mirror: TaskRepository) -> None:
        self.primary = primary
        self.mirror = mirror

    async def create_task(self, task: Task) -> Task:
        saved = await self.primary.create_task(task)
        try:
            if hasattr(self.mirror, "create_task_with_remote_id"):
                _, remote_id = await self.mirror.create_task_with_remote_id(saved)
                await self._record_mapping(saved.id, remote_id)
            else:
                await self.mirror.create_task(saved)
        except DailyPlannerError as exc:
            await self._record_failure(saved.id, SyncOperation.CREATE, saved.model_dump_json(), str(exc))
        return saved

    async def get_task(self, task_id: str) -> Task | None:
        return await self.primary.get_task(task_id)

    async def list_tasks_by_date(self, plan_date: date, status: TaskStatus | None = None, user_id: str = "default") -> list[Task]:
        return await self.primary.list_tasks_by_date(plan_date, status, user_id)

    async def list_tasks(
        self,
        plan_date: date | None = None,
        status: TaskStatus | None = None,
        user_id: str = "default",
    ) -> list[Task]:
        if hasattr(self.primary, "list_tasks"):
            return await self.primary.list_tasks(plan_date, status, user_id)
        if not plan_date:
            plan_date = date.today()
        return await self.primary.list_tasks_by_date(plan_date, status, user_id)

    async def search_open_tasks(self, keyword: str, plan_date: date | None = None, user_id: str = "default") -> list[Task]:
        return await self.primary.search_open_tasks(keyword, plan_date, user_id)

    async def update_status(self, task_id: str, status: TaskStatus) -> Task | None:
        task = await self.primary.update_status(task_id, status)
        if task:
            try:
                mapping = await self._get_mapping(task_id)
                if mapping and hasattr(self.mirror, "update_status_by_remote_id"):
                    await self.mirror.update_status_by_remote_id(mapping.remote_id, status)
                else:
                    await self.mirror.update_status(task_id, status)
            except DailyPlannerError as exc:
                await self._record_failure(task_id, SyncOperation.UPDATE_STATUS, json.dumps({"status": status.value}), str(exc))
        return task

    async def update_schedule(self, task_id: str, start: datetime, end: datetime) -> Task | None:
        task = await self.primary.update_schedule(task_id, start, end)
        if task:
            try:
                mapping = await self._get_mapping(task_id)
                if mapping and hasattr(self.mirror, "update_schedule_by_remote_id"):
                    await self.mirror.update_schedule_by_remote_id(mapping.remote_id, start, end)
                else:
                    await self.mirror.update_schedule(task_id, start, end)
            except DailyPlannerError as exc:
                await self._record_failure(
                    task_id,
                    SyncOperation.UPDATE_SCHEDULE,
                    json.dumps({"start": start.isoformat(), "end": end.isoformat()}),
                    str(exc),
                )
        return task

    async def append_result_note(self, task_id: str, note: str) -> Task | None:
        task = await self.primary.append_result_note(task_id, note)
        if task:
            try:
                mapping = await self._get_mapping(task_id)
                if mapping and hasattr(self.mirror, "append_result_note_by_remote_id"):
                    await self.mirror.append_result_note_by_remote_id(mapping.remote_id, note)
                else:
                    await self.mirror.append_result_note(task_id, note)
            except DailyPlannerError as exc:
                await self._record_failure(task_id, SyncOperation.APPEND_NOTE, json.dumps({"note": note}), str(exc))
        return task

    async def list_sync_queue(self, status=None):
        if hasattr(self.primary, "list_sync_queue"):
            return await self.primary.list_sync_queue(status)
        return []

    async def _record_mapping(self, local_task_id: str, remote_id: str) -> None:
        if hasattr(self.primary, "record_sync_mapping"):
            await self.primary.record_sync_mapping(
                SyncMapping(local_task_id=local_task_id, remote_provider=self._provider_name(), remote_id=remote_id)
            )

    async def _get_mapping(self, local_task_id: str):
        if hasattr(self.primary, "get_sync_mapping"):
            return await self.primary.get_sync_mapping(local_task_id, self._provider_name())
        return None

    async def _record_failure(self, local_task_id: str, operation: SyncOperation, payload: str, error: str) -> None:
        if hasattr(self.primary, "record_sync_failure"):
            await self.primary.record_sync_failure(local_task_id, self._provider_name(), operation, payload, error)

    def _provider_name(self) -> str:
        return getattr(self.mirror, "provider_name", self.mirror.__class__.__name__.lower())
