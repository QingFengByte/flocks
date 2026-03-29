"""
Task Center CLI commands

Provides: flocks task [dashboard|list|show|create|queue|scheduled|cancel|retry]
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from flocks.storage.storage import Storage

task_app = typer.Typer(
    name="task",
    help="Task Center — manage queued and scheduled tasks",
    invoke_without_command=True,
)

console = Console()


# ------------------------------------------------------------------
# Default: dashboard
# ------------------------------------------------------------------

@task_app.callback(invoke_without_command=True)
def task_default(ctx: typer.Context):
    """Show task dashboard (default when no subcommand given)."""
    if ctx.invoked_subcommand is None:
        asyncio.run(_dashboard())


@task_app.command("dashboard")
def task_dashboard():
    """Show task center overview."""
    asyncio.run(_dashboard())


async def _dashboard():
    await Storage.init()
    from flocks.task.manager import TaskManager
    from flocks.task.store import TaskStore
    await TaskStore.init()

    counts = await TaskManager.dashboard()

    panel_lines = [
        f"🟢 Running:             {counts.get('running', 0)}",
        f"📋 Queued:              {counts.get('queued', 0)}",
        f"✅ Completed (7d):      {counts.get('completed_week', 0)}",
        f"🔔 Unviewed results:    {counts.get('completed_unviewed', 0)}",
        f"❌ Failed (7d):         {counts.get('failed_week', 0)}",
        f"⏰ Scheduled (active):  {counts.get('scheduled_active', 0)}",
        f"⏸️  Queue paused:        {counts.get('queue_paused', False)}",
    ]

    console.print(Panel("\n".join(panel_lines), title="📋 Task Center", border_style="cyan"))

    unviewed = await TaskManager.get_unviewed_results()
    if unviewed:
        console.print()
        console.print("[bold]Unviewed completed tasks:[/bold]")
        for t in unviewed[:5]:
            console.print(f"  🔔 {t.id}  {t.title}")


# ------------------------------------------------------------------
# list
# ------------------------------------------------------------------

@task_app.command("list")
def task_list(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    task_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type (queued/scheduled/stream)"),
    limit: int = typer.Option(20, "-n", "--limit", help="Max results"),
    format: str = typer.Option("table", "--format", help="Output format: table | json"),
):
    """List tasks."""
    asyncio.run(_list_tasks(status, task_type, limit, format))


async def _list_tasks(status_val, type_val, limit, fmt):
    await Storage.init()
    from flocks.task.manager import TaskManager
    from flocks.task.models import TaskStatus, TaskType
    from flocks.task.store import TaskStore
    await TaskStore.init()

    tasks, total = await TaskManager.list_tasks(
        status=TaskStatus(status_val) if status_val else None,
        task_type=TaskType(type_val) if type_val else None,
        limit=limit,
    )

    if fmt == "json":
        console.print(json.dumps([t.model_dump(mode="json") for t in tasks], indent=2, default=str))
        return

    table = Table(title=f"Tasks ({total} total)", show_header=True, header_style="bold cyan")
    table.add_column("Status", width=8)
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Type", width=10)
    table.add_column("Mode", width=10)
    table.add_column("Priority", width=8)
    table.add_column("Created")

    status_icon = {
        "pending": "⏳", "queued": "📋", "running": "🟢",
        "completed": "✅", "failed": "❌", "cancelled": "🚫",
        "paused": "⏸️", "stopped": "🛑",
    }
    for t in tasks:
        icon = status_icon.get(t.status.value, "·")
        created = _relative_time(t.created_at)
        mode = t.execution_mode.value if t.execution_mode else "-"
        table.add_row(icon, t.id[:16], t.title, t.type.value, mode, t.priority.value, created)

    console.print(table)


# ------------------------------------------------------------------
# show
# ------------------------------------------------------------------

@task_app.command("show")
def task_show(task_id: str = typer.Argument(..., help="Task ID")):
    """Show task details."""
    asyncio.run(_show_task(task_id))


async def _show_task(task_id: str):
    await Storage.init()
    from flocks.task.manager import TaskManager
    from flocks.task.store import TaskStore
    await TaskStore.init()

    task = await TaskManager.get_task(task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found[/red]")
        raise typer.Exit(1)

    lines = [
        f"[bold]{task.title}[/bold]",
        f"ID:       {task.id}",
        f"Type:     {task.type.value}",
        f"Status:   {task.status.value}",
        f"Priority: {task.priority.value}",
        f"Mode:     {task.execution_mode.value}",
    ]
    if task.execution_mode.value == "agent":
        lines.append(f"Agent:    {task.agent_name}")
    if task.workflow_id:
        lines.append(f"Workflow: {task.workflow_id}")
    if task.skills:
        lines.append(f"Skills:   {', '.join(task.skills)}")
    if task.category:
        lines.append(f"Category: {task.category}")
    lines.append(f"Created:  {task.created_at.isoformat()}")
    if task.description:
        lines.append(f"Desc:     {task.description}")
    if task.schedule:
        lines.append(f"Cron:     {task.schedule.cron} ({task.schedule.timezone})")
        if task.schedule.next_run:
            lines.append(f"Next run: {task.schedule.next_run.isoformat()}")
    if task.execution:
        if task.execution.started_at:
            lines.append(f"Started:  {task.execution.started_at.isoformat()}")
        if task.execution.completed_at:
            lines.append(f"Finished: {task.execution.completed_at.isoformat()}")
        if task.execution.duration_ms is not None:
            lines.append(f"Duration: {_fmt_duration(task.execution.duration_ms)}")
        if task.execution.result_summary:
            lines.append(f"\n[bold]Result:[/bold]\n{task.execution.result_summary}")
        if task.execution.error:
            lines.append(f"\n[red]Error:[/red] {task.execution.error}")

    console.print(Panel("\n".join(lines), border_style="cyan"))


# ------------------------------------------------------------------
# create
# ------------------------------------------------------------------

@task_app.command("create")
def task_create(
    title: str = typer.Argument(..., help="Task title"),
    description: str = typer.Option("", "--desc", "-d", help="Task description"),
    task_type: str = typer.Option("queued", "--type", "-t", help="queued | scheduled | stream"),
    priority: str = typer.Option("normal", "--priority", "-p", help="urgent | high | normal | low"),
    mode: str = typer.Option("agent", "--mode", "-m", help="agent | workflow"),
    agent: str = typer.Option("rex", "--agent", "-a", help="Agent name (for agent mode)"),
    workflow: Optional[str] = typer.Option(None, "--workflow", "-w", help="Workflow ID (for workflow mode)"),
    skill: Optional[list[str]] = typer.Option(None, "--skill", help="Skills to inject"),
    cron: Optional[str] = typer.Option(None, "--cron", help="Cron expression (for scheduled type)"),
    prompt: Optional[str] = typer.Option(None, "--prompt", help="User prompt"),
):
    """Create a new task."""
    asyncio.run(_create_task(title, description, task_type, priority, mode, agent, workflow, skill or [], cron, prompt))


async def _create_task(title, description, task_type, priority, mode, agent, workflow, skills, cron, prompt):
    await Storage.init()
    from flocks.task.manager import TaskManager
    from flocks.task.models import ExecutionMode, TaskPriority, TaskSchedule, TaskSource, TaskType
    from flocks.task.store import TaskStore
    await TaskStore.init()

    schedule = None
    if task_type == "scheduled":
        if not cron:
            console.print("[red]--cron is required for scheduled tasks[/red]")
            raise typer.Exit(1)
        schedule = TaskSchedule(cron=cron)

    source = TaskSource(user_prompt=prompt) if prompt else None

    task = await TaskManager.create_task(
        title=title,
        description=description,
        task_type=TaskType(task_type),
        priority=TaskPriority(priority),
        source=source,
        schedule=schedule,
        execution_mode=ExecutionMode(mode),
        agent_name=agent,
        workflow_id=workflow,
        skills=skills,
    )
    console.print(f"[green]✅ Created:[/green] {task.id}  {task.title}")


# ------------------------------------------------------------------
# queue
# ------------------------------------------------------------------

@task_app.command("queue")
def task_queue(
    pause: bool = typer.Option(False, "--pause", help="Pause queue"),
    resume: bool = typer.Option(False, "--resume", help="Resume queue"),
):
    """View or control the task queue."""
    asyncio.run(_queue(pause, resume))


async def _queue(pause: bool, resume: bool):
    await Storage.init()
    from flocks.task.manager import TaskManager
    from flocks.task.store import TaskStore
    await TaskStore.init()

    if pause:
        TaskManager.pause_queue()
        console.print("[yellow]Queue paused[/yellow]")
        return
    if resume:
        TaskManager.resume_queue()
        console.print("[green]Queue resumed[/green]")
        return

    qs = await TaskManager.queue_status()
    console.print(Panel(
        f"Paused:         {qs['paused']}\n"
        f"Max concurrent: {qs['max_concurrent']}\n"
        f"Running:        {qs['running']}\n"
        f"Queued:         {qs['queued']}",
        title="📋 Queue Status",
        border_style="cyan",
    ))


# ------------------------------------------------------------------
# scheduled
# ------------------------------------------------------------------

@task_app.command("scheduled")
def task_scheduled():
    """List all scheduled (cron) tasks."""
    asyncio.run(_scheduled())


async def _scheduled():
    await Storage.init()
    from flocks.task.manager import TaskManager
    from flocks.task.store import TaskStore
    await TaskStore.init()

    tasks = await TaskManager.list_scheduled()
    if not tasks:
        console.print("[dim]No scheduled tasks[/dim]")
        return

    table = Table(title="Scheduled Tasks", show_header=True, header_style="bold cyan")
    table.add_column("Status", width=8)
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Cron")
    table.add_column("Next Run")

    for t in tasks:
        enabled = "✅" if (t.schedule and t.schedule.enabled) else "⏸️"
        cron = t.schedule.cron if t.schedule else "-"
        next_run = t.schedule.next_run.isoformat() if (t.schedule and t.schedule.next_run) else "-"
        table.add_row(enabled, t.id[:16], t.title, cron, next_run)

    console.print(table)


# ------------------------------------------------------------------
# cancel / retry
# ------------------------------------------------------------------

@task_app.command("cancel")
def task_cancel(task_id: str = typer.Argument(..., help="Task ID")):
    """Cancel a task."""
    asyncio.run(_cancel(task_id))


async def _cancel(task_id: str):
    await Storage.init()
    from flocks.task.manager import TaskManager
    from flocks.task.store import TaskStore
    await TaskStore.init()

    task = await TaskManager.cancel_task(task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✅ Cancelled:[/green] {task.title}")


@task_app.command("retry")
def task_retry(task_id: str = typer.Argument(..., help="Task ID")):
    """Retry a failed task."""
    asyncio.run(_retry(task_id))


async def _retry(task_id: str):
    await Storage.init()
    from flocks.task.manager import TaskManager
    from flocks.task.store import TaskStore
    await TaskStore.init()

    task = await TaskManager.retry_task(task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found or not failed[/red]")
        raise typer.Exit(1)
    console.print(f"[green]🔄 Retrying:[/green] {task.title}")


@task_app.command("rerun")
def task_rerun(task_id: str = typer.Argument(..., help="Task ID")):
    """Rerun a task (stop if running, requeue)."""
    asyncio.run(_rerun(task_id))


async def _rerun(task_id: str):
    await Storage.init()
    from flocks.task.manager import TaskManager
    from flocks.task.store import TaskStore
    await TaskStore.init()

    task = await TaskManager.rerun_task(task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found[/red]")
        raise typer.Exit(1)
    console.print(f"[green]🔄 Rerunning:[/green] {task.title}")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _relative_time(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _fmt_duration(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    secs = ms / 1000
    if secs < 60:
        return f"{secs:.1f}s"
    mins = int(secs // 60)
    remaining = secs - mins * 60
    return f"{mins}m {remaining:.0f}s"
