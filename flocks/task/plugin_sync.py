"""
Task plugin DB synchronization helpers.
"""

from __future__ import annotations

from typing import Optional, Sequence

from flocks.utils.log import Log

from .plugin_models import TaskSpec

log = Log.create(service="task.plugin.sync")


async def upsert_task_specs(specs: Sequence[TaskSpec]) -> int:
    """Create or update built-in tasks from collected specs.

    Three-way logic based on DB state:

    1. No task with this dedup_key in DB → create a new PENDING task.
    2. Task exists and is active (PENDING/QUEUED/RUNNING) → update definition
       fields from YAML but preserve runtime state (status, enabled, next_run).
    3. Task exists but is terminal (CANCELLED/COMPLETED/FAILED) → the user
       intentionally dismissed it. Update definition fields but do NOT change
       the status — the task stays dismissed and won't be re-activated.
    """
    from flocks.task.models import (
        ExecutionMode,
        Task,
        TaskPriority,
        TaskSchedule,
        TaskSource,
        TaskStatus,
        TaskType,
    )
    from flocks.task.store import TaskStore

    await TaskStore.init()
    created = 0

    for spec in specs:
        schedule: Optional[TaskSchedule] = None
        if spec.task_type == "scheduled":
            if not spec.cron:
                log.warn("task.plugin.missing_cron", {"dedup_key": spec.dedup_key})
                continue
            schedule = TaskSchedule(
                cron=spec.cron,
                timezone=spec.timezone,
                cron_description=spec.cron_description,
                enabled=spec.enabled,
            )

        try:
            priority = TaskPriority(spec.priority)
        except ValueError:
            priority = TaskPriority.NORMAL

        try:
            exec_mode = ExecutionMode(spec.execution_mode)
        except ValueError:
            exec_mode = ExecutionMode.AGENT

        existing = await TaskStore.get_by_dedup_key(spec.dedup_key)
        if existing is not None:
            if existing.is_terminal:
                existing.title = spec.title
                existing.description = spec.description
                if existing.source is None:
                    existing.source = TaskSource(source_type="scheduled_trigger")
                existing.source.user_prompt = spec.user_prompt
                existing.context = spec.context
                existing.tags = spec.tags
                await TaskStore.update_task(existing)
                log.info("task.plugin.skip_dismissed", {
                    "dedup_key": spec.dedup_key,
                    "task_id": existing.id,
                    "status": existing.status.value,
                })
                continue

            existing.title = spec.title
            existing.description = spec.description
            existing.priority = priority
            existing.execution_mode = exec_mode
            existing.agent_name = spec.agent_name
            if existing.source is None:
                existing.source = TaskSource(source_type="scheduled_trigger")
            existing.source.user_prompt = spec.user_prompt
            existing.tags = spec.tags
            existing.context = spec.context
            if schedule and existing.schedule:
                existing.schedule.cron = schedule.cron
                existing.schedule.timezone = schedule.timezone
                existing.schedule.cron_description = schedule.cron_description
            elif schedule and not existing.schedule:
                existing.schedule = schedule
            await TaskStore.update_task(existing)
            log.info("task.plugin.updated", {
                "dedup_key": spec.dedup_key,
                "task_id": existing.id,
            })
            continue

        task = Task(
            title=spec.title,
            description=spec.description,
            type=TaskType(spec.task_type),
            status=TaskStatus.PENDING,
            priority=priority,
            execution_mode=exec_mode,
            agent_name=spec.agent_name,
            schedule=schedule,
            source=TaskSource(
                source_type="scheduled_trigger",
                user_prompt=spec.user_prompt,
            ),
            tags=spec.tags,
            context=spec.context,
            created_by="system",
            dedup_key=spec.dedup_key,
        )

        result = await TaskStore.create_task(task)
        if result is not None:
            created += 1
            log.info("task.plugin.created", {
                "dedup_key": spec.dedup_key,
                "title": task.title,
                "task_id": result.id,
            })
        else:
            log.info("task.plugin.dedup_by_store", {"dedup_key": spec.dedup_key})

    log.info("task.plugin.done", {"created": created, "total": len(specs)})
    return created
