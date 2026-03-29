"""
call_omo_agent tool - spawn explore/librarian subagents (Oh-My-Flocks parity).
"""

from typing import Optional

from flocks.tool.registry import (
    ToolRegistry,
    ToolCategory,
    ToolParameter,
    ParameterType,
    ToolResult,
    ToolContext,
)
from flocks.session.session import Session
from flocks.session.message import Message, MessageRole
from flocks.session.session_loop import SessionLoop
from flocks.task.background import get_background_manager, LaunchInput
from flocks.utils.log import Log

log = Log.create(service="tool.call_omo_agent")


ALLOWED_AGENTS = ["explore", "librarian"]


@ToolRegistry.register_function(
    name="call_omo_agent",
    description=(
        "Spawn explore/librarian agent. "
        "run_in_background defaults to false (sync). Set true for async with task_id. "
        "Pass session_id to continue a previous agent with full context."
    ),
    category=ToolCategory.SYSTEM,
    parameters=[
        ToolParameter(
            name="description",
            type=ParameterType.STRING,
            description="A short (3-5 words) description of the task",
            required=True,
        ),
        ToolParameter(
            name="prompt",
            type=ParameterType.STRING,
            description="The task for the agent to perform",
            required=True,
        ),
        ToolParameter(
            name="subagent_type",
            type=ParameterType.STRING,
            description="The type of specialized agent to use (explore or librarian)",
            required=True,
        ),
        ToolParameter(
            name="run_in_background",
            type=ParameterType.BOOLEAN,
            description="Optional. true=async (returns task_id), false=sync (waits). Defaults to false.",
            required=False,
        ),
        ToolParameter(
            name="session_id",
            type=ParameterType.STRING,
            description="Existing Task session to continue",
            required=False,
        ),
    ],
)
async def call_omo_agent_tool(
    ctx: ToolContext,
    description: str,
    prompt: str,
    subagent_type: str,
    run_in_background: Optional[bool] = False,
    session_id: Optional[str] = None,
) -> ToolResult:
    if not subagent_type:
        return ToolResult(success=False, error="subagent_type is required")
    normalized = subagent_type.lower()
    if normalized not in ALLOWED_AGENTS:
        return ToolResult(
            success=False,
            error=f'Invalid agent type "{subagent_type}". Only {", ".join(ALLOWED_AGENTS)} are allowed.',
        )
    if run_in_background is None:
        run_in_background = False

    await ctx.ask(
        permission="call_omo_agent",
        patterns=[normalized],
        always=["*"],
        metadata={"description": description, "subagent_type": normalized},
    )

    if run_in_background:
        if session_id:
            return ToolResult(
                success=False,
                error="session_id is not supported in background mode. Use run_in_background=false to continue.",
            )
        manager = get_background_manager()
        task = await manager.launch(
            LaunchInput(
                description=description,
                prompt=prompt,
                agent=normalized,
                parent_session_id=ctx.session_id,
                parent_message_id=ctx.message_id,
                parent_agent=ctx.agent,
            )
        )
        ctx.metadata({"title": description, "metadata": {"sessionId": task.session_id}})
        output = (
            "Background agent task launched successfully.\n\n"
            f"Task ID: {task.id}\n"
            f"Session ID: {task.session_id}\n"
            f"Description: {task.description}\n"
            f"Agent: {task.agent} (subagent)\n"
            f"Status: {task.status}\n\n"
            f'Use `background_output` with task_id="{task.id}" to check progress.'
        )
        return ToolResult(success=True, output=output, title=description, metadata={"sessionId": task.session_id})

    # Sync path
    if session_id:
        session = await Session.get_by_id(session_id)
        if not session:
            return ToolResult(success=False, error=f"Session {session_id} not found")
        target_session_id = session.id
    else:
        parent_session = await Session.get_by_id(ctx.session_id)
        if not parent_session:
            return ToolResult(success=False, error="Parent session not found")
        created = await Session.create(
            project_id=parent_session.project_id,
            directory=parent_session.directory,
            title=f"{description} (@{normalized} subagent)",
            parent_id=parent_session.id,
            permission=[{"permission": "question", "action": "deny", "pattern": "*"}],
            agent=normalized,
        )
        target_session_id = created.id

    await Message.create(
        session_id=target_session_id,
        role=MessageRole.USER,
        content=prompt,
        agent=normalized,
    )
    from flocks.session.session_loop import LoopCallbacks as _LoopCbs
    result = await SessionLoop.run(
        target_session_id,
        callbacks=_LoopCbs(event_publish_callback=ctx.event_publish_callback),
    )
    output_text = ""
    if result.last_message:
        output_text = await Message.get_text_content(result.last_message)
    ctx.metadata({"title": description, "metadata": {"sessionId": target_session_id}})
    output = (
        f"{output_text}\n\n<task_metadata>\n"
        f"session_id: {target_session_id}\n"
        "</task_metadata>"
    )
    return ToolResult(success=True, output=output, title=description, metadata={"sessionId": target_session_id})
