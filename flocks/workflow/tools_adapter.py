"""Adapter: expose flocks ToolRegistry as workflow's tool registry (sync interface)."""

from __future__ import annotations

import asyncio
import json as _json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FuturesTimeoutError
from typing import Any, Dict, List, Optional

from flocks.tool import ToolContext, ToolRegistry, ToolResult
from flocks.workflow.errors import NodeExecutionError
from flocks.workflow.tools_spec import ToolSpec

# Tools that must not be exposed inside workflow (avoid circular invocation).
WORKFLOW_TOOL_BLOCKLIST = frozenset({"run_workflow"})


class FlocksToolAdapter:
    """Adapts flocks async ToolRegistry to workflow sync tool.run(name, **kwargs).

    - run(name, **kwargs): sync, runs asyncio.run(ToolRegistry.execute(...))
    - list(): all tool ids (auto-discovered from flocks), excluding blocklist
    - get(name): stub impl for code_gen signature extraction
    - get_spec(name): ToolSpec for code_gen
    - run_workflow is hidden to avoid workflow-in-workflow circular calls.
    """

    def __init__(self, tool_context: Optional[ToolContext] = None):
        ToolRegistry.init()
        self._ctx = tool_context
        # Executor used only when adapter is invoked from a thread
        # that already has a running asyncio event loop (common when workflow
        # is called from an async tool handler). In that case we cannot
        # run a nested loop in the same thread, so we offload tool execution
        # to a worker thread which uses asyncio.run().
        self._executor: Optional[ThreadPoolExecutor] = None

    def _blocked(self, name: str) -> bool:
        return (name or "").strip() in WORKFLOW_TOOL_BLOCKLIST

    def _ensure_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            # Low concurrency: workflow python nodes call tools sequentially.
            self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="wf-tool")
        return self._executor

    def _execute_tool_async(self, name: str, ctx: ToolContext, kwargs: Dict[str, Any]) -> ToolResult:
        """
        Execute an async tool from a sync context safely.

        - If no event loop is running in the current thread: run directly via asyncio.run().
        - If an event loop *is* running: offload to a worker thread to avoid
          'Cannot run the event loop while another loop is running'.
        """
        try:
            asyncio.get_running_loop()
            in_running_loop = True
        except RuntimeError:
            in_running_loop = False

        if not in_running_loop:
            # Safe in a pure sync thread.
            return asyncio.run(ToolRegistry.execute(name, ctx=ctx, **kwargs))

        # We are in a thread with a running event loop, but we must block synchronously.
        # The only safe option is to run the tool coroutine in another thread.
        ex = self._ensure_executor()
        fut = ex.submit(lambda: asyncio.run(ToolRegistry.execute(name, ctx=ctx, **kwargs)))
        return fut.result()

    def run(self, name: str, /, **kwargs: Any) -> Any:
        name = (name or "").strip()
        if self._blocked(name):
            raise NodeExecutionError(
                node_id="<tool>",
                message=f"Tool {name!r} is not available inside workflow (blocked to avoid circular invocation)",
            )
        tool = ToolRegistry.get(name)
        if tool is None:
            raise NodeExecutionError(node_id="<tool>", message=f"Tool not found: {name!r}")

        ctx = self._ctx or ToolContext(session_id="workflow", message_id="workflow")
        try:
            result: ToolResult = self._execute_tool_async(name, ctx, dict(kwargs))
        except _FuturesTimeoutError:
            raise
        except Exception as e:
            raise NodeExecutionError(
                node_id="<tool>", message=f"Tool {name!r} failed: {e}"
            ) from e

        if not result.success:
            raise NodeExecutionError(
                node_id="<tool>",
                message=result.error or f"Tool {name!r} failed",
            )
        return result.output

    def run_safe(self, name: str, /, **kwargs: Any) -> Dict[str, Any]:
        """Run tool and return a unified envelope dict.

        Returns:
            {
                "success": bool,
                "text": str,   # always a string (safe for prompt / string ops)
                "obj": Any,    # raw output (str | dict | list | None)
                "error": str | None,
            }

        Unlike ``run()`` which raises on failure and returns raw *output*
        (whose type varies per tool), ``run_safe()`` never raises and always
        returns a dict with a guaranteed ``text`` field.
        """
        try:
            raw = self.run(name, **kwargs)
            if isinstance(raw, str):
                text = raw
            elif raw is None:
                text = ""
            else:
                try:
                    text = _json.dumps(raw, ensure_ascii=False, default=str)
                except Exception:
                    text = str(raw)
            return {"success": True, "text": text, "obj": raw, "error": None}
        except _FuturesTimeoutError:
            raise
        except Exception as exc:
            return {"success": False, "text": "", "obj": None, "error": str(exc)}

    def list(self) -> List[str]:
        ToolRegistry.init()
        return [n for n in ToolRegistry.all_tool_ids() if n not in WORKFLOW_TOOL_BLOCKLIST]

    def get(self, name: str) -> Optional[Any]:
        """Return a stub with .run for code_gen signature extraction."""
        if self._blocked(name):
            return None
        tool = ToolRegistry.get(name)
        if tool is None:
            return None
        return _ToolStub(tool)

    def get_spec(self, name: str) -> Optional[ToolSpec]:
        if self._blocked(name):
            return None
        tool = ToolRegistry.get(name)
        if tool is None:
            return None
        info = tool.info
        props: Dict[str, Any] = {}
        required: List[str] = []
        for p in info.parameters:
            props[p.name] = {"type": p.type.value, "description": p.description or ""}
            if p.required:
                required.append(p.name)
        args_schema: Dict[str, Any] = {"type": "object", "properties": props}
        if required:
            args_schema["required"] = required
        sig_parts = [f"{p.name}: {p.type.value}" for p in info.parameters]
        signature = "(" + ", ".join(sig_parts) + ")"
        return ToolSpec(
            name=info.name,
            description=info.description or "",
            args_schema=args_schema,
            signature=signature,
        )


class _ToolStub:
    """Stub so code_gen can get run() signature from flocks tool."""

    def __init__(self, tool: Any):
        self._tool = tool

    def run(self, **kwargs: Any) -> Any:
        raise NotImplementedError("Use adapter.run()")

    @property
    def __doc__(self) -> str:
        return getattr(self._tool.info, "description", "") or ""
