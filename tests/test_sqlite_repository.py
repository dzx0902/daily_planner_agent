from datetime import date

import pytest

from daily_planner.models.task import Task, TaskStatus
from daily_planner.repositories.sqlite import SQLiteTaskRepository


@pytest.mark.asyncio
async def test_sqlite_repository_crud(tmp_path):
    repo = SQLiteTaskRepository(tmp_path / "daily.db")
    task = await repo.create_task(Task(title="口语练习", plan_date=date(2026, 7, 12)))

    fetched = await repo.get_task(task.id)
    assert fetched.title == "口语练习"

    listed = await repo.list_tasks_by_date(date(2026, 7, 12))
    assert len(listed) == 1

    matches = await repo.search_open_tasks("口语")
    assert matches[0].id == task.id

    done = await repo.update_status(task.id, TaskStatus.DONE)
    assert done.status == TaskStatus.DONE
