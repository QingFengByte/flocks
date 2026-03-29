"""
Priority Task Queue

Database-backed priority queue with concurrency control.
Queue state is derived from tasks with status='queued' in SQLite,
so no extra in-memory state is needed.
"""

import asyncio
from typing import List, Optional

from flocks.utils.log import Log

from .models import Task, TaskStatus
from .store import TaskStore

log = Log.create(service="task.queue")


class TaskQueue:
    """Priority queue with concurrency control."""

    def __init__(self, max_concurrent: int = 1):
        self.max_concurrent = max_concurrent
        self._paused = False
        self._running_ids: set[str] = set()
        self._lock = asyncio.Lock()

    @property
    def paused(self) -> bool:
        return self._paused

    async def enqueue(self, task: Task) -> Task:
        task.status = TaskStatus.QUEUED
        task.touch()
        task = await TaskStore.update_task(task)
        log.info("queue.enqueued", {"id": task.id, "priority": task.priority.value})
        return task

    async def dequeue(self) -> Optional[Task]:
        """Pick the next task to run, respecting concurrency and pause."""
        async with self._lock:
            if self._paused:
                return None
            running = await TaskStore.count_running()
            if running >= self.max_concurrent:
                return None
            task = await TaskStore.dequeue_next(
                exclude_ids=list(self._running_ids)
            )
            if task:
                self._running_ids.add(task.id)
            return task

    def mark_started(self, task_id: str) -> None:
        self._running_ids.add(task_id)

    def mark_finished(self, task_id: str) -> None:
        self._running_ids.discard(task_id)

    async def pending_count(self) -> int:
        _, total = await TaskStore.list_tasks(
            status=TaskStatus.QUEUED, limit=0, offset=0
        )
        return total

    def pause(self) -> None:
        self._paused = True
        log.info("queue.paused")

    def resume(self) -> None:
        self._paused = False
        log.info("queue.resumed")

    async def status(self) -> dict:
        running = await TaskStore.count_running()
        pending = await self.pending_count()
        return {
            "paused": self._paused,
            "max_concurrent": self.max_concurrent,
            "running": running,
            "queued": pending,
        }
