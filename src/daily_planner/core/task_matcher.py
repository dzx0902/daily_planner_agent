from __future__ import annotations

from daily_planner.models.task import Task


def exact_id_match(tasks: list[Task], keyword_or_id: str) -> Task | None:
    return next((task for task in tasks if task.id == keyword_or_id), None)
