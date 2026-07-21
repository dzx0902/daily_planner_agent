from datetime import date

import pytest

from daily_planner.core.sync_service import SyncService
from daily_planner.exceptions import IntegrationError
from daily_planner.models.sync import SyncOperation, SyncStatus
from daily_planner.models.task import Task
from daily_planner.repositories.sqlite import SQLiteTaskRepository


class RetryMirror:
    provider_name = "notion"

    def __init__(self):
        self.created = []

    async def create_task_with_remote_id(self, task):
        self.created.append(task.id)
        return task, "retried-page-id"


class FailingRetryMirror(RetryMirror):
    async def create_task_with_remote_id(self, task):
        raise IntegrationError("still failing")


@pytest.mark.asyncio
async def test_sync_retry_create_success_records_mapping_and_marks_success(tmp_path):
    repo = SQLiteTaskRepository(tmp_path / "daily.db")
    task = Task(title="口语练习", plan_date=date(2026, 7, 12))
    item = await repo.record_sync_failure(task.id, "notion", SyncOperation.CREATE, task.model_dump_json(), "failed")

    report = await SyncService(repo, RetryMirror()).retry_failed()
    updated = await repo.get_sync_queue_item(item.id)
    mapping = await repo.get_sync_mapping(task.id, "notion")

    assert report.attempted == 1
    assert report.succeeded == 1
    assert updated.status == SyncStatus.SUCCESS
    assert mapping.remote_id == "retried-page-id"


@pytest.mark.asyncio
async def test_sync_retry_failure_increments_attempts(tmp_path):
    repo = SQLiteTaskRepository(tmp_path / "daily.db")
    task = Task(title="口语练习", plan_date=date(2026, 7, 12))
    item = await repo.record_sync_failure(task.id, "notion", SyncOperation.CREATE, task.model_dump_json(), "failed")

    report = await SyncService(repo, FailingRetryMirror()).retry_failed()
    updated = await repo.get_sync_queue_item(item.id)

    assert report.failed == 1
    assert updated.status == SyncStatus.FAILED
    assert updated.attempts == 2
