"""
List Tool - Directory listing

Lists files and directories in a given path with:
- Common directory filtering (node_modules, .git, etc.)
- Custom ignore patterns
- Tree-style output
- File count limiting
"""

import os
import asyncio
import shutil
from pathlib import Path
from typing import Optional, List, Set, Dict, AsyncIterator

from flocks.tool.registry import (
    ToolRegistry, ToolCategory, ToolParameter, ParameterType, ToolResult, ToolContext
)
from flocks.project.instance import Instance
from flocks.utils.log import Log


log = Log.create(service="tool.list")


# Default ignore patterns matching Flocks
IGNORE_PATTERNS = [
    "node_modules/",
    "__pycache__/",
    ".git/",
    "dist/",
    "build/",
    "target/",
    "vendor/",
    "bin/",
    "obj/",
    ".idea/",
    ".vscode/",
    ".zig-cache/",
    "zig-out",
    ".coverage",
    "coverage/",
    "tmp/",
    "temp/",
    ".cache/",
    "cache/",
    "logs/",
    ".venv/",
    "venv/",
    "env/",
]

# Maximum number of files to list
LIMIT = 100


# Description matching Flocks' ls.txt
DESCRIPTION = """Lists files and directories in a given path. The path parameter must be absolute; omit it to use the current workspace directory. You can optionally provide an array of glob patterns to ignore with the ignore parameter. You should generally prefer the Glob and Grep tools, if you know which directories to search."""


def find_ripgrep() -> Optional[str]:
    """Find ripgrep executable"""
    for name in ['rg', 'ripgrep']:
        path = shutil.which(name)
        if path:
            return path
    return None


def should_ignore(filepath: str, ignore_patterns: List[str]) -> bool:
    """
    Check if file should be ignored based on patterns
    
    Args:
        filepath: Relative file path
        ignore_patterns: List of ignore patterns
        
    Returns:
        True if file should be ignored
    """
    import fnmatch
    
    for pattern in ignore_patterns:
        # Handle directory patterns (ending with /)
        if pattern.endswith('/'):
            dir_pattern = pattern.rstrip('/')
            parts = filepath.split(os.sep)
            if dir_pattern in parts:
                return True
        else:
            if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(os.path.basename(filepath), pattern):
                return True
    
    return False


async def ripgrep_files(
    rg_path: str,
    cwd: str,
    ignore_globs: List[str]
) -> AsyncIterator[str]:
    """
    Find files using ripgrep with ignore patterns
    
    Args:
        rg_path: Path to ripgrep
        cwd: Working directory
        ignore_globs: Glob patterns to ignore
        
    Yields:
        File paths relative to cwd
    """
    args = [
        rg_path,
        "--files",
        "--hidden",
        "--follow",
        "--no-messages"
    ]
    
    for pattern in ignore_globs:
        args.extend(["--glob", pattern])
    
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd
    )
    
    async for line in proc.stdout:
        filepath = line.decode('utf-8', errors='replace').strip()
        if filepath:
            yield filepath
    
    await proc.wait()


def fallback_list(
    cwd: str,
    ignore_patterns: List[str],
    limit: int
) -> List[str]:
    """
    Fallback directory listing using os.walk
    
    Args:
        cwd: Working directory
        ignore_patterns: Patterns to ignore
        limit: Maximum files to return
        
    Returns:
        List of file paths
    """
    files = []
    
    # Convert ignore patterns to directory names to skip
    ignore_dirs = set()
    for pattern in ignore_patterns:
        if pattern.endswith('/'):
            ignore_dirs.add(pattern.rstrip('/'))
        elif pattern.endswith('*'):
            # Handle patterns like "node_modules/*"
            parts = pattern.split('/')
            if len(parts) >= 1:
                ignore_dirs.add(parts[0])
    
    for root, dirs, filenames in os.walk(cwd):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        
        for filename in filenames:
            if len(files) >= limit:
                return files
            
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, cwd)
            
            if not should_ignore(rel_path, ignore_patterns):
                files.append(rel_path)
    
    return files


def render_directory_tree(files: List[str], base_path: str) -> str:
    """
    Render files as a directory tree
    
    Args:
        files: List of relative file paths
        base_path: Base directory path
        
    Returns:
        Tree-style string representation
    """
    # Build directory structure
    dirs: Set[str] = set()
    files_by_dir: Dict[str, List[str]] = {}
    
    for filepath in files:
        dirname = os.path.dirname(filepath)
        parts = dirname.split(os.sep) if dirname and dirname != "." else []
        
        # Add all parent directories
        for i in range(len(parts) + 1):
            dir_path = os.sep.join(parts[:i]) if i > 0 else "."
            dirs.add(dir_path)
        
        # Add file to its directory
        if dirname not in files_by_dir:
            files_by_dir[dirname] = []
        files_by_dir[dirname].append(os.path.basename(filepath))
    
    def render_dir(dir_path: str, depth: int) -> str:
        indent = "  " * depth
        output = ""
        
        if depth > 0:
            output += f"{indent}{os.path.basename(dir_path)}/\n"
        
        child_indent = "  " * (depth + 1)
        
        # Get child directories
        children = sorted([
            d for d in dirs
            if os.path.dirname(d) == dir_path and d != dir_path
        ])
        
        # Render subdirectories first
        for child in children:
            output += render_dir(child, depth + 1)
        
        # Render files
        dir_files = files_by_dir.get(dir_path if dir_path != "." else "", [])
        for filename in sorted(dir_files):
            output += f"{child_indent}{filename}\n"
        
        return output
    
    return f"{base_path}/\n" + render_dir(".", 0)


@ToolRegistry.register_function(
    name="list",
    description=DESCRIPTION,
    category=ToolCategory.FILE,
    parameters=[
        ToolParameter(
            name="path",
            type=ParameterType.STRING,
            description="The absolute path to the directory to list (must be absolute, not relative)",
            required=False
        ),
        ToolParameter(
            name="ignore",
            type=ParameterType.ARRAY,
            description="List of glob patterns to ignore",
            required=False
        ),
    ]
)
async def list_tool(
    ctx: ToolContext,
    path: Optional[str] = None,
    ignore: Optional[List[str]] = None,
) -> ToolResult:
    """
    List files in a directory
    
    Args:
        ctx: Tool context
        path: Directory to list
        ignore: Additional ignore patterns
        
    Returns:
        ToolResult with directory listing
    """
    # Resolve search path
    base_dir = Instance.get_directory() or os.getcwd()
    search_path = os.path.join(base_dir, path or ".")
    
    if not os.path.isabs(search_path):
        search_path = os.path.abspath(search_path)
    
    # Request permission
    await ctx.ask(
        permission="list",
        patterns=[search_path],
        always=["*"],
        metadata={
            "path": search_path
        }
    )
    
    # Build ignore globs
    ignore_globs = [f"!{p}*" for p in IGNORE_PATTERNS]
    if ignore:
        ignore_globs.extend([f"!{p}" for p in ignore])
    
    # Get relative title
    worktree = Instance.get_worktree() or os.getcwd()
    try:
        title = os.path.relpath(search_path, worktree)
    except ValueError:
        title = search_path
    
    # Find files
    rg_path = find_ripgrep()
    files: List[str] = []
    
    try:
        if rg_path:
            async for filepath in ripgrep_files(rg_path, search_path, ignore_globs):
                files.append(filepath)
                if len(files) >= LIMIT:
                    break
        else:
            log.warn("list.ripgrep_not_found", {"fallback": "os_walk"})
            files = fallback_list(search_path, IGNORE_PATTERNS + (ignore or []), LIMIT)
            
    except Exception as e:
        return ToolResult(
            success=False,
            error=f"Directory listing failed: {str(e)}",
            title=title
        )
    
    truncated = len(files) >= LIMIT
    
    # Build output
    output = render_directory_tree(files, search_path)
    
    return ToolResult(
        success=True,
        output=output,
        title=title,
        truncated=truncated,
        metadata={
            "count": len(files),
            "truncated": truncated
        }
    )
