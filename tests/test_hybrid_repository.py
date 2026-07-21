from datetime import date, datetime

import pytest

from daily_planner.exceptions import IntegrationError
from daily_planner.models.sync import SyncOperation, SyncStatus
from daily_planner.models.task import Task, TaskStatus
from daily_planner.repositories.hybrid import HybridTaskRepository
from daily_planner.repositories.sqlite import SQLiteTaskRepository


class MirrorRecorder:
    def __init__(self):
        self.status_updates = []
        self.schedule_updates = []
        self.created = []

    async def create_task(self, task):
        self.created.append(task.id)
        return task

    async def get_task(self, task_id):
        return None

    async def list_tasks_by_date(self, plan_date, status=None, user_id="default"):
        return []

    async def search_open_tasks(self, keyword, plan_date=None, user_id="default"):
        return []

    async def update_status(self, task_id, status):
        self.status_updates.append((task_id, status))
        return None

    async def update_schedule(self, task_id, start, end):
        self.schedule_updates.append((task_id, start, end))
        return None

    async def append_result_note(self, task_id, note):
        return None


class RemoteIdMirror(MirrorRecorder):
    provider_name = "notion"

    async def create_task_with_remote_id(self, task):
        self.created.append(task.id)
        return task, "remote-page-id"

    async def update_status_by_remote_id(self, remote_id, status):
        self.status_updates.append((remote_id, status))


class FailingMirror(MirrorRecorder):
    provider_name = "notion"

    async def create_task_with_remote_id(self, task):
        raise IntegrationError("remote write failed")


@pytest.mark.asyncio
async def test_hybrid_updates_mirror_after_primary_update(tmp_path):
    primary = SQLiteTaskRepository(tmp_path / "daily.db")
    mirror = MirrorRecorder()
    repo = HybridTaskRepository(primary, mirror)
    task = await repo.create_task(Task(title="口语练习", plan_date=date(2026, 7, 12)))

    await repo.update_status(task.id, TaskStatus.DONE)
    await repo.update_schedule(task.id, datetime(2026, 7, 12, 20), datetime(2026, 7, 12, 20, 30))

    assert mirror.created == [task.id]
    assert mirror.status_updates == [(task.id, TaskStatus.DONE)]
    assert mirror.schedule_updates[0][0] == task.id


@pytest.mark.asyncio
async def test_hybrid_records_sync_mapping_and_uses_remote_id(tmp_path):
    primary = SQLiteTaskRepository(tmp_path / "daily.db")
    mirror = RemoteIdMirror()
    repo = HybridTaskRepository(primary, mirror)
    task = await repo.create_task(Task(title="口语练习", plan_date=date(2026, 7, 12)))

    mapping = await primary.get_sync_mapping(task.id, "notion")
    await repo.update_status(task.id, TaskStatus.DONE)

    assert mapping.remote_id == "remote-page-id"
    assert mirror.status_updates == [("remote-page-id", TaskStatus.DONE)]


@pytest.mark.asyncio
async def test_hybrid_records_sync_failure(tmp_path):
    primary = SQLiteTaskRepository(tmp_path / "daily.db")
    repo = HybridTaskRepository(primary, FailingMirror())
    task = await repo.create_task(Task(title="口语练习", plan_date=date(2026, 7, 12)))

    failures = await primary.list_sync_queue(SyncStatus.FAILED)

    assert task.title == "口语练习"
    assert len(failures) == 1
    assert failures[0].operation == SyncOperation.CREATE
