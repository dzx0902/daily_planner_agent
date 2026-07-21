from __future__ import annotations

from fastapi import APIRouter

from daily_planner.api.schemas import ApiResponse
from daily_planner.config import get_settings
from daily_planner.factory import build_repository, build_sync_service
from daily_planner.models.sync import SyncStatus

router = APIRouter()


@router.get("/sync/queue", response_model=ApiResponse)
async def sync_queue(status: SyncStatus | None = None) -> ApiResponse:
    repo = build_repository(get_settings())
    if not hasattr(repo, "list_sync_queue"):
        return ApiResponse(success=True, data=[])
    items = await repo.list_sync_queue(status)
    return ApiResponse(success=True, data=[item.model_dump(mode="json") for item in items])


@router.post("/sync/retry", response_model=ApiResponse)
async def sync_retry(limit: int = 10) -> ApiResponse:
    report = await build_sync_service().retry_failed(limit)
    return ApiResponse(success=True, data=report.__dict__)
