from __future__ import annotations

from fastapi import APIRouter

from daily_planner.api.schemas import ApiResponse
from daily_planner.config import get_settings

router = APIRouter()


@router.get("/health", response_model=ApiResponse)
async def health() -> ApiResponse:
    settings = get_settings()
    return ApiResponse(success=True, data={"status": "ok", "backend": settings.task_backend, "timezone": settings.timezone})
