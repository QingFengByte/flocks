"""
Permission handling for session operations.

Ported from original permission/next.ts PermissionNext namespace.
Handles permission requests, replies, and rule evaluation.
"""

import asyncio
from typing import Optional, Dict, Any, List, Callable, Awaitable

from pydantic import BaseModel, Field

from flocks.utils.log import Log
from flocks.utils.id import Identifier
from flocks.permission.rule import PermissionRule, PermissionLevel
from flocks.permission.helpers import Ruleset, from_config, merge

log = Log.create(service="permission")


class PermissionRequestInfo(BaseModel):
    """Permission request information"""

    model_config = {"populate_by_name": True}

    id: str
    session_id: str = Field(alias="sessionID")
    permission: str
    patterns: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    always: List[str] = Field(default_factory=list)
    tool: Optional[Dict[str, str]] = None


class DeniedError(Exception):
    """Exception raised when permission is denied"""

    def __init__(self, rules: List[PermissionRule]):
        self.rules = rules
        super().__init__(f"Permission denied by rules: {rules}")


class PermissionNext:
    """
    Permission management namespace.

    Handles:
    - Permission rule evaluation
    - Permission request/reply flow
    - Session-scoped permission caching
    """

    _pending: Dict[str, Dict[str, Any]] = {}
    _session_permissions: Dict[str, Dict[str, str]] = {}
    _permanent_rules: Dict[str, str] = {}

    _on_permission_asked: Optional[Callable[[PermissionRequestInfo], Awaitable[None]]] = None
    _on_permission_replied: Optional[Callable[[str, str, str], Awaitable[None]]] = None

    @classmethod
    def set_callbacks(
        cls,
        on_asked: Optional[Callable[[PermissionRequestInfo], Awaitable[None]]] = None,
        on_replied: Optional[Callable[[str, str, str], Awaitable[None]]] = None,
    ) -> None:
        """Set event callbacks for permission events."""
        cls._on_permission_asked = on_asked
        cls._on_permission_replied = on_replied

    @classmethod
    async def ask(
        cls,
        session_id: str,
        permission: str,
        patterns: List[str],
        ruleset: Ruleset,
        metadata: Optional[Dict[str, Any]] = None,
        always: Optional[List[str]] = None,
        tool: Optional[Dict[str, str]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """
        Ask for permission to perform an action.

        Ported from original PermissionNext.ask().
        """
        import os

        metadata = metadata or {}
        always_patterns = always or []

        if os.environ.get("FLOCKS_AUTO_APPROVE") == "true":
            log.debug("permission.auto_approved", {
                "permission": permission,
                "reason": "FLOCKS_AUTO_APPROVE=true",
            })
            return

        session_perms = cls._session_permissions.get(session_id, {})
        if permission in session_perms:
            action = session_perms[permission]
            if action == "allow":
                return
            if action == "deny":
                raise DeniedError([])

        if permission in cls._permanent_rules:
            action = cls._permanent_rules[permission]
            if action in ("allow", "always"):
                return
            if action in ("deny", "never"):
                raise DeniedError([])

        if ruleset:
            action = cls._evaluate(permission, patterns[0] if patterns else "*", ruleset)
            if action == "allow":
                return
            if action == "deny":
                matching_rules = [
                    rule for rule in ruleset
                    if cls._pattern_matches(permission, rule.permission or "*")
                    and cls._pattern_matches(patterns[0] if patterns else "*", rule.pattern or "*")
                ]
                raise DeniedError(matching_rules)

        if always_patterns:
            for pattern in always_patterns:
                if cls._pattern_matches(patterns[0] if patterns else "*", pattern):
                    return

        req_id = request_id or Identifier.create("permission")
        request_info = PermissionRequestInfo(
            id=req_id,
            sessionID=session_id,
            permission=permission,
            patterns=patterns,
            metadata=metadata,
            always=always_patterns,
            tool=tool,
        )

        future = asyncio.Future()
        cls._pending[req_id] = {
            "info": request_info,
            "future": future,
        }

        if cls._on_permission_asked:
            await cls._on_permission_asked(request_info)

        try:
            from flocks.server.routes.event import publish_event
            await publish_event("permission.request", {
                "requestID": req_id,
                "sessionID": session_id,
                "permission": permission,
                "patterns": patterns,
                "metadata": metadata or {},
                "tool": tool,
            })
        except Exception as exc:
            log.debug("permission.request.publish_failed", {"error": str(exc)})

        try:
            reply = await asyncio.wait_for(future, timeout=300)
        except asyncio.TimeoutError:
            if req_id in cls._pending:
                del cls._pending[req_id]
            raise PermissionError(f"Permission request timed out: {permission}")

        if reply in ("allow", "once"):
            return
        if reply in ("deny", "reject"):
            raise DeniedError([])
        if reply == "always":
            cls._permanent_rules[permission] = "allow"
            return
        if reply == "never":
            cls._permanent_rules[permission] = "deny"
            raise DeniedError([])
        if reply == "allow_session":
            if session_id not in cls._session_permissions:
                cls._session_permissions[session_id] = {}
            cls._session_permissions[session_id][permission] = "allow"
            return

        raise PermissionError(f"Unknown permission reply: {reply}")

    @classmethod
    def reply(
        cls,
        request_id: str,
        reply: str,
        session_id: Optional[str] = None,
    ) -> None:
        """Reply to a pending permission request."""
        if request_id not in cls._pending:
            log.warn("permission.reply.not_found", {"request_id": request_id})
            return

        pending = cls._pending[request_id]
        future = pending["future"]
        request_info = pending["info"]

        log.info("permission.replied", {
            "request_id": request_id,
            "reply": reply,
        })

        if not future.done():
            future.set_result(reply)

        if cls._on_permission_replied:
            resolved_session_id = session_id or request_info.session_id
            try:
                task = cls._on_permission_replied(resolved_session_id, request_id, reply)
                if asyncio.iscoroutine(task):
                    asyncio.create_task(task)
            except Exception as exc:
                log.debug("permission.reply.callback_failed", {"error": str(exc)})

        if request_id in cls._pending:
            del cls._pending[request_id]

    @classmethod
    def evaluate(
        cls,
        permission: str,
        pattern: str,
        ruleset: Ruleset,
    ) -> str:
        """
        Public interface: evaluate permission action for a (permission, pattern) pair
        against a ruleset using last-matching-rule-wins semantics.

        Returns one of: 'allow', 'deny', 'ask'.
        """
        return cls._evaluate(permission, pattern, ruleset)

    @classmethod
    def _evaluate(
        cls,
        permission: str,
        pattern: str,
        ruleset: Ruleset,
    ) -> str:
        """Evaluate permission action for a pattern."""
        matched_rule = None
        for rule in reversed(ruleset):
            if not cls._pattern_matches(permission, rule.permission or "*"):
                continue
            if not cls._pattern_matches(pattern, rule.pattern or "*"):
                continue
            matched_rule = rule
            break

        if matched_rule:
            return matched_rule.level.value if hasattr(matched_rule.level, "value") else str(matched_rule.level)

        return "ask"

    @classmethod
    def _pattern_matches(cls, text: str, pattern: str) -> bool:
        """Check if text matches pattern (with wildcard support)."""
        if pattern == "*":
            return True
        if "*" in pattern:
            import fnmatch
            return fnmatch.fnmatch(text, pattern)
        return text == pattern

    @classmethod
    def from_config(cls, permission_config):
        """Alias for from_config function."""
        return from_config(permission_config)

    @classmethod
    def merge(cls, *rulesets: Ruleset) -> Ruleset:
        """Alias for merge function."""
        return merge(*rulesets)


__all__ = ["PermissionNext", "PermissionRequestInfo", "DeniedError", "Ruleset"]
