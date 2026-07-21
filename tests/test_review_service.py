from datetime import date

import pytest

from daily_planner.core.review_service import ReviewService
from daily_planner.models.task import Priority, Task, TaskStatus
from daily_planner.repositories.sqlite import SQLiteTaskRepository


@pytest.mark.asyncio
async def test_review_service_summarizes_and_appends_to_review_task(tmp_path):
    repo = SQLiteTaskRepository(tmp_path / "daily.db")
    done = await repo.create_task(Task(title="完成任务", plan_date=date(2026, 7, 12)))
    await repo.update_status(done.id, TaskStatus.DONE)
    await repo.create_task(Task(title="未完成重点", plan_date=date(2026, 7, 12), priority=Priority.P0))
    review = await repo.create_task(Task(title="今日复盘", plan_date=date(2026, 7, 12)))

    note = await ReviewService(repo).create_daily_review(date(2026, 7, 12))
    updated_review = await repo.get_task(review.id)

    assert "总任务: 3" in note
    assert "已完成: 1" in note
    assert "未完成 P0: 未完成重点" in note
    assert "完成率: 33%" in updated_review.result_note
