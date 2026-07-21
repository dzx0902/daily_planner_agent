from datetime import date

import pytest

from daily_planner.config import Settings
from daily_planner.core.planner_service import PlannerService
from daily_planner.core.scheduler import Scheduler
from daily_planner.llm.parser import RuleBasedParser
from daily_planner.models.task import Task, TaskStatus
from daily_planner.repositories.sqlite import SQLiteTaskRepository


@pytest.mark.asyncio
async def test_planner_service_sqlite_mode_without_notion(tmp_path):
    repo = SQLiteTaskRepository(tmp_path / "daily.db")
    service = PlannerService(RuleBasedParser(), repo, Scheduler(Settings(auto_add_daily_review=False)))

    result = await service.create_plan("今天口语练习30分钟", date(2026, 7, 12))

    assert result.success is True
    assert len(result.scheduled_tasks) == 1
    assert result.scheduled_tasks[0].title == "口语练习"


@pytest.mark.asyncio
async def test_ambiguous_done_does_not_mark_task(tmp_path):
    repo = SQLiteTaskRepository(tmp_path / "daily.db")
    await repo.create_task(Task(title="口语练习 A", plan_date=date.today()))
    await repo.create_task(Task(title="口语练习 B", plan_date=date.today()))
    service = PlannerService(RuleBasedParser(), repo, Scheduler(Settings(auto_add_daily_review=False)))

    result = await service.mark_done("口语")

    assert result.success is False
    assert len(result.candidates) == 2


@pytest.mark.asyncio
async def test_daily_review_is_added_only_once_per_day(tmp_path):
    repo = SQLiteTaskRepository(tmp_path / "daily.db")
    service = PlannerService(RuleBasedParser(), repo, Scheduler(Settings(auto_add_daily_review=True)))

    first = await service.create_plan("今天口语练习30分钟", date(2026, 7, 12))
    second = await service.create_plan("今天提交报名30分钟", date(2026, 7, 12))
    tasks = await repo.list_tasks_by_date(date(2026, 7, 12))

    assert any(task.title == "今日复盘" for task in first.scheduled_tasks)
    assert not any(task.title == "今日复盘" for task in second.scheduled_tasks)
    assert len([task for task in tasks if task.title == "今日复盘"]) == 1


@pytest.mark.asyncio
async def test_new_plan_avoids_existing_scheduled_tasks(tmp_path):
    repo = SQLiteTaskRepository(tmp_path / "daily.db")
    service = PlannerService(RuleBasedParser(), repo, Scheduler(Settings(auto_add_daily_review=False)))

    first = await service.create_plan("今天口语练习30分钟", date(2026, 7, 12))
    second = await service.create_plan("今天提交报名30分钟", date(2026, 7, 12))

    assert first.scheduled_tasks[0].start != second.scheduled_tasks[0].start
    assert second.scheduled_tasks[0].start >= first.scheduled_tasks[0].end


@pytest.mark.asyncio
async def test_cancel_and_archive_done(tmp_path):
    repo = SQLiteTaskRepository(tmp_path / "daily.db")
    service = PlannerService(RuleBasedParser(), repo, Scheduler(Settings(auto_add_daily_review=False)))
    old_task = await repo.create_task(Task(title="旧任务", plan_date=date(2026, 7, 10)))
    await repo.update_status(old_task.id, TaskStatus.DONE)
    await repo.create_task(Task(title="取消任务", plan_date=date(2026, 7, 12)))

    canceled = await service.cancel_task("取消任务")
    archived = await service.archive_done(date(2026, 7, 12))
    old_task_after = await repo.get_task(old_task.id)

    assert canceled.task.status == "Canceled"
    assert archived.message == "Archived 1 done tasks before 2026-07-12."
    assert old_task_after.status == "Canceled"
