"""
Tests for session abort and inject functionality.

Tests cover:
- SessionRunner external abort_event propagation
- SessionLoop abort mechanism
- Inject endpoint logic (message creation without starting new loop)
- _should_exit behavior with injected messages
"""

import asyncio
import pytest

from flocks.session.session_loop import SessionLoop, LoopContext, LoopResult
from flocks.session.runner import SessionRunner
from flocks.session.session import SessionInfo
from flocks.server.routes import session as session_routes


def _make_session_info(session_id: str = "test_session") -> SessionInfo:
    """Create a minimal SessionInfo via model_construct (skips validation)."""
    return SessionInfo.model_construct(
        id=session_id,
        slug="test",
        project_id="test_project",
        directory="/tmp",
        title="Test Session",
    )


# ---------------------------------------------------------------------------
# Abort propagation tests
# ---------------------------------------------------------------------------

class TestAbortPropagation:
    """Test that abort_event propagates from SessionLoop to SessionRunner."""

    def test_runner_accepts_external_abort_event(self):
        """SessionRunner should accept an optional external abort_event."""
        external_event = asyncio.Event()
        session_info = _make_session_info()

        runner = SessionRunner(
            session=session_info,
            abort_event=external_event,
        )

        # Initially not aborted
        assert runner.is_aborted is False

        # Set external event → runner should report aborted
        external_event.set()
        assert runner.is_aborted is True

    def test_runner_internal_abort_still_works(self):
        """SessionRunner's own abort() method should still work."""
        session_info = _make_session_info()
        runner = SessionRunner(session=session_info)

        assert runner.is_aborted is False
        runner.abort()
        assert runner.is_aborted is True

    def test_runner_either_abort_triggers(self):
        """Either internal or external abort should trigger is_aborted."""
        external_event = asyncio.Event()
        session_info = _make_session_info()

        runner = SessionRunner(
            session=session_info,
            abort_event=external_event,
        )

        # Neither set → not aborted
        assert runner.is_aborted is False

        # Only external set
        external_event.set()
        assert runner.is_aborted is True

        # Clear external, set internal
        external_event.clear()
        runner._abort.clear()
        assert runner.is_aborted is False

        runner.abort()
        assert runner.is_aborted is True

    def test_runner_without_external_event(self):
        """Runner created without abort_event should still work normally."""
        session_info = _make_session_info()
        runner = SessionRunner(session=session_info)

        assert runner._external_abort is None
        assert runner.is_aborted is False
        runner.abort()
        assert runner.is_aborted is True


# ---------------------------------------------------------------------------
# SessionLoop abort tests
# ---------------------------------------------------------------------------

class TestSessionLoopAbort:
    """Test SessionLoop.abort() class method."""

    def test_abort_nonexistent_session(self):
        """Aborting a session that isn't running should return False."""
        result = SessionLoop.abort("nonexistent_session_id")
        assert result is False

    def test_abort_running_session(self):
        """Aborting a running session should set the abort_event and return True."""
        session_info = _make_session_info("test_loop_abort")
        ctx = LoopContext(
            session=session_info,
            provider_id="test",
            model_id="test",
            agent_name="test",
        )

        # Register the context
        SessionLoop._active_loops["test_loop_abort"] = ctx

        try:
            assert ctx.should_abort() is False
            result = SessionLoop.abort("test_loop_abort")
            assert result is True
            assert ctx.should_abort() is True
        finally:
            # Clean up
            SessionLoop._active_loops.pop("test_loop_abort", None)

    def test_is_running(self):
        """is_running should reflect _active_loops state."""
        assert SessionLoop.is_running("not_there") is False

        session_info = _make_session_info("running_test")
        ctx = LoopContext(
            session=session_info,
            provider_id="test",
            model_id="test",
            agent_name="test",
        )
        SessionLoop._active_loops["running_test"] = ctx

        try:
            assert SessionLoop.is_running("running_test") is True
        finally:
            SessionLoop._active_loops.pop("running_test", None)

    def test_get_context(self):
        """get_context should return the LoopContext for a running session."""
        session_info = _make_session_info("ctx_get_test")
        ctx = LoopContext(
            session=session_info,
            provider_id="test",
            model_id="test",
            agent_name="test",
        )
        SessionLoop._active_loops["ctx_get_test"] = ctx

        try:
            retrieved = SessionLoop.get_context("ctx_get_test")
            assert retrieved is ctx
            assert SessionLoop.get_context("nonexistent") is None
        finally:
            SessionLoop._active_loops.pop("ctx_get_test", None)


# ---------------------------------------------------------------------------
# _should_exit logic with injected messages
# ---------------------------------------------------------------------------

class TestShouldExitWithInject:
    """Test that _should_exit correctly handles injected user messages."""

    @staticmethod
    def _make_msg(msg_id: str, role: str, finish: str = None):
        """Create a minimal message-like object for testing."""
        msg = type("Msg", (), {})()
        msg.id = msg_id
        msg.role = role
        msg.finish = finish
        return msg

    def test_exit_when_assistant_after_user_and_finished(self):
        """Should exit if last assistant finished after last user."""
        last_user = self._make_msg("msg_001", "user")
        last_assistant = self._make_msg("msg_002", "assistant", finish="stop")

        # assistant.id > user.id → user.id < assistant.id → True → should exit
        assert SessionLoop._should_exit(last_user, last_assistant) is True

    def test_no_exit_when_user_injected_after_assistant(self):
        """Should NOT exit when a new user message appears after the assistant.

        This is the core inject scenario: the injected user message has a
        higher ID than the last assistant message, so the loop should continue.
        """
        last_user = self._make_msg("msg_003", "user")  # injected message
        last_assistant = self._make_msg("msg_002", "assistant", finish="stop")

        # user.id > assistant.id → user.id < assistant.id → False → don't exit
        assert SessionLoop._should_exit(last_user, last_assistant) is False

    def test_no_exit_when_assistant_has_tool_calls(self):
        """Should NOT exit when assistant finish is 'tool-calls'."""
        last_user = self._make_msg("msg_001", "user")
        last_assistant = self._make_msg("msg_002", "assistant", finish="tool-calls")

        assert SessionLoop._should_exit(last_user, last_assistant) is False

    def test_no_exit_when_no_assistant(self):
        """Should NOT exit when there is no assistant message yet."""
        last_user = self._make_msg("msg_001", "user")

        assert SessionLoop._should_exit(last_user, None) is False

    def test_no_exit_when_assistant_finish_is_unknown(self):
        """Should NOT exit when finish reason is 'unknown'."""
        last_user = self._make_msg("msg_001", "user")
        last_assistant = self._make_msg("msg_002", "assistant", finish="unknown")

        assert SessionLoop._should_exit(last_user, last_assistant) is False

    def test_no_exit_when_assistant_not_finished(self):
        """Should NOT exit when assistant has no finish status."""
        last_user = self._make_msg("msg_001", "user")
        last_assistant = self._make_msg("msg_002", "assistant", finish=None)

        assert SessionLoop._should_exit(last_user, last_assistant) is False


# ---------------------------------------------------------------------------
# LoopContext tests
# ---------------------------------------------------------------------------

class TestLoopContext:
    """Test LoopContext abort event lifecycle."""

    def test_signal_and_check_abort(self):
        """signal_abort should cause should_abort to return True."""
        session_info = _make_session_info("ctx_abort_test")
        ctx = LoopContext(
            session=session_info,
            provider_id="test",
            model_id="test",
            agent_name="test",
        )

        assert ctx.should_abort() is False
        ctx.signal_abort()
        assert ctx.should_abort() is True

    def test_abort_event_is_asyncio_event(self):
        """abort_event should be a proper asyncio.Event."""
        session_info = _make_session_info("event_type_test")
        ctx = LoopContext(
            session=session_info,
            provider_id="test",
            model_id="test",
            agent_name="test",
        )

        assert isinstance(ctx.abort_event, asyncio.Event)

    def test_step_counter_default(self):
        """Step counter should default to 0."""
        session_info = _make_session_info("step_test")
        ctx = LoopContext(
            session=session_info,
            provider_id="test",
            model_id="test",
            agent_name="test",
        )
        assert ctx.step == 0


