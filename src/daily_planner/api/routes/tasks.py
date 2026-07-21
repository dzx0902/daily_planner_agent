from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from daily_planner.api.schemas import ApiResponse, ReviewRequest, ScheduleRequest
from daily_planner.factory import build_review_service, build_service
from daily_planner.config import get_settings
from daily_planner.factory import build_repository
from daily_planner.models.task import TaskStatus

router = APIRouter()


@router.get("/tasks/today", response_model=ApiResponse)
async def today(user_id: str = "default") -> ApiResponse:
    tasks = await build_service().get_today_tasks(user_id)
    return ApiResponse(success=True, data=[task.model_dump(mode="json") for task in tasks])


@router.get("/tasks", response_model=ApiResponse)
async def list_tasks(plan_date: date = Query(default_factory=date.today), user_id: str = "default") -> ApiResponse:
    repo = build_repository(get_settings())
    tasks = await repo.list_tasks_by_date(plan_date, user_id=user_id)
    return ApiResponse(success=True, data=[task.model_dump(mode="json") for task in tasks])


@router.post("/tasks/{task_id}/done", response_model=ApiResponse)
async def done(task_id: str, user_id: str = "default") -> ApiResponse:
    result = await build_service().mark_done(task_id, user_id)
    return ApiResponse(success=result.success, data=result.model_dump(mode="json"), error=None if result.success else result.message)


@router.post("/tasks/{task_id}/cancel", response_model=ApiResponse)
async def cancel(task_id: str, user_id: str = "default") -> ApiResponse:
    result = await build_service().cancel_task(task_id, user_id)
    return ApiResponse(success=result.success, data=result.model_dump(mode="json"), error=None if result.success else result.message)


@router.post("/tasks/archive-done", response_model=ApiResponse)
async def archive_done(before: date | None = None, user_id: str = "default") -> ApiResponse:
    result = await build_service().archive_done(before, user_id)
    return ApiResponse(success=result.success, data=result.model_dump(mode="json"), error=None if result.success else result.message)


@router.patch("/tasks/{task_id}/schedule", response_model=ApiResponse)
async def reschedule(task_id: str, request: ScheduleRequest) -> ApiResponse:
    result = await build_service().reschedule_task(task_id, request.start, request.end)
    return ApiResponse(success=result.success, data=result.model_dump(mode="json"), error=None if result.success else result.message)


@router.post("/review", response_model=ApiResponse)
async def review(request: ReviewRequest) -> ApiResponse:
    plan_date = request.date or date.today()
    note = await build_review_service().create_daily_review(plan_date, request.user_id)
    return ApiResponse(success=True, data={"review": note})
