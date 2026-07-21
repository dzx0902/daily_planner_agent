from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from daily_planner.models.task import Task, TaskStatus
from daily_planner.models.sync import SyncMapping, SyncOperation, SyncQueueItem, SyncStatus
from daily_planner.repositories.base import TaskRepository


class SQLiteTaskRepository(TaskRepository):
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    async def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    plan_date TEXT NOT NULL,
                    start TEXT,
                    end TEXT,
                    duration_minutes INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    project TEXT,
                    must_today INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    calendar_event_id TEXT,
                    raw_input TEXT,
                    result_note TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_mappings (
                    local_task_id TEXT NOT NULL,
                    remote_provider TEXT NOT NULL,
                    remote_id TEXT NOT NULL,
                    sync_status TEXT NOT NULL,
                    last_synced_at TEXT NOT NULL,
                    last_error TEXT,
                    PRIMARY KEY (local_task_id, remote_provider)
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_queue (
                    id TEXT PRIMARY KEY,
                    local_task_id TEXT NOT NULL,
                    remote_provider TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.commit()

    async def create_task(self, task: Task) -> Task:
        await self.init()
        data = task.to_record()
        data["must_today"] = int(task.must_today)
        columns = ", ".join(data.keys())
        placeholders = ", ".join([f":{key}" for key in data.keys()])
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"INSERT INTO tasks ({columns}) VALUES ({placeholders})", data)
            await db.commit()
        return task

    async def get_task(self, task_id: str) -> Task | None:
        await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
        return self._task_from_row(row)

    async def list_tasks_by_date(
        self,
        plan_date: date,
        status: TaskStatus | None = None,
        user_id: str = "default",
    ) -> list[Task]:
        await self.init()
        params: list[Any] = [plan_date.isoformat(), user_id]
        query = "SELECT * FROM tasks WHERE plan_date = ? AND user_id = ?"
        if status:
            query += " AND status = ?"
            params.append(status.value)
        query += " ORDER BY COALESCE(start, '9999'), priority, created_at"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
        return [task for row in rows if (task := self._task_from_row(row))]

    async def search_open_tasks(
        self,
        keyword: str,
        plan_date: date | None = None,
        user_id: str = "default",
    ) -> list[Task]:
        await self.init()
        params: list[Any] = [user_id, f"%{keyword}%"]
        query = """
            SELECT * FROM tasks
            WHERE user_id = ? AND title LIKE ?
              AND status NOT IN ('Done', 'Canceled')
        """
        if plan_date:
            query += " AND plan_date = ?"
            params.append(plan_date.isoformat())
        query += " ORDER BY plan_date DESC, COALESCE(start, '9999')"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
        return [task for row in rows if (task := self._task_from_row(row))]

    async def update_status(self, task_id: str, status: TaskStatus) -> Task | None:
        await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, datetime.now().isoformat(), task_id),
            )
            await db.commit()
        return await self.get_task(task_id)

    async def update_schedule(self, task_id: str, start: datetime, end: datetime) -> Task | None:
        await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET start = ?, end = ?, updated_at = ? WHERE id = ?",
                (start.isoformat(), end.isoformat(), datetime.now().isoformat(), task_id),
            )
            await db.commit()
        return await self.get_task(task_id)

    async def append_result_note(self, task_id: str, note: str) -> Task | None:
        existing = await self.get_task(task_id)
        if not existing:
            return None
        combined = f"{existing.result_note}\n{note}" if existing.result_note else note
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET result_note = ?, updated_at = ? WHERE id = ?",
                (combined, datetime.now().isoformat(), task_id),
            )
            await db.commit()
        return await self.get_task(task_id)

    async def list_tasks(
        self,
        plan_date: date | None = None,
        status: TaskStatus | None = None,
        user_id: str = "default",
    ) -> list[Task]:
        await self.init()
        params: list[Any] = [user_id]
        query = "SELECT * FROM tasks WHERE user_id = ?"
        if plan_date:
            query += " AND plan_date = ?"
            params.append(plan_date.isoformat())
        if status:
            query += " AND status = ?"
            params.append(status.value)
        query += " ORDER BY plan_date, COALESCE(start, '9999'), priority, created_at"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
        return [task for row in rows if (task := self._task_from_row(row))]

    async def archive_done_before(self, before_date: date, user_id: str = "default") -> int:
        await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?
                WHERE user_id = ? AND status = ? AND plan_date < ?
                """,
                (TaskStatus.CANCELED.value, datetime.now().isoformat(), user_id, TaskStatus.DONE.value, before_date.isoformat()),
            )
            await db.commit()
            return cursor.rowcount

    async def record_sync_mapping(self, mapping: SyncMapping) -> None:
        await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO sync_mappings (
                    local_task_id, remote_provider, remote_id, sync_status, last_synced_at, last_error
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(local_task_id, remote_provider) DO UPDATE SET
                    remote_id = excluded.remote_id,
                    sync_status = excluded.sync_status,
                    last_synced_at = excluded.last_synced_at,
                    last_error = excluded.last_error
                """,
                (
                    mapping.local_task_id,
                    mapping.remote_provider,
                    mapping.remote_id,
                    mapping.sync_status.value,
                    mapping.last_synced_at.isoformat(),
                    mapping.last_error,
                ),
            )
            await db.commit()

    async def get_sync_mapping(self, local_task_id: str, remote_provider: str) -> SyncMapping | None:
        await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM sync_mappings WHERE local_task_id = ? AND remote_provider = ?",
                (local_task_id, remote_provider),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["last_synced_at"] = datetime.fromisoformat(data["last_synced_at"])
        return SyncMapping(**data)

    async def record_sync_failure(
        self,
        local_task_id: str,
        remote_provider: str,
        operation: SyncOperation,
        payload: str,
        error: str,
    ) -> SyncQueueItem:
        await self.init()
        item = SyncQueueItem(
            local_task_id=local_task_id,
            remote_provider=remote_provider,
            operation=operation,
            payload=payload,
            status=SyncStatus.FAILED,
            attempts=1,
            last_error=error,
        )
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO sync_queue (
                    id, local_task_id, remote_provider, operation, payload, status,
                    attempts, last_error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.local_task_id,
                    item.remote_provider,
                    item.operation.value,
                    item.payload,
                    item.status.value,
                    item.attempts,
                    item.last_error,
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                ),
            )
            await db.commit()
        return item

    async def list_sync_queue(self, status: SyncStatus | None = None) -> list[SyncQueueItem]:
        await self.init()
        params: list[Any] = []
        query = "SELECT * FROM sync_queue"
        if status:
            query += " WHERE status = ?"
            params.append(status.value)
        query += " ORDER BY created_at"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
        return [self._sync_item_from_row(row) for row in rows]

    async def get_sync_queue_item(self, item_id: str) -> SyncQueueItem | None:
        await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM sync_queue WHERE id = ?", (item_id,))
            row = await cursor.fetchone()
        return self._sync_item_from_row(row) if row else None

    async def update_sync_queue_item(
        self,
        item_id: str,
        status: SyncStatus,
        last_error: str | None = None,
        increment_attempts: bool = False,
    ) -> SyncQueueItem | None:
        await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE sync_queue
                SET status = ?,
                    last_error = ?,
                    attempts = attempts + ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (status.value, last_error, 1 if increment_attempts else 0, datetime.now().isoformat(), item_id),
            )
            await db.commit()
        return await self.get_sync_queue_item(item_id)

    def _task_from_row(self, row: aiosqlite.Row | None) -> Task | None:
        if row is None:
            return None
        return Task.from_record(dict(row))

    def _sync_item_from_row(self, row: aiosqlite.Row) -> SyncQueueItem:
        data = dict(row)
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return SyncQueueItem(**data)
