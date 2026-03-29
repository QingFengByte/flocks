"""
Apply Patch Tool - Patch application

Applies unified diff patches to files.
Supports file add, update, delete, and move operations.
"""

import os
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from difflib import unified_diff

from flocks.tool.registry import (
    ToolRegistry, ToolCategory, ToolParameter, ParameterType, ToolResult, ToolContext
)
from flocks.project.instance import Instance
from flocks.utils.log import Log


log = Log.create(service="tool.apply_patch")


def _safe_relpath(path: str, start: Optional[str]) -> str:
    """Return a relative path when possible, otherwise keep the absolute path."""
    if not start:
        return path
    try:
        return os.path.relpath(path, start)
    except ValueError:
        return path


DESCRIPTION = """Apply a patch to modify files.

This tool is designed for advanced patch-based editing, supporting:
- File creation (add)
- File modification (update)
- File deletion (delete)
- File moves (update with move_path)

Patch format:
*** Begin Patch
*** Add File: path/to/new/file.py
content of new file
*** Update File: path/to/existing/file.py
@@@ ... @@@
-old line
+new line
*** Delete File: path/to/delete.py
*** End Patch

Use the edit tool for simple string replacements.
Use apply_patch for complex multi-file changes."""


@dataclass
class PatchChunk:
    """A chunk of changes within a file update"""
    start_line: int
    original_lines: List[str] = field(default_factory=list)
    new_lines: List[str] = field(default_factory=list)


@dataclass
class PatchHunk:
    """A hunk representing a single file operation"""
    path: str
    type: str  # "add", "update", "delete"
    contents: str = ""  # For add operations
    chunks: List[PatchChunk] = field(default_factory=list)  # For update operations
    move_path: Optional[str] = None  # For move operations


def parse_patch(patch_text: str) -> List[PatchHunk]:
    """
    Parse a patch text into hunks
    
    Args:
        patch_text: The patch text
        
    Returns:
        List of PatchHunk objects
    """
    hunks = []
    
    # Normalize line endings
    patch_text = patch_text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Check for empty patch
    if "*** Begin Patch" in patch_text and "*** End Patch" in patch_text:
        begin_idx = patch_text.find("*** Begin Patch")
        end_idx = patch_text.find("*** End Patch")
        patch_content = patch_text[begin_idx + len("*** Begin Patch"):end_idx].strip()
        
        if not patch_content:
            return []
    
    lines = patch_text.split("\n")
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Skip begin/end markers
        if line.startswith("*** Begin Patch") or line.startswith("*** End Patch"):
            i += 1
            continue
        
        # Add file
        if line.startswith("*** Add File:"):
            path = line[len("*** Add File:"):].strip()
            i += 1
            
            # Collect content until next marker
            content_lines = []
            while i < len(lines) and not lines[i].startswith("***"):
                content_lines.append(lines[i])
                i += 1
            
            hunks.append(PatchHunk(
                path=path,
                type="add",
                contents="\n".join(content_lines)
            ))
            continue
        
        # Update file
        if line.startswith("*** Update File:"):
            path = line[len("*** Update File:"):].strip()
            move_path = None
            
            # Check for move
            if " -> " in path:
                parts = path.split(" -> ")
                path = parts[0].strip()
                move_path = parts[1].strip()
            
            i += 1
            
            # Collect chunks until next file marker
            chunks = []
            while i < len(lines) and not lines[i].startswith("*** "):
                chunk_line = lines[i]
                
                # Parse chunk header @@ ... @@
                if chunk_line.startswith("@@@") or chunk_line.startswith("@@"):
                    # Parse line numbers
                    match = re.match(r'@@+\s*-(\d+)(?:,\d+)?\s*\+(\d+)(?:,\d+)?\s*@@+', chunk_line)
                    if match:
                        start_line = int(match.group(1))
                    else:
                        start_line = 1
                    
                    i += 1
                    
                    # Collect lines until next chunk or file
                    original_lines = []
                    new_lines = []
                    
                    while i < len(lines):
                        if lines[i].startswith("@@") or lines[i].startswith("*** "):
                            break
                        
                        if lines[i].startswith("-"):
                            original_lines.append(lines[i][1:])
                        elif lines[i].startswith("+"):
                            new_lines.append(lines[i][1:])
                        elif lines[i].startswith(" "):
                            original_lines.append(lines[i][1:])
                            new_lines.append(lines[i][1:])
                        else:
                            # Context line without prefix
                            original_lines.append(lines[i])
                            new_lines.append(lines[i])
                        
                        i += 1
                    
                    chunks.append(PatchChunk(
                        start_line=start_line,
                        original_lines=original_lines,
                        new_lines=new_lines
                    ))
                else:
                    i += 1
            
            hunks.append(PatchHunk(
                path=path,
                type="update",
                chunks=chunks,
                move_path=move_path
            ))
            continue
        
        # Delete file
        if line.startswith("*** Delete File:"):
            path = line[len("*** Delete File:"):].strip()
            hunks.append(PatchHunk(
                path=path,
                type="delete"
            ))
            i += 1
            continue
        
        i += 1
    
    return hunks


def apply_chunks(content: str, chunks: List[PatchChunk]) -> str:
    """
    Apply chunks to file content
    
    Args:
        content: Original file content
        chunks: List of changes to apply
        
    Returns:
        Modified content
    """
    if not chunks:
        return content
    
    lines = content.split("\n")
    
    # Apply chunks in reverse order to preserve line numbers
    for chunk in reversed(chunks):
        start_idx = chunk.start_line - 1
        
        # Find and replace the matching lines
        if start_idx >= 0 and start_idx < len(lines):
            # Remove original lines
            end_idx = start_idx + len(chunk.original_lines)
            del lines[start_idx:end_idx]
            
            # Insert new lines
            for i, new_line in enumerate(chunk.new_lines):
                lines.insert(start_idx + i, new_line)
    
    return "\n".join(lines)


def generate_diff(filepath: str, old_content: str, new_content: str) -> str:
    """Generate unified diff"""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    diff_lines = list(unified_diff(
        old_lines,
        new_lines,
        fromfile=filepath,
        tofile=filepath
    ))
    
    return "".join(diff_lines)


@ToolRegistry.register_function(
    name="apply_patch",
    description=DESCRIPTION,
    category=ToolCategory.FILE,
    parameters=[
        ToolParameter(
            name="patchText",
            type=ParameterType.STRING,
            description="The full patch text that describes all changes to be made",
            required=True
        ),
    ]
)
async def apply_patch_tool(
    ctx: ToolContext,
    patchText: str,
) -> ToolResult:
    """
    Apply a patch to files
    
    Args:
        ctx: Tool context
        patchText: Patch text to apply
        
    Returns:
        ToolResult with applied changes
    """
    if not patchText:
        return ToolResult(
            success=False,
            error="patchText is required"
        )
    
    # Parse patch
    try:
        hunks = parse_patch(patchText)
    except Exception as e:
        return ToolResult(
            success=False,
            error=f"Failed to parse patch: {str(e)}"
        )
    
    if not hunks:
        return ToolResult(
            success=False,
            error="No valid hunks found in patch"
        )
    
    # Resolve base directory
    base_dir = Instance.get_directory() or os.getcwd()
    worktree = Instance.get_worktree() or os.getcwd()
    
    # Process hunks and collect changes
    file_changes: List[Dict[str, Any]] = []
    total_diff = ""
    
    for hunk in hunks:
        filepath = os.path.join(base_dir, hunk.path)
        
        try:
            if hunk.type == "add":
                old_content = ""
                new_content = hunk.contents if hunk.contents.endswith("\n") or not hunk.contents else hunk.contents + "\n"
                diff = generate_diff(filepath, old_content, new_content)
                
                file_changes.append({
                    "filePath": filepath,
                    "oldContent": old_content,
                    "newContent": new_content,
                    "type": "add",
                    "diff": diff,
                    "additions": new_content.count("\n") + 1,
                    "deletions": 0
                })
                total_diff += diff + "\n"
                
            elif hunk.type == "update":
                if not os.path.exists(filepath):
                    return ToolResult(
                        success=False,
                        error=f"File not found for update: {filepath}"
                    )
                
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    old_content = f.read()
                
                new_content = apply_chunks(old_content, hunk.chunks)
                diff = generate_diff(filepath, old_content, new_content)
                
                change_type = "move" if hunk.move_path else "update"
                move_filepath = os.path.join(base_dir, hunk.move_path) if hunk.move_path else None
                
                file_changes.append({
                    "filePath": filepath,
                    "oldContent": old_content,
                    "newContent": new_content,
                    "type": change_type,
                    "movePath": move_filepath,
                    "diff": diff,
                    "additions": sum(1 for line in new_content.split("\n") if line not in old_content.split("\n")),
                    "deletions": sum(1 for line in old_content.split("\n") if line not in new_content.split("\n"))
                })
                total_diff += diff + "\n"
                
            elif hunk.type == "delete":
                if not os.path.exists(filepath):
                    return ToolResult(
                        success=False,
                        error=f"File not found for deletion: {filepath}"
                    )
                
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    old_content = f.read()
                
                diff = generate_diff(filepath, old_content, "")
                
                file_changes.append({
                    "filePath": filepath,
                    "oldContent": old_content,
                    "newContent": "",
                    "type": "delete",
                    "diff": diff,
                    "additions": 0,
                    "deletions": old_content.count("\n") + 1
                })
                total_diff += diff + "\n"
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to process hunk for {hunk.path}: {str(e)}"
            )
    
    # Request permission
    await ctx.ask(
        permission="edit",
        patterns=[_safe_relpath(c["filePath"], worktree) for c in file_changes],
        always=["*"],
        metadata={"diff": total_diff}
    )
    
    # Apply changes
    changed_files = []
    
    for change in file_changes:
        filepath = change["filePath"]
        
        try:
            if change["type"] == "add":
                # Create parent directory
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(change["newContent"])
                changed_files.append(filepath)
                
            elif change["type"] == "update":
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(change["newContent"])
                changed_files.append(filepath)
                
            elif change["type"] == "move":
                move_path = change["movePath"]
                os.makedirs(os.path.dirname(move_path), exist_ok=True)
                with open(move_path, 'w', encoding='utf-8') as f:
                    f.write(change["newContent"])
                os.remove(filepath)
                changed_files.append(move_path)
                
            elif change["type"] == "delete":
                os.remove(filepath)
                changed_files.append(filepath)
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to apply change to {filepath}: {str(e)}"
            )
    
    # Build summary
    summary_lines = []
    for change in file_changes:
        rel_path = _safe_relpath(change.get("movePath") or change["filePath"], worktree)
        if change["type"] == "add":
            summary_lines.append(f"A {rel_path}")
        elif change["type"] == "delete":
            summary_lines.append(f"D {rel_path}")
        else:
            summary_lines.append(f"M {rel_path}")
    
    output = f"Success. Updated the following files:\n" + "\n".join(summary_lines)
    
    return ToolResult(
        success=True,
        output=output,
        title=output,
        metadata={
            "diff": total_diff,
            "files": file_changes
        }
    )
