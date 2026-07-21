from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, Field

from daily_planner.models.task import ParsedTask


class BlockedTime(BaseModel):
    start: time
    end: time


class ParsedPlan(BaseModel):
    date: date
    tasks: list[ParsedTask] = Field(default_factory=list)
    blocked_times: list[BlockedTime] = Field(default_factory=list)
    preferences: dict[str, str] = Field(default_factory=dict)
