"""Tests for bash tool error propagation."""

import pytest

from flocks.tool.code.bash import _stream_output
from flocks.tool.registry import ToolContext


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _size: int = -1) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class _FakeProcess:
    def __init__(self, *, stdout_chunks, stderr_chunks, returncode):
        self.stdout = _FakeStream(stdout_chunks)
        self.stderr = _FakeStream(stderr_chunks)
        self.returncode = returncode

    async def wait(self) -> int:
        return self.returncode


@pytest.mark.asyncio
async def test_stream_output_sets_error_from_captured_stderr() -> None:
    ctx = ToolContext(session_id="s-bash", message_id="m-bash")
    proc = _FakeProcess(
        stdout_chunks=[b""],
        stderr_chunks=[b"Navigation failed: net::ERR_CERT_AUTHORITY_INVALID\n"],
        returncode=1,
    )

    result = await _stream_output(
        ctx=ctx,
        proc=proc,
        command="agent-browser open https://example.com",
        timeout_sec=1,
        timeout_ms=1000,
        description="Open example",
    )

    assert result.success is False
    assert "Command failed with exit code 1" in result.error
    assert "ERR_CERT_AUTHORITY_INVALID" in result.error
    assert "ERR_CERT_AUTHORITY_INVALID" in result.output
    assert result.metadata["exit"] == 1
