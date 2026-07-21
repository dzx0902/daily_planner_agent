from datetime import date, time

from daily_planner.config import Settings
from daily_planner.core.scheduler import Scheduler
from daily_planner.models.plan import ParsedPlan
from daily_planner.models.task import ParsedTask, Priority


def test_p0_schedules_before_p1_and_avoids_blocked_time():
    scheduler = Scheduler(Settings(auto_add_daily_review=False))
    parsed = ParsedPlan(
        date=date(2026, 7, 12),
        tasks=[
            ParsedTask(title="普通任务", duration_minutes=60, priority=Priority.P1),
            ParsedTask(title="必须任务", duration_minutes=60, priority=Priority.P0, must_today=True),
        ],
    )

    scheduled, unscheduled = scheduler.schedule(parsed, "raw")

    assert not unscheduled
    assert scheduled[0].title == "必须任务"
    for task in scheduled:
        assert not (task.start.time() < time(13, 0) and task.end.time() > time(12, 0))


def test_after_20_not_before_20():
    scheduler = Scheduler(Settings(auto_add_daily_review=False))
    parsed = ParsedPlan(
        date=date(2026, 7, 12),
        tasks=[ParsedTask(title="报名", duration_minutes=30, earliest_start=time(20, 0))],
    )

    scheduled, _ = scheduler.schedule(parsed, "raw")

    assert scheduled[0].start.time() >= time(20, 0)


def test_unscheduled_when_time_is_not_enough():
    scheduler = Scheduler(Settings(default_day_start="09:00", default_day_end="10:00", default_blocked_times="", auto_add_daily_review=False))
    parsed = ParsedPlan(date=date(2026, 7, 12), tasks=[ParsedTask(title="长任务", duration_minutes=120)])

    scheduled, unscheduled = scheduler.schedule(parsed, "raw")

    assert scheduled == []
    assert len(unscheduled) == 1


def test_timezone_is_applied_to_scheduled_datetimes():
    scheduler = Scheduler(Settings(timezone="Asia/Shanghai", auto_add_daily_review=False))
    parsed = ParsedPlan(date=date(2026, 7, 12), tasks=[ParsedTask(title="任务", duration_minutes=30)])

    scheduled, _ = scheduler.schedule(parsed, "raw")

    assert scheduled[0].start.utcoffset().total_seconds() == 8 * 3600
