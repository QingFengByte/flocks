"""
Tests for Phase 1: Unified UI entry via SessionLoop.

Verifies that:
1. RunnerCallbacks.event_publish_callback is passed through to StreamProcessor
2. LoopCallbacks carries runner_callbacks and event_publish_callback
3. SessionRunner uses explicit callbacks (doesn't override with CLI fallback)
4. _resolve_model implements 5-level priority correctly
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from flocks.session.runner import RunnerCallbacks
from flocks.session.session_loop import LoopCallbacks


class TestRunnerCallbacksEventPublish:
    """RunnerCallbacks should carry event_publish_callback."""

    def test_event_publish_callback_field_exists(self):
        cb = RunnerCallbacks()
        assert hasattr(cb, 'event_publish_callback')
        assert cb.event_publish_callback is None

    def test_event_publish_callback_can_be_set(self):
        publish = AsyncMock()
        cb = RunnerCallbacks(event_publish_callback=publish)
        assert cb.event_publish_callback is publish


class TestLoopCallbacksFields:
    """LoopCallbacks should carry event_publish_callback and runner_callbacks."""

    def test_event_publish_callback_field(self):
        cb = LoopCallbacks()
        assert hasattr(cb, 'event_publish_callback')
        assert cb.event_publish_callback is None

    def test_runner_callbacks_field(self):
        cb = LoopCallbacks()
        assert hasattr(cb, 'runner_callbacks')
        assert cb.runner_callbacks is None

    def test_pass_runner_callbacks(self):
        runner_cb = RunnerCallbacks(on_error=AsyncMock())
        loop_cb = LoopCallbacks(runner_callbacks=runner_cb)
        assert loop_cb.runner_callbacks is runner_cb
        assert loop_cb.runner_callbacks.on_error is not None


class TestCallbackPrecedence:
    """SessionRunner should not override explicit callbacks with CLI fallback."""

    def test_explicit_callbacks_not_overridden(self):
        """When event_publish_callback is set, CLI fallback should NOT be used."""
        publish = AsyncMock()
        cb = RunnerCallbacks(event_publish_callback=publish)
        
        # Verify the check that _process_step uses
        has_explicit = any([
            cb.on_text_delta,
            cb.on_tool_start,
            cb.on_tool_end,
            cb.on_error,
            cb.event_publish_callback,
        ])
        assert has_explicit is True

    def test_empty_callbacks_allows_cli_fallback(self):
        """When no callbacks are set, CLI fallback should be used."""
        cb = RunnerCallbacks()
        has_explicit = any([
            cb.on_text_delta,
            cb.on_tool_start,
            cb.on_tool_end,
            cb.on_error,
            cb.event_publish_callback,
        ])
        assert has_explicit is False


class TestResolveModel:
    """Test the _resolve_model 5-level priority."""

    @pytest.mark.asyncio
    async def test_priority_1_request_model(self):
        """Request model takes highest priority."""
        from flocks.server.routes.session import _resolve_model

        request = MagicMock()
        request.model = MagicMock()
        request.model.providerID = "anthropic"
        request.model.modelID = "claude-sonnet-4-5"
        
        agent = MagicMock()
        agent.model = None

        provider_id, model_id, source = await _resolve_model(request, agent, "test-session")
        assert provider_id == "anthropic"
        assert model_id == "claude-sonnet-4-5"
        assert source == "request"

    @pytest.mark.asyncio
    async def test_priority_2_agent_model(self):
        """Agent model is used when request has no model."""
        from flocks.server.routes.session import _resolve_model

        request = MagicMock()
        request.model = None
        
        agent = MagicMock()
        agent.model = {"providerID": "openai", "modelID": "gpt-4o"}

        provider_id, model_id, source = await _resolve_model(request, agent, "test-session")
        assert provider_id == "openai"
        assert model_id == "gpt-4o"
        assert source == "agent"

    @pytest.mark.asyncio
    async def test_priority_5_env_fallback(self):
        """Environment variables are used as final fallback."""
        from flocks.server.routes.session import _resolve_model

        request = MagicMock()
        request.model = None
        
        agent = MagicMock()
        agent.model = None

        with patch("flocks.server.routes.session._get_last_model", return_value=None), \
             patch("flocks.config.config.Config") as mock_config_cls:
            # Make config not have a model
            mock_config = MagicMock()
            mock_config.model = None
            mock_config_cls.get = AsyncMock(return_value=mock_config)
            
            with patch.dict("os.environ", {"LLM_PROVIDER": "test-provider", "LLM_MODEL": "test-model"}):
                provider_id, model_id, source = await _resolve_model(request, agent, "test-session")
                assert provider_id == "test-provider"
                assert model_id == "test-model"
                assert source == "env_default"
