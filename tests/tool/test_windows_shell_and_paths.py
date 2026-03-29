"""
Tests for Windows shell selection and cross-drive path fallback behavior.
"""

from unittest.mock import AsyncMock

import pytest

from flocks.tool.code import bash as bash_module
from flocks.tool.file import apply_patch as apply_patch_module
from flocks.tool.file import edit as edit_module
from flocks.tool.file import write as write_module
from flocks.tool.registry import ToolContext, ToolResult


def _make_ctx(requests=None) -> ToolContext:
    """Create a minimal ToolContext that records permission requests."""

    async def _auto_approve(req):
        if requests is not None:
            requests.append(req)

    return ToolContext(
        session_id="test-session",
        message_id="msg-1",
        agent="test",
        call_id="call-1",
        permission_callback=_auto_approve,
    )


class _FakeProcess:
    stdout = None
    stderr = None
    returncode = 0


@pytest.mark.asyncio
async def test_execute_host_windows_uses_explicit_powershell(monkeypatch):
    """Windows host execution should use an explicit shell command."""
    ctx = _make_ctx()
    exec_calls = []
    shell_mock = AsyncMock()

    async def fake_exec(*args, **kwargs):
        exec_calls.append((args, kwargs))
        return _FakeProcess()

    async def fake_stream_output(**kwargs):
        return ToolResult(success=True, output="ok", metadata={})

    monkeypatch.setattr(bash_module.sys, "platform", "win32")
    monkeypatch.setattr(bash_module.Instance, "contains_path", lambda _path: True)
    monkeypatch.setattr(bash_module, "get_shell", lambda: "pwsh")
    monkeypatch.setattr(bash_module.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(bash_module.asyncio, "create_subprocess_shell", shell_mock)
    monkeypatch.setattr(bash_module, "_stream_output", fake_stream_output)

    result = await bash_module._execute_host(
        ctx=ctx,
        command="Write-Output 'hi'",
        cwd="/tmp",
        timeout_sec=1,
        timeout_ms=1000,
        description="powershell test",
    )

    assert result.success is True
    assert exec_calls == [
        (
            ("pwsh", "-NoProfile", "-NonInteractive", "-Command", "Write-Output 'hi'"),
            {
                "stdout": bash_module.asyncio.subprocess.PIPE,
                "stderr": bash_module.asyncio.subprocess.PIPE,
                "cwd": "/tmp",
                "env": {
                    **bash_module.os.environ,
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                },
            },
        )
    ]
    shell_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_host_unix_still_uses_subprocess_shell(monkeypatch):
    """Unix host execution should preserve the existing shell behavior."""
    ctx = _make_ctx()
    shell_calls = []
    exec_mock = AsyncMock()

    async def fake_shell(*args, **kwargs):
        shell_calls.append((args, kwargs))
        return _FakeProcess()

    async def fake_stream_output(**kwargs):
        return ToolResult(success=True, output="ok", metadata={})

    monkeypatch.setattr(bash_module.sys, "platform", "linux")
    monkeypatch.setattr(bash_module.Instance, "contains_path", lambda _path: True)
    monkeypatch.setattr(bash_module, "get_shell", lambda: "/bin/bash")
    monkeypatch.setattr(bash_module.asyncio, "create_subprocess_shell", fake_shell)
    monkeypatch.setattr(bash_module.asyncio, "create_subprocess_exec", exec_mock)
    monkeypatch.setattr(bash_module, "_stream_output", fake_stream_output)

    result = await bash_module._execute_host(
        ctx=ctx,
        command="echo hi",
        cwd="/tmp",
        timeout_sec=1,
        timeout_ms=1000,
        description="unix test",
    )

    assert result.success is True
    assert shell_calls == [
        (
            ("echo hi",),
            {
                "stdout": bash_module.asyncio.subprocess.PIPE,
                "stderr": bash_module.asyncio.subprocess.PIPE,
                "cwd": "/tmp",
                "start_new_session": True,
            },
        )
    ]
    exec_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_write_tool_uses_absolute_path_when_relpath_fails(tmp_path, monkeypatch):
    """Cross-drive relpath errors should fall back to the absolute path."""
    requests = []
    target = tmp_path / "cross-drive.txt"
    ctx = _make_ctx(requests)

    def fake_relpath(_path, _start):
        raise ValueError("path is on mount 'C:', start on mount 'D:'")

    monkeypatch.setattr(write_module.os.path, "relpath", fake_relpath)

    result = await write_module.write_tool(ctx=ctx, content="hello", filePath=str(target))

    assert result.success is True
    assert result.title == str(target)
    assert requests[-1].patterns == [str(target)]


def test_write_safe_relpath_keeps_relative_paths():
    """Normal relative path behavior should remain unchanged."""
    rel_path = write_module._safe_relpath("/tmp/project/file.txt", "/tmp/project")
    assert rel_path == "file.txt"


def test_edit_safe_relpath_falls_back_to_absolute(monkeypatch):
    """Edit helper should keep absolute paths on relpath failures."""

    def fake_relpath(_path, _start):
        raise ValueError("cross-drive")

    monkeypatch.setattr(edit_module.os.path, "relpath", fake_relpath)

    path = "C:\\Users\\Example\\file.txt"
    assert edit_module._safe_relpath(path, "D:\\workspace") == path


def test_apply_patch_safe_relpath_falls_back_to_absolute(monkeypatch):
    """Apply-patch helper should keep absolute paths on relpath failures."""

    def fake_relpath(_path, _start):
        raise ValueError("cross-drive")

    monkeypatch.setattr(apply_patch_module.os.path, "relpath", fake_relpath)

    path = "C:\\Users\\Example\\file.txt"
    assert apply_patch_module._safe_relpath(path, "D:\\workspace") == path
