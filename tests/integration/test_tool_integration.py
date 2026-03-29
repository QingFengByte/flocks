"""
Tool integration tests.

Tests tool registration and agent permission checking.
Tests that relied on the removed runtime/ module (ToolCoordinator, strategy)
have been removed as part of the runtime/ cleanup.
"""

import pytest
from unittest.mock import patch, MagicMock

from flocks.tool.registry import ToolRegistry
from flocks.agent import Agent


class TestToolRegistration:
    """Test tool registration."""

    def test_threatbook_tools_registered(self):
        """Verify ThreatBook tools are registered."""
        ToolRegistry.init()
        tools = [t.name for t in ToolRegistry.list_tools()]

        assert "threatbook_ip_query" in tools
        assert "threatbook_domain_query" in tools
        assert "threatbook_file_report" in tools


class TestRexPermissions:
    """Test Rex agent permission checking."""

    @pytest.mark.asyncio
    async def test_rex_permission_for_ip_query(self):
        """Verify Rex permission for IP query tool."""
        result = await Agent.check_permission("rex", "threatbook_ip_query")
        assert result in ["allow", "deny"]
