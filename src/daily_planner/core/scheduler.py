from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from daily_planner.config import Settings
from daily_planner.models.plan import ParsedPlan
from daily_planner.models.task import ParsedTask, Priority, Task, TaskSource, TimePreference


@dataclass(frozen=True)
class TimeRange:
    start: datetime
    end: datetime

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start < other.end and other.start < self.end


class Scheduler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def schedule(
        self,
        parsed_plan: ParsedPlan,
        raw_input: str,
        user_id: str = "default",
        include_daily_review: bool | None = None,
        existing_tasks: list[Task] | None = None,
    ) -> tuple[list[Task], list[Task]]:
        plan_date = parsed_plan.date
        parsed_tasks = list(parsed_plan.tasks)
        should_add_review = self.settings.auto_add_daily_review if include_daily_review is None else include_daily_review
        if should_add_review:
            parsed_tasks.append(
                ParsedTask(
                    title="今日复盘",
                    duration_minutes=self.settings.daily_review_duration,
                    priority=Priority.P2,
                )
            )
        scheduled: list[Task] = []
        unscheduled: list[Task] = []
        occupied = [*self._blocked_ranges(plan_date), *self._existing_task_ranges(existing_tasks or [])]

        for parsed in sorted(parsed_tasks, key=self._sort_key):
            parts = self._split(parsed)
            for index, part in enumerate(parts):
                title = parsed.title if len(parts) == 1 else f"{parsed.title} ({index + 1}/{len(parts)})"
                slot = self._find_slot(part, plan_date, occupied)
                task = self._to_task(part, title, plan_date, raw_input, user_id)
                if slot:
                    task.start = slot.start
                    task.end = slot.end
                    scheduled.append(task)
                    occupied.append(slot)
                else:
                    unscheduled.append(task)
        return scheduled, unscheduled

    def _sort_key(self, task: ParsedTask) -> tuple[int, int]:
        fixed = 0 if task.fixed_start else 1
        priority = {Priority.P0: 0, Priority.P1: 1, Priority.P2: 2}[task.priority]
        must = 0 if task.must_today else 1
        return (fixed, priority, must)

    def _split(self, task: ParsedTask) -> list[ParsedTask]:
        if task.duration_minutes <= 120:
            return [task]
        remaining = task.duration_minutes
        parts: list[ParsedTask] = []
        while remaining > 0:
            chunk = min(120, remaining)
            parts.append(task.model_copy(update={"duration_minutes": chunk, "fixed_start": None, "fixed_end": None}))
            remaining -= chunk
        return parts

    def _find_slot(self, task: ParsedTask, plan_date: date, occupied: list[TimeRange]) -> TimeRange | None:
        duration = timedelta(minutes=task.duration_minutes)
        if task.fixed_start:
            start = self._combine(plan_date, task.fixed_start)
            end = self._combine(plan_date, task.fixed_end) if task.fixed_end else start + duration
            candidate = TimeRange(start, end)
            return candidate if self._available(candidate, occupied) else None

        start_time, end_time = self._preference_window(task.time_preference)
        cursor = self._combine(plan_date, task.earliest_start or start_time)
        latest = self._combine(plan_date, task.latest_end or end_time)
        if cursor < self._combine(plan_date, start_time):
            cursor = self._combine(plan_date, start_time)

        while cursor + duration <= latest:
            candidate = TimeRange(cursor, cursor + duration)
            if self._available(candidate, occupied):
                return candidate
            cursor += timedelta(minutes=15)
        if task.time_preference != TimePreference.ANY:
            fallback = task.model_copy(update={"time_preference": TimePreference.ANY})
            return self._find_slot(fallback, plan_date, occupied)
        return None

    def _available(self, candidate: TimeRange, occupied: list[TimeRange]) -> bool:
        buffered = TimeRange(candidate.start - timedelta(minutes=10), candidate.end + timedelta(minutes=10))
        return not any(buffered.overlaps(item) for item in occupied)

    def _blocked_ranges(self, plan_date: date) -> list[TimeRange]:
        ranges: list[TimeRange] = []
        for item in self.settings.default_blocked_times.split(","):
            if not item.strip():
                continue
            start_text, end_text = item.split("-", 1)
            ranges.append(TimeRange(self._combine(plan_date, self._parse_time(start_text)), self._combine(plan_date, self._parse_time(end_text))))
        return ranges

    def _existing_task_ranges(self, tasks: list[Task]) -> list[TimeRange]:
        return [
            TimeRange(task.start, task.end)
            for task in tasks
            if task.start and task.end and task.status != "Canceled"
        ]

    def _preference_window(self, preference: TimePreference) -> tuple[time, time]:
        if preference == TimePreference.MORNING:
            return time(9), time(12)
        if preference == TimePreference.AFTERNOON:
            return time(13), time(18)
        if preference == TimePreference.EVENING:
            return time(19), self._parse_time(self.settings.default_day_end)
        return self._parse_time(self.settings.default_day_start), self._parse_time(self.settings.default_day_end)

    def _to_task(self, parsed: ParsedTask, title: str, plan_date: date, raw_input: str, user_id: str) -> Task:
        source = TaskSource.REVIEW.value if title.startswith("今日复盘") else TaskSource.AGENT.value
        return Task(
            user_id=user_id,
            title=title,
            plan_date=plan_date,
            duration_minutes=parsed.duration_minutes,
            priority=parsed.priority,
            project=parsed.project,
            must_today=parsed.must_today,
            source=source,
            raw_input=raw_input,
            notes=parsed.notes,
        )

    def _parse_time(self, value: str) -> time:
        hour, minute = value.strip().split(":", 1)
        return time(int(hour), int(minute))

    def _combine(self, plan_date: date, value: time) -> datetime:
        return datetime.combine(plan_date, value, tzinfo=self.settings.tzinfo)
