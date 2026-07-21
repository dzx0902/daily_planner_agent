from __future__ import annotations

from fastapi import APIRouter

from daily_planner.api.schemas import ApiResponse, PlanRequest
from daily_planner.factory import build_service

router = APIRouter()


@router.post("/plans", response_model=ApiResponse)
async def create_plan(request: PlanRequest) -> ApiResponse:
    result = await build_service().create_plan(request.input, request.date, request.user_id)
    return ApiResponse(success=result.success, data=result.model_dump(mode="json"), error=None if result.success else result.message)
