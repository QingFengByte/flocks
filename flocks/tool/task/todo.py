"""
Todo Tools - TODO list management

Provides tools for reading and writing TODO lists:
- todoread: Read current todo list
- todowrite: Update todo list with new items
"""

import json
from typing import List, Dict, Any, Optional
from enum import Enum

from flocks.tool.registry import (
    ToolRegistry, ToolCategory, ToolParameter, ParameterType, ToolResult, ToolContext
)
from flocks.utils.log import Log


log = Log.create(service="tool.todo")


# In-memory todo storage (per session)
# In production, this would be persisted to storage
_todo_storage: Dict[str, List[Dict[str, Any]]] = {}


class TodoStatus(str, Enum):
    """Todo item status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


TODOWRITE_DESCRIPTION = """Use this tool to create and manage a structured task list for your current SecOps session. This helps track progress, organize complex tasks, and demonstrate thoroughness.

When to Use This Tool:
1. Complex multi-step tasks (3+ distinct steps)
2. Non-trivial tasks requiring careful planning
3. User explicitly requests todo list
4. User provides multiple tasks

When NOT to Use:
1. Single, straightforward tasks
2. Trivial tasks with no organizational benefit
3. Tasks completable in < 3 trivial steps

Task States:
- pending: Not yet started
- in_progress: Currently working on
- completed: Finished successfully

Usage:
- Create specific, actionable items
- Break complex tasks into manageable steps
- Update status in real-time
- Mark complete IMMEDIATELY after finishing
- Only ONE task in_progress at a time"""


TODOREAD_DESCRIPTION = """Use this tool to read your current todo list.

Returns the current state of all todo items for this session."""


def get_todos(session_id: str) -> List[Dict[str, Any]]:
    """Get todos for a session"""
    return _todo_storage.get(session_id, [])


def set_todos(session_id: str, todos: List[Dict[str, Any]]) -> None:
    """Set todos for a session"""
    _todo_storage[session_id] = todos


@ToolRegistry.register_function(
    name="todowrite",
    description=TODOWRITE_DESCRIPTION,
    category=ToolCategory.SYSTEM,
    parameters=[
        ToolParameter(
            name="todos",
            type=ParameterType.ARRAY,
            description="Array of todo items with id, content, and status fields",
            required=True
        ),
    ]
)
async def todowrite_tool(
    ctx: ToolContext,
    todos: List[Dict[str, Any]],
) -> ToolResult:
    """
    Update the todo list
    
    Args:
        ctx: Tool context
        todos: List of todo items
        
    Returns:
        ToolResult with updated todos
    """
    # Request permission
    await ctx.ask(
        permission="todowrite",
        patterns=["*"],
        always=["*"],
        metadata={}
    )
    
    # Validate and normalize todos
    normalized_todos = []
    for todo in todos:
        # Ensure required fields
        if not isinstance(todo, dict):
            continue
        
        normalized = {
            "id": str(todo.get("id", len(normalized_todos) + 1)),
            "content": str(todo.get("content", "")),
            "status": todo.get("status", TodoStatus.PENDING.value)
        }
        
        # Validate status
        if normalized["status"] not in [s.value for s in TodoStatus]:
            normalized["status"] = TodoStatus.PENDING.value
        
        normalized_todos.append(normalized)
    
    # Store todos
    set_todos(ctx.session_id, normalized_todos)
    
    # Count pending todos
    pending_count = len([t for t in normalized_todos if t["status"] != TodoStatus.COMPLETED.value])
    
    return ToolResult(
        success=True,
        output=json.dumps(normalized_todos, indent=2),
        title=f"{pending_count} todos",
        metadata={
            "todos": normalized_todos
        }
    )


@ToolRegistry.register_function(
    name="todoread",
    description=TODOREAD_DESCRIPTION,
    category=ToolCategory.SYSTEM,
    parameters=[]
)
async def todoread_tool(
    ctx: ToolContext,
) -> ToolResult:
    """
    Read the current todo list
    
    Args:
        ctx: Tool context
        
    Returns:
        ToolResult with current todos
    """
    # Request permission
    await ctx.ask(
        permission="todoread",
        patterns=["*"],
        always=["*"],
        metadata={}
    )
    
    # Get todos
    todos = get_todos(ctx.session_id)
    
    # Count pending todos
    pending_count = len([t for t in todos if t.get("status") != TodoStatus.COMPLETED.value])
    
    return ToolResult(
        success=True,
        output=json.dumps(todos, indent=2),
        title=f"{pending_count} todos",
        metadata={
            "todos": todos
        }
    )
