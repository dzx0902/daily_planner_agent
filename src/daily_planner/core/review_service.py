from __future__ import annotations

from datetime import date

from daily_planner.models.task import Task, TaskStatus
from daily_planner.repositories.base import TaskRepository


class ReviewService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    async def create_daily_review(self, plan_date: date, user_id: str = "default") -> str:
        tasks = await self.repository.list_tasks_by_date(plan_date, user_id=user_id)
        total = len(tasks)
        done = len([task for task in tasks if task.status == TaskStatus.DONE])
        canceled = len([task for task in tasks if task.status == TaskStatus.CANCELED])
        planned = len([task for task in tasks if task.status == TaskStatus.PLANNED])
        p0_open = [task for task in tasks if task.priority == "P0" and task.status != TaskStatus.DONE]

        lines = [
            f"日期: {plan_date.isoformat()}",
            f"总任务: {total}",
            f"已完成: {done}",
            f"进行中/计划中: {planned}",
            f"已取消/归档: {canceled}",
        ]
        if total:
            lines.append(f"完成率: {done / total:.0%}")
        lines.append("未完成 P0: " + ("、".join(task.title for task in p0_open) if p0_open else "无"))
        note = "\n".join(lines)

        review_task = self._find_review_task(tasks)
        if review_task:
            await self.repository.append_result_note(review_task.id, note)
        return note

    def _find_review_task(self, tasks: list[Task]) -> Task | None:
        return next((task for task in tasks if task.title.startswith("今日复盘")), None)
