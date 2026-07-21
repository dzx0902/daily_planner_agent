from __future__ import annotations

from fastapi import APIRouter

from daily_planner.api.schemas import ApiResponse
from daily_planner.config import get_settings
from daily_planner.repositories.notion import NotionTaskRepository

router = APIRouter()


@router.get("/integrations/notion/check", response_model=ApiResponse)
async def check_notion() -> ApiResponse:
    result = await NotionTaskRepository(get_settings()).check()
    return ApiResponse(success=result["ok"], data=result, error=None if result["ok"] else "; ".join(result["problems"]))
