from __future__ import annotations

from datetime import date, datetime

from daily_planner.llm.base import LLMParser
from daily_planner.models.result import ActionResult, PlanResult
from daily_planner.models.task import Task, TaskStatus
from daily_planner.repositories.base import TaskRepository
from daily_planner.core.scheduler import Scheduler


class PlannerService:
    def __init__(self, parser: LLMParser, repository: TaskRepository, scheduler: Scheduler) -> None:
        self.parser = parser
        self.repository = repository
        self.scheduler = scheduler

    async def create_plan(self, raw_input: str, target_date: date | None = None, user_id: str = "default") -> PlanResult:
        parsed = await self.parser.parse(raw_input, target_date)
        existing_tasks = await self._list_existing_tasks(parsed.date, user_id)
        include_daily_review = self._should_add_daily_review(existing_tasks)
        scheduled, unscheduled = self.scheduler.schedule(
            parsed,
            raw_input,
            user_id,
            include_daily_review=include_daily_review,
            existing_tasks=existing_tasks,
        )
        created = await self.repository.create_tasks([*scheduled, *unscheduled])
        scheduled_ids = {task.id for task in scheduled}
        return PlanResult(
            success=True,
            message=f"Created {len(created)} tasks, {len(unscheduled)} unscheduled.",
            scheduled_tasks=[task for task in created if task.id in scheduled_ids],
            unscheduled_tasks=[task for task in created if task.id not in scheduled_ids],
        )

    async def get_today_tasks(self, user_id: str = "default") -> list:
        return await self.repository.list_tasks_by_date(date.today(), user_id=user_id)

    async def list_tasks(
        self,
        plan_date: date | None = None,
        status: TaskStatus | None = None,
        user_id: str = "default",
    ) -> list[Task]:
        if hasattr(self.repository, "list_tasks"):
            return await self.repository.list_tasks(plan_date, status, user_id)
        if not plan_date:
            plan_date = date.today()
        return await self.repository.list_tasks_by_date(plan_date, status=status, user_id=user_id)

    async def mark_done(self, keyword_or_id: str, user_id: str = "default") -> ActionResult:
        resolved = await self._resolve_one_open_task(keyword_or_id, user_id)
        if not resolved.success:
            return resolved
        task = await self.repository.update_status(resolved.task.id, TaskStatus.DONE)
        return ActionResult(success=True, message="Task marked done.", task=task)

    async def cancel_task(self, keyword_or_id: str, user_id: str = "default") -> ActionResult:
        resolved = await self._resolve_one_open_task(keyword_or_id, user_id)
        if not resolved.success:
            return resolved
        task = await self.repository.update_status(resolved.task.id, TaskStatus.CANCELED)
        return ActionResult(success=True, message="Task canceled.", task=task)

    async def archive_done(self, before_date: date | None = None, user_id: str = "default") -> ActionResult:
        before_date = before_date or date.today()
        tasks = await self.list_tasks(status=TaskStatus.DONE, user_id=user_id)
        archived = 0
        for task in tasks:
            if task.plan_date < before_date:
                await self.repository.update_status(task.id, TaskStatus.CANCELED)
                archived += 1
        return ActionResult(success=True, message=f"Archived {archived} done tasks before {before_date.isoformat()}.")

    async def reschedule_task(self, task_id: str, new_start: datetime, new_end: datetime) -> ActionResult:
        if new_end <= new_start:
            return ActionResult(success=False, message="new_end must be after new_start.")
        task = await self.repository.update_schedule(task_id, new_start, new_end)
        if not task:
            return ActionResult(success=False, message="Task not found.")
        return ActionResult(success=True, message="Task rescheduled.", task=task)

    async def _resolve_one_open_task(self, keyword_or_id: str, user_id: str) -> ActionResult:
        exact = await self.repository.get_task(keyword_or_id)
        if exact and exact.user_id == user_id:
            return ActionResult(success=True, message="Task resolved.", task=exact)

        candidates = await self.repository.search_open_tasks(keyword_or_id, user_id=user_id)
        if not candidates:
            return ActionResult(success=False, message="No matching open task found.")
        if len(candidates) > 1:
            return ActionResult(success=False, message="Multiple matching tasks found; use task id.", candidates=candidates)
        return ActionResult(success=True, message="Task resolved.", task=candidates[0])

    async def _list_existing_tasks(self, plan_date: date, user_id: str) -> list[Task]:
        try:
            return await self.repository.list_tasks_by_date(plan_date, user_id=user_id)
        except NotImplementedError:
            return []

    def _should_add_daily_review(self, existing_tasks: list[Task]) -> bool:
        if not self.scheduler.settings.auto_add_daily_review:
            return False
        return not any(self._is_active_daily_review(task) for task in existing_tasks)

    def _is_active_daily_review(self, task: Task) -> bool:
        return task.title.startswith("今日复盘") and task.status != TaskStatus.CANCELED
