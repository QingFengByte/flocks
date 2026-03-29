"""
Tests for MCP Client SSE transport support

Verifies that McpClient correctly handles:
- remote / sse server type (auto-detect: Streamable HTTP -> SSE fallback)
- Timeout does NOT fall back (avoids double wait)
- Unknown server types (raises ValueError)
- Error message extraction from ExceptionGroups
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from flocks.mcp.client import McpClient, _extract_root_cause


class TestMcpClientServerTypes:
    """Test McpClient server type routing"""

    def test_init_sse_type(self):
        """SSE type should be accepted"""
        client = McpClient(
            name="test-sse",
            server_type="sse",
            url="https://example.com/sse",
        )
        assert client.server_type == "sse"
        assert client.url == "https://example.com/sse"

    def test_init_remote_type(self):
        """Remote type should be accepted"""
        client = McpClient(
            name="test-remote",
            server_type="remote",
            url="https://example.com/mcp",
        )
        assert client.server_type == "remote"

    @pytest.mark.asyncio
    async def test_unknown_type_raises_value_error(self):
        """Unknown server type should raise ValueError"""
        client = McpClient(
            name="test-bad",
            server_type="websocket",
            url="wss://example.com",
        )
        with pytest.raises(ValueError, match="Unknown server type: websocket"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_sse_type_uses_auto_detect(self):
        """SSE type should use _connect_remote (auto-detect) same as remote"""
        client = McpClient(
            name="test",
            server_type="sse",
            url="https://example.com/sse",
        )
        client._connect_remote = AsyncMock()
        await client.connect()
        client._connect_remote.assert_called_once()

    @pytest.mark.asyncio
    async def test_remote_type_calls_connect_remote(self):
        """Remote type should call _connect_remote"""
        client = McpClient(
            name="test",
            server_type="remote",
            url="https://example.com/mcp",
        )
        client._connect_remote = AsyncMock()
        await client.connect()
        client._connect_remote.assert_called_once()

    @pytest.mark.asyncio
    async def test_stdio_type_calls_connect_local(self):
        """Stdio type attempts connection (raises RuntimeError on failure)"""
        client = McpClient(
            name="test",
            server_type="stdio",
            url=None,
            command=["python", "-m", "some_server"],
        )
        # Stdio connection will fail since 'some_server' doesn't exist
        with pytest.raises((NotImplementedError, RuntimeError)):
            await client.connect()

    @pytest.mark.asyncio
    async def test_already_connected_skips(self):
        """Already connected client should skip reconnection"""
        client = McpClient(
            name="test",
            server_type="sse",
            url="https://example.com/sse",
        )
        client._connected = True
        client._connect_remote = AsyncMock()
        await client.connect()
        client._connect_remote.assert_not_called()


class TestMcpClientRemoteFallback:
    """Test remote type fallback from Streamable HTTP to SSE"""

    @pytest.mark.asyncio
    async def test_remote_falls_back_to_sse(self):
        """Remote type should fall back to SSE when Streamable HTTP fails"""
        client = McpClient(
            name="test-remote",
            server_type="remote",
            url="https://mcp.example.com/mcp",
            timeout=10.0,
        )

        # Mock _do_connect_streamable_http to fail
        client._do_connect_streamable_http = AsyncMock(
            side_effect=RuntimeError("Streamable HTTP not supported")
        )
        # Mock _do_connect_sse to succeed
        async def mark_connected(url, headers=None):
            client._connected = True
        client._do_connect_sse = AsyncMock(side_effect=mark_connected)

        await client.connect()

        client._do_connect_streamable_http.assert_called_once()
        client._do_connect_sse.assert_called_once()
        assert client._transport_type == "sse"

    @pytest.mark.asyncio
    async def test_remote_streamable_http_success_no_sse(self):
        """Remote type should not try SSE if Streamable HTTP succeeds"""
        client = McpClient(
            name="test-remote",
            server_type="remote",
            url="https://mcp.example.com/mcp",
            timeout=10.0,
        )

        async def mark_connected(url, headers=None):
            client._connected = True
        client._do_connect_streamable_http = AsyncMock(side_effect=mark_connected)
        client._do_connect_sse = AsyncMock()

        await client.connect()

        client._do_connect_streamable_http.assert_called_once()
        client._do_connect_sse.assert_not_called()
        assert client._transport_type == "streamable_http"

    @pytest.mark.asyncio
    async def test_remote_both_fail_raises(self):
        """Remote type should raise RuntimeError if both transports fail"""
        client = McpClient(
            name="test-remote",
            server_type="remote",
            url="https://mcp.example.com/mcp",
            timeout=10.0,
        )

        client._do_connect_streamable_http = AsyncMock(
            side_effect=RuntimeError("HTTP failed")
        )
        client._do_connect_sse = AsyncMock(
            side_effect=RuntimeError("SSE failed")
        )

        with pytest.raises(RuntimeError, match="Connection failed.*SSE failed"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_sse_type_also_tries_streamable_http_first(self):
        """SSE type uses same auto-detect strategy as remote (Streamable HTTP first)"""
        client = McpClient(
            name="test-sse",
            server_type="sse",
            url="https://mcp.example.com/mcp",
            timeout=10.0,
        )

        async def mark_connected(url, headers=None):
            client._connected = True
        client._do_connect_streamable_http = AsyncMock(side_effect=mark_connected)
        client._do_connect_sse = AsyncMock()

        await client.connect()

        # "sse" and "remote" share the same auto-detect logic
        client._do_connect_streamable_http.assert_called_once()
        client._do_connect_sse.assert_not_called()
        assert client._transport_type == "streamable_http"

    @pytest.mark.asyncio
    async def test_timeout_does_not_fall_back(self):
        """Streamable HTTP timeout should NOT fall back to SSE (avoids double wait)"""
        client = McpClient(
            name="test-timeout",
            server_type="remote",
            url="https://mcp.example.com/mcp",
            timeout=10.0,
        )

        client._do_connect_streamable_http = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        client._do_connect_sse = AsyncMock()

        with pytest.raises(RuntimeError, match="Connection timeout"):
            await client.connect()

        # SSE should NOT have been attempted
        client._do_connect_sse.assert_not_called()
        assert client._transport_type is None

    @pytest.mark.asyncio
    async def test_remote_passes_resolved_headers_to_transports(self):
        """Remote connection should pass config and auth headers to SDK transports"""
        client = McpClient(
            name="test-headers",
            server_type="remote",
            url="https://mcp.example.com/mcp",
            headers={"Api-Key": "token123"},
            auth_config={
                "type": "apikey",
                "location": "header",
                "param_name": "Authorization",
                "value": "Bearer abc",
            },
            timeout=10.0,
        )

        client._do_connect_streamable_http = AsyncMock(
            side_effect=RuntimeError("HTTP failed")
        )

        async def mark_connected(url, headers):
            client._connected = True

        client._do_connect_sse = AsyncMock(side_effect=mark_connected)

        await client.connect()

        expected_headers = {
            "Api-Key": "token123",
            "Authorization": "Bearer abc",
        }
        client._do_connect_streamable_http.assert_called_once_with(
            "https://mcp.example.com/mcp",
            expected_headers,
        )
        client._do_connect_sse.assert_called_once_with(
            "https://mcp.example.com/mcp",
            expected_headers,
        )


class TestExtractRootCause:
    """Test _extract_root_cause helper function"""

    def test_simple_exception(self):
        """Simple exception returns its message"""
        assert _extract_root_cause(RuntimeError("simple error")) == "simple error"

    def test_exception_group(self):
        """ExceptionGroup should unwrap to the root cause"""
        inner = RuntimeError("real error")
        group = ExceptionGroup("group", [inner])
        assert _extract_root_cause(group) == "real error"

    def test_nested_exception_group(self):
        """Nested ExceptionGroups should be fully unwrapped"""
        inner = ValueError("deep error")
        group1 = ExceptionGroup("inner group", [inner])
        group2 = ExceptionGroup("outer group", [group1])
        assert _extract_root_cause(group2) == "deep error"

    def test_http_status_error(self):
        """HTTP status errors should show status code"""
        # Simulate httpx.HTTPStatusError
        class MockResponse:
            status_code = 401
        class MockRequest:
            url = "https://example.com/mcp?apikey=secret123"
        exc = Exception("HTTP error")
        exc.response = MockResponse()
        exc.request = MockRequest()
        result = _extract_root_cause(exc)
        assert "401" in result
        assert "secret" not in result  # URL should be masked
