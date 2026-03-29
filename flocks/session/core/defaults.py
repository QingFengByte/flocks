"""
Default constants for the session module.

Single source of truth for fallback provider/model values used across
runner.py, session_loop.py, and message.py.
"""

import os

_DEFAULT_PROVIDER = "anthropic"
_DEFAULT_MODEL = "claude-sonnet-4-20250514"


def fallback_provider_id() -> str:
    """Return the fallback provider, respecting runtime env-var overrides."""
    return os.environ.get("LLM_PROVIDER", _DEFAULT_PROVIDER)


def fallback_model_id() -> str:
    """Return the fallback model, respecting runtime env-var overrides."""
    return os.environ.get("LLM_MODEL", _DEFAULT_MODEL)


# Doom-loop detection: if the last N tool calls in a single assistant
# message are identical (same tool + same input), stop processing.
DOOM_LOOP_THRESHOLD = 3
