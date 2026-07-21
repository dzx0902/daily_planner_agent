from __future__ import annotations

from datetime import date as dt_date, datetime
from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None


class PlanRequest(BaseModel):
    input: str
    date: dt_date | None = None
    user_id: str = "default"
    source: str = "api"


class ScheduleRequest(BaseModel):
    start: datetime
    end: datetime


class ReviewRequest(BaseModel):
    date: dt_date | None = None
    user_id: str = "default"
