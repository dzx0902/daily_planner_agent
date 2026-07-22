from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

try:
    import asyncpg
except ImportError:  # SQLite-only development does not need the production driver installed.
    asyncpg = None

from daily_planner.models.sync import SyncMapping, SyncOperation, SyncQueueItem, SyncStatus
from daily_planner.models.task import Task, TaskStatus


class PostgresTaskRepository:
    """PostgreSQL implementation with the same public contract as SQLiteTaskRepository."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._ready = False

    async def _connect(self):
        if asyncpg is None:
            raise RuntimeError("PostgreSQL backend requires the asyncpg package.")
        return await asyncpg.connect(self.database_url)

    async def init(self) -> None:
        if self._ready:
            return
        conn = await self._connect()
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, plan_date DATE NOT NULL,
                    start TIMESTAMPTZ, "end" TIMESTAMPTZ, duration_minutes INTEGER NOT NULL, status TEXT NOT NULL,
                    priority TEXT NOT NULL, project TEXT, must_today BOOLEAN NOT NULL, source TEXT NOT NULL,
                    calendar_event_id TEXT, raw_input TEXT, result_note TEXT, notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_date_user ON tasks(plan_date, user_id);
                CREATE TABLE IF NOT EXISTS sync_mappings (
                    local_task_id TEXT NOT NULL, remote_provider TEXT NOT NULL, remote_id TEXT NOT NULL,
                    sync_status TEXT NOT NULL, last_synced_at TIMESTAMPTZ NOT NULL, last_error TEXT,
                    PRIMARY KEY(local_task_id, remote_provider)
                );
                CREATE TABLE IF NOT EXISTS sync_queue (
                    id TEXT PRIMARY KEY, local_task_id TEXT NOT NULL, remote_provider TEXT NOT NULL,
                    operation TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL,
                    last_error TEXT, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
                );
            """)
            self._ready = True
        finally:
            await conn.close()

    @staticmethod
    def _task(row: Any | None) -> Task | None:
        return Task(**dict(row)) if row else None

    async def create_task(self, task: Task) -> Task:
        await self.init(); conn = await self._connect()
        try:
            await conn.execute("""INSERT INTO tasks VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)""",
                task.id, task.user_id, task.title, task.plan_date, task.start, task.end, task.duration_minutes, task.status.value, task.priority.value, task.project, task.must_today, task.source, task.calendar_event_id, task.raw_input, task.result_note, task.notes, task.created_at, task.updated_at)
            return task
        finally: await conn.close()

    async def create_tasks(self, tasks: list[Task]) -> list[Task]:
        for task in tasks: await self.create_task(task)
        return tasks

    async def get_task(self, task_id: str) -> Task | None:
        await self.init(); conn = await self._connect()
        try: return self._task(await conn.fetchrow("SELECT * FROM tasks WHERE id=$1", task_id))
        finally: await conn.close()

    async def list_tasks_by_date(self, plan_date: date, status: TaskStatus | None = None, user_id: str = "default") -> list[Task]:
        await self.init(); conn = await self._connect()
        try:
            query = "SELECT * FROM tasks WHERE plan_date=$1 AND user_id=$2"; args: list[Any] = [plan_date, user_id]
            if status: query += " AND status=$3"; args.append(status.value)
            rows = await conn.fetch(query + ' ORDER BY start NULLS LAST, priority, created_at', *args)
            return [self._task(row) for row in rows if self._task(row)]
        finally: await conn.close()

    async def search_open_tasks(self, keyword: str, plan_date: date | None = None, user_id: str = "default") -> list[Task]:
        await self.init(); conn = await self._connect()
        try:
            query = "SELECT * FROM tasks WHERE user_id=$1 AND title ILIKE $2 AND status NOT IN ('Done','Canceled')"; args: list[Any] = [user_id, f"%{keyword}%"]
            if plan_date: query += " AND plan_date=$3"; args.append(plan_date)
            rows = await conn.fetch(query + " ORDER BY plan_date DESC, start NULLS LAST", *args)
            return [self._task(row) for row in rows if self._task(row)]
        finally: await conn.close()

    async def update_status(self, task_id: str, status: TaskStatus) -> Task | None:
        return await self._update(task_id, "status=$1", status.value)

    async def update_schedule(self, task_id: str, start: datetime, end: datetime) -> Task | None:
        await self.init(); conn = await self._connect()
        try: return self._task(await conn.fetchrow('UPDATE tasks SET start=$1, "end"=$2, updated_at=$3 WHERE id=$4 RETURNING *', start, end, datetime.now(), task_id))
        finally: await conn.close()

    async def _update(self, task_id: str, assignment: str, value: Any) -> Task | None:
        await self.init(); conn = await self._connect()
        try: return self._task(await conn.fetchrow(f"UPDATE tasks SET {assignment}, updated_at=$2 WHERE id=$3 RETURNING *", value, datetime.now(), task_id))
        finally: await conn.close()

    async def append_result_note(self, task_id: str, note: str) -> Task | None:
        task = await self.get_task(task_id)
        if not task: return None
        await self.init(); conn = await self._connect()
        try: return self._task(await conn.fetchrow("UPDATE tasks SET result_note=$1, updated_at=$2 WHERE id=$3 RETURNING *", f"{task.result_note}\n{note}" if task.result_note else note, datetime.now(), task_id))
        finally: await conn.close()

    async def list_tasks(self, plan_date: date | None = None, status: TaskStatus | None = None, user_id: str = "default") -> list[Task]:
        await self.init(); conn = await self._connect()
        try:
            query = "SELECT * FROM tasks WHERE user_id=$1"; args: list[Any] = [user_id]
            if plan_date: query += f" AND plan_date=${len(args)+1}"; args.append(plan_date)
            if status: query += f" AND status=${len(args)+1}"; args.append(status.value)
            rows = await conn.fetch(query + " ORDER BY plan_date, start NULLS LAST, priority", *args)
            return [self._task(row) for row in rows if self._task(row)]
        finally: await conn.close()

    async def archive_done_before(self, before_date: date, user_id: str = "default") -> int:
        await self.init(); conn = await self._connect()
        try: return int((await conn.execute("UPDATE tasks SET status='Canceled', updated_at=$1 WHERE user_id=$2 AND status='Done' AND plan_date<$3", datetime.now(), user_id, before_date)).split()[-1])
        finally: await conn.close()

    async def record_sync_mapping(self, mapping: SyncMapping) -> None:
        await self.init(); conn = await self._connect()
        try: await conn.execute("INSERT INTO sync_mappings VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(local_task_id,remote_provider) DO UPDATE SET remote_id=EXCLUDED.remote_id,sync_status=EXCLUDED.sync_status,last_synced_at=EXCLUDED.last_synced_at,last_error=EXCLUDED.last_error", mapping.local_task_id,mapping.remote_provider,mapping.remote_id,mapping.sync_status.value,mapping.last_synced_at,mapping.last_error)
        finally: await conn.close()

    async def get_sync_mapping(self, local_task_id: str, remote_provider: str) -> SyncMapping | None:
        await self.init(); conn = await self._connect()
        try:
            row = await conn.fetchrow("SELECT * FROM sync_mappings WHERE local_task_id=$1 AND remote_provider=$2",local_task_id,remote_provider)
            return SyncMapping(**dict(row)) if row else None
        finally: await conn.close()

    async def record_sync_failure(self, local_task_id: str, remote_provider: str, operation: SyncOperation, payload: str, error: str) -> SyncQueueItem:
        item = SyncQueueItem(local_task_id=local_task_id,remote_provider=remote_provider,operation=operation,payload=payload,status=SyncStatus.FAILED,attempts=1,last_error=error)
        await self.init(); conn = await self._connect()
        try: await conn.execute("INSERT INTO sync_queue VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",item.id,item.local_task_id,item.remote_provider,item.operation.value,item.payload,item.status.value,item.attempts,item.last_error,item.created_at,item.updated_at)
        finally: await conn.close()
        return item

    async def list_sync_queue(self, status: SyncStatus | None = None) -> list[SyncQueueItem]:
        await self.init(); conn = await self._connect()
        try:
            rows = await conn.fetch("SELECT * FROM sync_queue" + (" WHERE status=$1" if status else "") + " ORDER BY created_at", *( [status.value] if status else []))
            return [SyncQueueItem(**dict(row)) for row in rows]
        finally: await conn.close()

    async def get_sync_queue_item(self, item_id: str) -> SyncQueueItem | None:
        await self.init(); conn = await self._connect()
        try:
            row=await conn.fetchrow("SELECT * FROM sync_queue WHERE id=$1",item_id); return SyncQueueItem(**dict(row)) if row else None
        finally: await conn.close()

    async def update_sync_queue_item(self, item_id: str, status: SyncStatus, last_error: str | None = None, increment_attempts: bool = False) -> SyncQueueItem | None:
        await self.init(); conn = await self._connect()
        try:
            row=await conn.fetchrow("UPDATE sync_queue SET status=$1,last_error=$2,attempts=attempts+$3,updated_at=$4 WHERE id=$5 RETURNING *",status.value,last_error,1 if increment_attempts else 0,datetime.now(),item_id); return SyncQueueItem(**dict(row)) if row else None
        finally: await conn.close()
