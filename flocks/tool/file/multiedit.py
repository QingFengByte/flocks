"""
MultiEdit Tool - Batch file edits

Performs multiple edit operations on a single file sequentially.
This is more efficient than calling edit multiple times.
"""

import os
from typing import List, Dict, Any, Optional

from flocks.tool.registry import (
    ToolRegistry, ToolCategory, ToolParameter, ParameterType, ToolResult, ToolContext
)
from flocks.tool.file.edit import edit_tool
from flocks.project.instance import Instance
from flocks.utils.log import Log


log = Log.create(service="tool.multiedit")


DESCRIPTION = """Performs multiple edit operations on a single file sequentially.

Usage:
- Use this when you need to make multiple changes to the same file
- Each edit is applied in order
- If any edit fails, subsequent edits are skipped
- More efficient than calling edit multiple times

Parameters:
- filePath: The file to edit
- edits: Array of edit operations, each with:
  - oldString: Text to replace
  - newString: Replacement text
  - replaceAll: (optional) Replace all occurrences"""


@ToolRegistry.register_function(
    name="multiedit",
    description=DESCRIPTION,
    category=ToolCategory.FILE,
    parameters=[
        ToolParameter(
            name="filePath",
            type=ParameterType.STRING,
            description="The absolute path to the file to modify",
            required=True
        ),
        ToolParameter(
            name="edits",
            type=ParameterType.ARRAY,
            description="Array of edit operations to perform sequentially",
            required=True
        ),
    ]
)
async def multiedit_tool(
    ctx: ToolContext,
    filePath: str,
    edits: List[Dict[str, Any]],
) -> ToolResult:
    """
    Perform multiple edits on a file
    
    Args:
        ctx: Tool context
        filePath: File to edit
        edits: List of edit operations
        
    Returns:
        ToolResult with combined results
    """
    if not filePath:
        return ToolResult(
            success=False,
            error="filePath is required"
        )
    
    if not edits:
        return ToolResult(
            success=False,
            error="At least one edit is required"
        )
    
    # Resolve path
    filepath = filePath
    if not os.path.isabs(filepath):
        base_dir = Instance.get_directory() or os.getcwd()
        filepath = os.path.join(base_dir, filepath)
    
    # Get relative title
    worktree = Instance.get_worktree() or os.getcwd()
    try:
        title = os.path.relpath(filepath, worktree)
    except ValueError:
        title = filepath
    
    results = []
    last_result = None
    
    for i, edit in enumerate(edits):
        if not isinstance(edit, dict):
            continue
        
        old_string = edit.get("oldString", "")
        new_string = edit.get("newString", "")
        replace_all = edit.get("replaceAll", False)
        
        try:
            result = await edit_tool(
                ctx,
                filePath=filepath,
                oldString=old_string,
                newString=new_string,
                replaceAll=replace_all
            )
            
            results.append({
                "index": i,
                "success": result.success,
                "metadata": result.metadata
            })
            
            last_result = result
            
            if not result.success:
                # Stop on first failure
                return ToolResult(
                    success=False,
                    error=f"Edit {i} failed: {result.error}",
                    title=title,
                    metadata={
                        "results": results,
                        "failedAt": i
                    }
                )
                
        except Exception as e:
            results.append({
                "index": i,
                "success": False,
                "error": str(e)
            })
            
            return ToolResult(
                success=False,
                error=f"Edit {i} failed: {str(e)}",
                title=title,
                metadata={
                    "results": results,
                    "failedAt": i
                }
            )
    
    return ToolResult(
        success=True,
        output=last_result.output if last_result else "All edits applied successfully.",
        title=title,
        metadata={
            "results": [r.get("metadata") for r in results if r.get("success")]
        }
    )
