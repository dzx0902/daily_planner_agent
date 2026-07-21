from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class SyncStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class SyncOperation(str, Enum):
    CREATE = "create"
    UPDATE_STATUS = "update_status"
    UPDATE_SCHEDULE = "update_schedule"
    APPEND_NOTE = "append_note"


class SyncMapping(BaseModel):
    local_task_id: str
    remote_provider: str
    remote_id: str
    sync_status: SyncStatus = SyncStatus.SUCCESS
    last_synced_at: datetime = Field(default_factory=datetime.now)
    last_error: str | None = None


class SyncQueueItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    local_task_id: str
    remote_provider: str
    operation: SyncOperation
    payload: str
    status: SyncStatus = SyncStatus.PENDING
    attempts: int = 0
    last_error: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
