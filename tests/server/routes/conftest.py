"""
Shared fixtures for server route tests.
The isolation (isolated_env) is now provided by tests/server/conftest.py.
This file only provides route-specific helpers: client, mock_workspace, session_id.
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client for the FastAPI app."""
    from flocks.server.app import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_workspace(tmp_path: Path) -> Path:
    """Patch WorkspaceManager root to a temp directory."""
    ws_root = tmp_path / "workspace"
    ws_root.mkdir()
    (ws_root / "README.md").write_text("# Test workspace\n")
    subdir = ws_root / "subdir"
    subdir.mkdir()
    (subdir / "file.txt").write_text("hello\n")

    from flocks.workspace.manager import WorkspaceManager

    original_instance = WorkspaceManager._instance
    manager = WorkspaceManager()
    manager._workspace_dir = ws_root
    manager._dirs_ensured = True
    WorkspaceManager._instance = manager

    yield ws_root

    WorkspaceManager._instance = original_instance


@pytest.fixture
async def session_id(client: AsyncClient) -> str:
    resp = await client.post("/api/session", json={"title": "fixture-session"})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]
