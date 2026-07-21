from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from daily_planner.exceptions import DailyPlannerError
from daily_planner.models.sync import SyncOperation, SyncQueueItem, SyncStatus
from daily_planner.models.task import Task, TaskStatus


@dataclass
class SyncRetryReport:
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0


class SyncService:
    def __init__(self, local_repository, remote_repository) -> None:
        self.local_repository = local_repository
        self.remote_repository = remote_repository

    async def retry_failed(self, limit: int = 10) -> SyncRetryReport:
        if not hasattr(self.local_repository, "list_sync_queue"):
            return SyncRetryReport()
        items = await self.local_repository.list_sync_queue(SyncStatus.FAILED)
        report = SyncRetryReport()
        for item in items[:limit]:
            report.attempted += 1
            try:
                await self._retry_item(item)
                await self.local_repository.update_sync_queue_item(item.id, SyncStatus.SUCCESS)
                report.succeeded += 1
            except DailyPlannerError as exc:
                await self.local_repository.update_sync_queue_item(item.id, SyncStatus.FAILED, str(exc), increment_attempts=True)
                report.failed += 1
        return report

    async def _retry_item(self, item: SyncQueueItem) -> None:
        payload = json.loads(item.payload)
        mapping = await self._mapping(item.local_task_id)
        if item.operation == SyncOperation.CREATE:
            task = Task.model_validate(payload)
            _, remote_id = await self.remote_repository.create_task_with_remote_id(task)
            await self.local_repository.record_sync_mapping(
                mapping.model_copy(update={"remote_id": remote_id}) if mapping else self._new_mapping(task.id, remote_id)
            )
            return

        if not mapping:
            task = await self.local_repository.get_task(item.local_task_id)
            if not task:
                raise DailyPlannerError(f"Local task not found for sync retry: {item.local_task_id}")
            _, remote_id = await self.remote_repository.create_task_with_remote_id(task)
            await self.local_repository.record_sync_mapping(self._new_mapping(task.id, remote_id))
            mapping = await self._mapping(item.local_task_id)

        if item.operation == SyncOperation.UPDATE_STATUS:
            await self.remote_repository.update_status_by_remote_id(mapping.remote_id, TaskStatus(payload["status"]))
        elif item.operation == SyncOperation.UPDATE_SCHEDULE:
            await self.remote_repository.update_schedule_by_remote_id(
                mapping.remote_id,
                datetime.fromisoformat(payload["start"]),
                datetime.fromisoformat(payload["end"]),
            )
        elif item.operation == SyncOperation.APPEND_NOTE:
            await self.remote_repository.append_result_note_by_remote_id(mapping.remote_id, payload["note"])

    async def _mapping(self, local_task_id: str):
        if hasattr(self.local_repository, "get_sync_mapping"):
            return await self.local_repository.get_sync_mapping(local_task_id, getattr(self.remote_repository, "provider_name", "remote"))
        return None

    def _new_mapping(self, local_task_id: str, remote_id: str):
        from daily_planner.models.sync import SyncMapping

        return SyncMapping(
            local_task_id=local_task_id,
            remote_provider=getattr(self.remote_repository, "provider_name", "remote"),
            remote_id=remote_id,
        )
