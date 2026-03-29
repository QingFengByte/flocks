"""
Task Store — SQLite persistence for Task Center

Manages two tables:
  - tasks: task definitions and state
  - task_execution_records: per-execution history for scheduled tasks
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite
from pydantic import BaseModel

from flocks.storage.storage import Storage
from flocks.utils.log import Log

from .models import (
    DeliveryStatus,
    Task,
    TaskExecutionRecord,
    TaskPriority,
    TaskStatus,
    TaskType,
)

log = Log.create(service="task.store")


class TaskStore:
    """SQLite-backed CRUD for tasks and execution records."""

    _initialized = False
    _conn: Optional[aiosqlite.Connection] = None

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    @classmethod
    async def init(cls) -> None:
        if cls._initialized:
            return
        await Storage._ensure_init()
        db_path = Storage._db_path
        cls._conn = await aiosqlite.connect(db_path)
        await cls._conn.executescript(_TASKS_DDL)
        for stmt in _INDEX_STMTS:
            try:
                await cls._conn.execute(stmt)
            except Exception:
                pass
        for stmt in _MIGRATION_STMTS:
            try:
                await cls._conn.execute(stmt)
            except Exception:
                pass  # column already exists
        await cls._conn.commit()
        cls._initialized = True
        log.info("task.store.initialized")

    @classmethod
    async def close(cls) -> None:
        if cls._conn:
            await cls._conn.close()
            cls._conn = None
            cls._initialized = False

    @classmethod
    async def _db(cls) -> aiosqlite.Connection:
        if not cls._conn:
            await cls.init()
        return cls._conn  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------

    @classmethod
    async def create_task(cls, task: Task) -> Optional[Task]:
        """Persist a new task.

        If the task has a ``dedup_key`` and an active task (PENDING / QUEUED /
        RUNNING, or FAILED-with-pending-retry) with the same key already
        exists, the insert is skipped and ``None`` is returned so the caller
        can detect the dedup.
        """
        if task.dedup_key:
            existing = await cls.get_active_by_dedup_key(task.dedup_key)
            if existing is not None:
                log.info("task.dedup_skipped", {
                    "dedup_key": task.dedup_key,
                    "title": task.title,
                    "existing_id": existing.id,
                })
                return None

        db = await cls._db()
        await db.execute(
            """INSERT INTO tasks
               (id, title, description, type, status, priority,
                source, schedule, execution, delivery_status,
                execution_mode, agent_name, workflow_id, skills, category,
                context, retry, tags, created_at, updated_at, created_by,
                dedup_key)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            cls._task_to_row(task),
        )
        await db.commit()
        log.info("task.created", {"id": task.id, "type": task.type.value})
        return task

    @classmethod
    async def get_task(cls, task_id: str) -> Optional[Task]:
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ) as cur:
            row = await cur.fetchone()
        return cls._row_to_task(row) if row else None

    @classmethod
    async def list_tasks(
        cls,
        *,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        priority: Optional[TaskPriority] = None,
        delivery_status: Optional[DeliveryStatus] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[List[Task], int]:
        """Return (items, total_count)."""
        where, params = cls._build_where(
            status=status,
            task_type=task_type,
            priority=priority,
            delivery_status=delivery_status,
        )
        allowed_sort = {"created_at", "updated_at", "priority"}
        col = sort_by if sort_by in allowed_sort else "created_at"
        direction = "ASC" if sort_order.lower() == "asc" else "DESC"

        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT COUNT(*) as cnt FROM tasks {where}", params
        ) as cur:
            total = (await cur.fetchone())["cnt"]
        async with db.execute(
            f"SELECT * FROM tasks {where} ORDER BY {col} {direction} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ) as cur:
            rows = await cur.fetchall()
        return [cls._row_to_task(r) for r in rows], total

    @classmethod
    async def update_task(cls, task: Task) -> Task:
        task.touch()
        db = await cls._db()
        await db.execute(
            """UPDATE tasks SET
                 title=?, description=?, status=?, priority=?,
                 source=?, schedule=?, execution=?, delivery_status=?,
                 execution_mode=?, agent_name=?, workflow_id=?,
                 skills=?, category=?,
                 context=?, retry=?, tags=?, updated_at=?, created_by=?,
                 dedup_key=?
               WHERE id=?""",
            (
                task.title,
                task.description,
                task.status.value,
                task.priority.value,
                _json(task.source),
                _json(task.schedule),
                _json(task.execution),
                task.delivery_status.value,
                task.execution_mode.value,
                task.agent_name,
                task.workflow_id,
                json.dumps(task.skills),
                task.category,
                _json(task.context),
                _json(task.retry),
                json.dumps(task.tags),
                task.updated_at.isoformat(),
                task.created_by,
                task.dedup_key,
                task.id,
            ),
        )
        await db.commit()
        return task

    @classmethod
    async def delete_task(cls, task_id: str) -> bool:
        db = await cls._db()
        cur = await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()
        return cur.rowcount > 0

    @classmethod
    async def batch_delete(cls, task_ids: List[str]) -> int:
        if not task_ids:
            return 0
        placeholders = ",".join("?" for _ in task_ids)
        db = await cls._db()
        cur = await db.execute(
            f"DELETE FROM tasks WHERE id IN ({placeholders})",
            tuple(task_ids),
        )
        await db.commit()
        return cur.rowcount

    @classmethod
    async def batch_update_status(
        cls, task_ids: List[str], status: TaskStatus
    ) -> int:
        if not task_ids:
            return 0
        placeholders = ",".join("?" for _ in task_ids)
        now = datetime.now(timezone.utc).isoformat()
        db = await cls._db()
        cur = await db.execute(
            f"UPDATE tasks SET status=?, updated_at=? WHERE id IN ({placeholders})",
            (status.value, now, *task_ids),
        )
        await db.commit()
        return cur.rowcount

    # ------------------------------------------------------------------
    # Execution Records (for scheduled tasks)
    # ------------------------------------------------------------------

    @classmethod
    async def create_record(cls, record: TaskExecutionRecord) -> TaskExecutionRecord:
        db = await cls._db()
        await db.execute(
            """INSERT INTO task_execution_records
               (id, task_id, status, started_at, completed_at,
                duration_ms, result_summary, error, session_id, delivery_status)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                record.id,
                record.task_id,
                record.status.value,
                record.started_at.isoformat() if record.started_at else None,
                record.completed_at.isoformat() if record.completed_at else None,
                record.duration_ms,
                record.result_summary,
                record.error,
                record.session_id,
                record.delivery_status.value,
            ),
        )
        await db.commit()
        return record

    @classmethod
    async def update_record(cls, record: TaskExecutionRecord) -> TaskExecutionRecord:
        db = await cls._db()
        await db.execute(
            """UPDATE task_execution_records SET
                 status=?, completed_at=?, duration_ms=?,
                 result_summary=?, error=?, session_id=?, delivery_status=?
               WHERE id=?""",
            (
                record.status.value,
                record.completed_at.isoformat() if record.completed_at else None,
                record.duration_ms,
                record.result_summary,
                record.error,
                record.session_id,
                record.delivery_status.value,
                record.id,
            ),
        )
        await db.commit()
        return record

    @classmethod
    async def list_records(
        cls, task_id: str, *, limit: int = 5, offset: int = 0
    ) -> tuple[List[TaskExecutionRecord], int]:
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM task_execution_records WHERE task_id=?",
            (task_id,),
        ) as cur:
            total = (await cur.fetchone())["cnt"]
        async with db.execute(
            "SELECT * FROM task_execution_records WHERE task_id=? "
            "ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (task_id, limit, offset),
        ) as cur:
            rows = await cur.fetchall()
        return [cls._row_to_record(r) for r in rows], total

    # ------------------------------------------------------------------
    # Dashboard helpers
    # ------------------------------------------------------------------

    @classmethod
    async def dashboard_counts(cls) -> Dict[str, Any]:
        from datetime import timedelta
        week_start = (
            datetime.now(timezone.utc) - timedelta(days=7)
        ).isoformat()
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        counts: Dict[str, Any] = {}
        for key, sql, params in (
            ("running", "SELECT COUNT(*) as c FROM tasks WHERE status='running'", ()),
            ("queued", "SELECT COUNT(*) as c FROM tasks WHERE status='queued'", ()),
            (
                "completed_week",
                "SELECT COUNT(*) as c FROM tasks WHERE status='completed' AND updated_at>=?",
                (week_start,),
            ),
            (
                "completed_unviewed",
                "SELECT COUNT(*) as c FROM tasks WHERE status='completed' AND delivery_status!='viewed'",
                (),
            ),
            (
                "failed_week",
                "SELECT COUNT(*) as c FROM tasks WHERE status='failed' AND updated_at>=?",
                (week_start,),
            ),
            (
                "scheduled_active",
                "SELECT COUNT(*) as c FROM tasks WHERE type='scheduled' AND status!='cancelled' AND json_extract(schedule, '$.enabled') = 1",
                (),
            ),
        ):
            async with db.execute(sql, params) as cur:
                counts[key] = (await cur.fetchone())["c"]
        return counts

    # ------------------------------------------------------------------
    # Queued task helpers (used by TaskQueue)
    # ------------------------------------------------------------------

    @classmethod
    async def dequeue_next(cls, *, exclude_ids: Optional[List[str]] = None) -> Optional[Task]:
        """Pick the highest-priority queued task (FIFO within same priority)."""
        excl = ""
        params: list = []
        if exclude_ids:
            placeholders = ",".join("?" for _ in exclude_ids)
            excl = f"AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)
        sql = f"""
            SELECT * FROM tasks
            WHERE status='queued' {excl}
            ORDER BY
              CASE priority
                WHEN 'urgent' THEN 1
                WHEN 'high'   THEN 2
                WHEN 'normal' THEN 3
                WHEN 'low'    THEN 4
              END,
              created_at ASC
            LIMIT 1
        """
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cur:
            row = await cur.fetchone()
        return cls._row_to_task(row) if row else None

    @classmethod
    async def count_running(cls) -> int:
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT COUNT(*) as c FROM tasks WHERE status='running'"
        ) as cur:
            return (await cur.fetchone())["c"]

    @classmethod
    async def get_unviewed_results(cls) -> List[Task]:
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tasks WHERE status='completed' AND delivery_status!='viewed' "
            "ORDER BY updated_at DESC"
        ) as cur:
            rows = await cur.fetchall()
        return [cls._row_to_task(r) for r in rows]

    @classmethod
    async def get_scheduled_tasks(cls, *, enabled_only: bool = True) -> List[Task]:
        where = "WHERE type='scheduled' AND status != 'cancelled'"
        if enabled_only:
            where += " AND json_extract(schedule, '$.enabled') = 1"
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(f"SELECT * FROM tasks {where}") as cur:
            rows = await cur.fetchall()
        return [cls._row_to_task(r) for r in rows]

    @classmethod
    async def get_active_by_dedup_key(cls, dedup_key: str) -> Optional[Task]:
        """Return the active task (PENDING/QUEUED/RUNNING or FAILED-with-retry)
        that holds the given dedup_key, or None."""
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM tasks
               WHERE dedup_key = ?
                 AND (status IN ('pending', 'queued', 'running')
                      OR (status = 'failed'
                          AND json_extract(retry, '$.retry_after') IS NOT NULL
                          AND json_extract(retry, '$.retry_count') < json_extract(retry, '$.max_retries')))
               LIMIT 1""",
            (dedup_key,),
        ) as cur:
            row = await cur.fetchone()
        return cls._row_to_task(row) if row else None

    @classmethod
    async def get_by_dedup_key(cls, dedup_key: str) -> Optional[Task]:
        """Return the most recent task with the given dedup_key regardless of
        status, or None if no such task has ever been created."""
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tasks WHERE dedup_key = ? ORDER BY created_at DESC LIMIT 1",
            (dedup_key,),
        ) as cur:
            row = await cur.fetchone()
        return cls._row_to_task(row) if row else None

    # ------------------------------------------------------------------
    # Startup-recovery / retry / expiry helpers
    # ------------------------------------------------------------------

    @classmethod
    async def list_by_status(cls, status: TaskStatus) -> List[Task]:
        """Return all tasks matching the given status (used for startup recovery)."""
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tasks WHERE status = ? AND type != 'scheduled'",
            (status.value,),
        ) as cur:
            rows = await cur.fetchall()
        return [cls._row_to_task(r) for r in rows]

    @classmethod
    async def list_retryable_failed(cls) -> List[Task]:
        """Return FAILED tasks whose retry_after timestamp has passed and that have
        remaining retry attempts."""
        now_iso = datetime.now(timezone.utc).isoformat()
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM tasks
               WHERE status = 'failed'
                 AND json_extract(retry, '$.retry_after') IS NOT NULL
                 AND json_extract(retry, '$.retry_after') <= ?
                 AND json_extract(retry, '$.retry_count') < json_extract(retry, '$.max_retries')""",
            (now_iso,),
        ) as cur:
            rows = await cur.fetchall()
        return [cls._row_to_task(r) for r in rows]

    @classmethod
    async def list_stale_queued(cls, before: datetime) -> List[Task]:
        """Return PENDING/QUEUED tasks whose last activity (updated_at) is older
        than *before*.  Using updated_at instead of created_at avoids
        accidentally expiring tasks that were recently re-queued by retry."""
        db = await cls._db()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM tasks
               WHERE status IN ('pending', 'queued')
                 AND updated_at < ?""",
            (before.isoformat(),),
        ) as cur:
            rows = await cur.fetchall()
        return [cls._row_to_task(r) for r in rows]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _task_to_row(cls, t: Task) -> tuple:
        return (
            t.id,
            t.title,
            t.description,
            t.type.value,
            t.status.value,
            t.priority.value,
            _json(t.source),
            _json(t.schedule),
            _json(t.execution),
            t.delivery_status.value,
            t.execution_mode.value,
            t.agent_name,
            t.workflow_id,
            json.dumps(t.skills),
            t.category,
            _json(t.context),
            _json(t.retry),
            json.dumps(t.tags),
            t.created_at.isoformat(),
            t.updated_at.isoformat(),
            t.created_by,
            t.dedup_key,
        )

    @classmethod
    def _row_to_task(cls, row: aiosqlite.Row) -> Task:
        d = dict(row)
        for col in ("source", "schedule", "execution", "context", "retry"):
            if d.get(col):
                d[col] = json.loads(d[col])
            elif col in ("context",):
                d[col] = {}
            else:
                d[col] = None
        for json_list_col in ("tags", "skills"):
            if d.get(json_list_col):
                d[json_list_col] = json.loads(d[json_list_col])
            else:
                d[json_list_col] = []
        # dedup_key is stored as plain TEXT; keep as-is (None if absent)
        d.setdefault("dedup_key", None)
        return Task(**d)

    @classmethod
    def _row_to_record(cls, row: aiosqlite.Row) -> TaskExecutionRecord:
        return TaskExecutionRecord(**dict(row))

    @classmethod
    def _build_where(
        cls,
        *,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        priority: Optional[TaskPriority] = None,
        delivery_status: Optional[DeliveryStatus] = None,
    ) -> tuple[str, tuple]:
        clauses: list[str] = []
        params: list = []
        if status:
            clauses.append("status = ?")
            params.append(status.value)
        elif task_type == TaskType.SCHEDULED:
            # Scheduled tasks that have been soft-deleted (CANCELLED) should not
            # appear in the list unless the caller explicitly filters by status.
            clauses.append("status != ?")
            params.append(TaskStatus.CANCELLED.value)
        if task_type:
            clauses.append("type = ?")
            params.append(task_type.value)
        if priority:
            clauses.append("priority = ?")
            params.append(priority.value)
        if delivery_status:
            clauses.append("delivery_status = ?")
            params.append(delivery_status.value)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return where, tuple(params)


# ======================================================================
# DDL
# ======================================================================

_TASKS_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    type            TEXT NOT NULL DEFAULT 'queued',
    status          TEXT NOT NULL DEFAULT 'pending',
    priority        TEXT NOT NULL DEFAULT 'normal',
    source          TEXT,            -- JSON
    schedule        TEXT,            -- JSON (scheduled tasks only)
    execution       TEXT,            -- JSON
    delivery_status TEXT NOT NULL DEFAULT 'unread',
    execution_mode  TEXT NOT NULL DEFAULT 'agent',
    agent_name      TEXT NOT NULL DEFAULT 'rex',
    workflow_id     TEXT,
    skills          TEXT DEFAULT '[]', -- JSON array
    category        TEXT,
    context         TEXT DEFAULT '{}', -- JSON
    retry           TEXT,            -- JSON
    tags            TEXT DEFAULT '[]', -- JSON array
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    created_by      TEXT NOT NULL DEFAULT 'rex',
    dedup_key       TEXT
);

CREATE TABLE IF NOT EXISTS task_execution_records (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running',
    started_at      TEXT,
    completed_at    TEXT,
    duration_ms     INTEGER,
    result_summary  TEXT,
    error           TEXT,
    session_id      TEXT,
    delivery_status TEXT NOT NULL DEFAULT 'unread',
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
"""

_INDEX_STMTS = [
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(type)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_delivery ON tasks(delivery_status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_dedup ON tasks(dedup_key)",
    "CREATE INDEX IF NOT EXISTS idx_texec_task ON task_execution_records(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_texec_started ON task_execution_records(started_at)",
]

# Migrations for tables created before these columns existed.
_MIGRATION_STMTS = [
    "ALTER TABLE tasks ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'agent'",
    "ALTER TABLE tasks ADD COLUMN agent_name TEXT NOT NULL DEFAULT 'rex'",
    "ALTER TABLE tasks ADD COLUMN workflow_id TEXT",
    "ALTER TABLE tasks ADD COLUMN skills TEXT DEFAULT '[]'",
    "ALTER TABLE tasks ADD COLUMN category TEXT",
    "ALTER TABLE tasks ADD COLUMN dedup_key TEXT",
]


def _json(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, BaseModel):
        return obj.model_dump_json()
    return json.dumps(obj)
