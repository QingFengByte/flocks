"""
Import CLI command

Imports session data from JSON file or URL
Ported from original cli/cmd/import.ts
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from flocks.session.session import SessionInfo
from flocks.session.message import MessageInfo, MessagePart
from flocks.project.project import Project
from flocks.storage.storage import Storage


import_app = typer.Typer(
    name="import",
    help="Import session data",
)

console = Console()


# Pattern for share URLs
SHARE_URL_PATTERN = re.compile(r"https?://(?:opncd\.ai|flocks\.ai)/share/([a-zA-Z0-9_-]+)")


@import_app.callback(invoke_without_command=True)
def import_session(
    file_or_url: str = typer.Argument(..., help="Path to JSON file or share URL"),
    project: Optional[str] = typer.Option(
        None, "-p", "--project",
        help="Project ID (uses current project if not specified)"
    ),
):
    """
    Import session data from JSON file or URL
    
    Supports:
    - Local JSON files exported with 'flocks export'
    - Share URLs (https://opncd.ai/share/<slug> or https://flocks.ai/share/<slug>)
    """
    asyncio.run(_import_session(file_or_url, project))


async def _import_session(file_or_url: str, project_id: Optional[str]):
    """Internal import implementation"""
    await Storage.init()
    
    # Get project
    if not project_id:
        result = await Project.from_directory(os.getcwd())
        project_id = result["project"].id
    
    export_data = None
    
    # Check if URL or file
    is_url = file_or_url.startswith("http://") or file_or_url.startswith("https://")
    
    if is_url:
        # Handle share URL
        match = SHARE_URL_PATTERN.match(file_or_url)
        if not match:
            console.print(f"[red]Invalid URL format. Expected: https://opncd.ai/share/<slug> or https://flocks.ai/share/<slug>[/red]")
            raise typer.Exit(1)
        
        slug = match.group(1)
        
        console.print(f"[dim]Fetching share data for {slug}...[/dim]")
        
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                # Try opncd.ai first
                response = await client.get(f"https://opncd.ai/api/share/{slug}")
                
                if response.status_code != 200:
                    # Try flocks.ai
                    response = await client.get(f"https://flocks.ai/api/share/{slug}")
                
                if response.status_code != 200:
                    console.print(f"[red]Failed to fetch share data: {response.status_code}[/red]")
                    raise typer.Exit(1)
                
                data = response.json()
                
                if not data.get("info") or not data.get("messages"):
                    console.print(f"[red]Share not found: {slug}[/red]")
                    raise typer.Exit(1)
                
                # Convert share format to export format
                export_data = {
                    "info": data["info"],
                    "messages": [
                        {
                            "info": {k: v for k, v in msg.items() if k != "parts"},
                            "parts": msg.get("parts", []),
                        }
                        for msg in data.get("messages", {}).values()
                    ],
                }
        
        except ImportError:
            console.print("[red]httpx is required for URL imports. Install with: pip install httpx[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Failed to fetch share data: {e}[/red]")
            raise typer.Exit(1)
    
    else:
        # Handle local file
        file_path = Path(file_or_url)
        
        if not file_path.exists():
            console.print(f"[red]File not found: {file_or_url}[/red]")
            raise typer.Exit(1)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                export_data = json.load(f)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON file: {e}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Failed to read file: {e}[/red]")
            raise typer.Exit(1)
    
    if not export_data:
        console.print("[red]Failed to read session data[/red]")
        raise typer.Exit(1)
    
    # Validate structure
    if "info" not in export_data:
        console.print("[red]Invalid export format: missing 'info' field[/red]")
        raise typer.Exit(1)
    
    if "messages" not in export_data:
        console.print("[red]Invalid export format: missing 'messages' field[/red]")
        raise typer.Exit(1)
    
    # Import session
    console.print("[dim]Importing session...[/dim]")
    
    try:
        session_info = export_data["info"]
        
        # Ensure project_id matches
        session_info["projectID"] = project_id
        
        # Store session
        session_key = f"session:{project_id}:{session_info['id']}"
        await Storage.set(session_key, session_info, "session")
        
        # Store messages
        message_count = 0
        for msg_data in export_data["messages"]:
            msg_info = msg_data.get("info", {})
            parts = msg_data.get("parts", [])
            
            # Store message
            msg_key = f"message:{session_info['id']}:{msg_info['id']}"
            await Storage.set(msg_key, msg_info, "message")
            
            # Store parts
            for part in parts:
                part_key = f"part:{msg_info['id']}:{part['id']}"
                await Storage.set(part_key, part, "part")
            
            message_count += 1
        
        console.print(f"[green]Imported session: {session_info['id']}[/green]")
        console.print(f"  Title: {session_info.get('title', 'Untitled')}")
        console.print(f"  Messages: {message_count}")
    
    except Exception as e:
        console.print(f"[red]Failed to import session: {e}[/red]")
        raise typer.Exit(1)
