from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PLANNED = "Planned"
    DOING = "Doing"
    DONE = "Done"
    CANCELED = "Canceled"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class TaskSource(str, Enum):
    AGENT = "Agent"
    ASTRBOT = "AstrBot"
    FEISHU = "Feishu"
    OPENCLAW = "OpenClaw"
    MANUAL = "Manual"
    REVIEW = "Review"


class TimePreference(str, Enum):
    ANY = "any"
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


class ParsedTask(BaseModel):
    title: str
    duration_minutes: int = 90
    priority: Priority = Priority.P1
    project: str | None = None
    must_today: bool = False
    time_preference: TimePreference = TimePreference.ANY
    earliest_start: time | None = None
    latest_end: time | None = None
    fixed_start: time | None = None
    fixed_end: time | None = None
    notes: str | None = None


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str = "default"
    title: str
    plan_date: date
    start: datetime | None = None
    end: datetime | None = None
    duration_minutes: int = 90
    status: TaskStatus = TaskStatus.PLANNED
    priority: Priority = Priority.P1
    project: str | None = None
    must_today: bool = False
    source: str = TaskSource.AGENT.value
    calendar_event_id: str | None = None
    raw_input: str | None = None
    result_note: str | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def to_record(self) -> dict[str, Any]:
        data = self.model_dump()
        for key in ("plan_date", "start", "end", "created_at", "updated_at"):
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data

    @classmethod
    def from_record(cls, row: dict[str, Any]) -> "Task":
        data = dict(row)
        data["plan_date"] = date.fromisoformat(data["plan_date"])
        for key in ("start", "end", "created_at", "updated_at"):
            if data.get(key):
                data[key] = datetime.fromisoformat(data[key])
        data["must_today"] = bool(data.get("must_today"))
        return cls(**data)
