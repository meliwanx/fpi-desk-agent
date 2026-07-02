"""Task tool — SubAgent invocation.

Spawns a child session with its own agent loop, enabling:
  - Parallel exploration (explore subagent)
  - Code search delegation
  - Multi-step subtask execution (general subagent)

Improvements over initial implementation:
  - Sets parent_id on child session for proper hierarchy
  - Recursion depth guard (max 3 levels) prevents infinite nesting
  - Timeout prevents child sessions from running forever
  - Abort signal propagated from parent to child
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext

logger = logging.getLogger(__name__)

# Maximum nesting depth for subtasks to prevent infinite recursion
MAX_SUBTASK_DEPTH = 3

# Default timeout for subtask execution (seconds)
SUBTASK_TIMEOUT = 600.0


class TaskTool(ToolDefinition):

    @property
    def id(self) -> str:
        return "task"

    @property
    def description(self) -> str:
        return (
            "启动专门的子任务助理处理复杂子任务。"
            "可用类型：explore（快速搜索和探索代码库）、general（通用工具能力，不含 todo）。"
            "子任务助理会运行独立循环并返回结果。"
            "传入先前结果中的 task_id 可继续已有子任务会话。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "子任务简短描述（3 到 5 个词）",
                },
                "prompt": {
                    "type": "string",
                    "description": "给子任务助理的详细指令",
                },
                "agent": {
                    "type": "string",
                    "description": "子任务助理类型：explore 或 general",
                    "default": "explore",
                    "enum": ["explore", "general"],
                },
                "task_id": {
                    "type": "string",
                    "description": "可选。传入之前结果里的 task_id 以继续某个子任务。",
                },
            },
            "required": ["description", "prompt"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        description = args["description"]
        prompt = args["prompt"]
        agent_name = args.get("agent", "explore")
        task_id = args.get("task_id")

        # Import here to avoid circular imports
        from app.schemas.chat import PromptRequest
        from app.session.processor import run_generation
        from app.streaming.manager import GenerationJob
        from app.utils.id import generate_ulid

        # --- Recursion depth guard ---
        parent_depth = getattr(ctx, "_depth", 0)
        if parent_depth >= MAX_SUBTASK_DEPTH:
            return ToolResult(
                error=(
                    f"子任务嵌套深度已超过上限（{MAX_SUBTASK_DEPTH}）。"
                    "请直接完成当前任务，不要继续分派。"
                ),
            )

        # Access app-level registries through the _app_state injected by processor
        app_state = getattr(ctx, "_app_state", None)
        if not app_state:
            return ToolResult(error="子任务助理不可用：缺少应用状态。")

        session_factory = app_state["session_factory"]
        child_stream_id = generate_ulid()
        resuming = False

        # --- Resume existing session or create new one ---
        from app.session.manager import create_session, get_session
        if task_id:
            # Try to resume an existing child session
            async with session_factory() as db:
                existing = await get_session(db, task_id)
                if existing and existing.parent_id == ctx.session_id:
                    child_session_id = task_id
                    resuming = True
                    logger.info("Resuming subtask session %s", task_id)
                else:
                    logger.warning(
                        "task_id %s not found or parent mismatch, creating new session",
                        task_id,
                    )
                    task_id = None  # Fall through to create new

        if not task_id:
            child_session_id = generate_ulid()
            async with session_factory() as db:
                async with db.begin():
                    await create_session(
                        db,
                        id=child_session_id,
                        parent_id=ctx.session_id,
                        directory=".",
                        title=description,
                    )

        # Create a child job to capture the output
        child_job = GenerationJob(
            stream_id=child_stream_id,
            session_id=child_session_id,
        )
        # Propagate depth for nested recursion guard
        child_job._depth = parent_depth + 1

        # Build the child request
        child_request = PromptRequest(
            session_id=child_session_id,
            text=prompt,
            model=getattr(ctx, "_model_id", None),
            agent=agent_name,
        )

        # Publish subtask start to parent stream
        if ctx._publish_fn:
            ctx._publish_fn("subtask_start", {
                "session_id": child_session_id,
                "parent_id": ctx.session_id,
                "title": description,
                "agent": agent_name,
                "depth": parent_depth + 1,
                "resumed": resuming,
            })

        try:
            # Run with timeout + abort propagation
            await asyncio.wait_for(
                run_generation(
                    child_job,
                    child_request,
                    session_factory=session_factory,
                    provider_registry=app_state["provider_registry"],
                    agent_registry=app_state["agent_registry"],
                    tool_registry=app_state["tool_registry"],
                ),
                timeout=SUBTASK_TIMEOUT,
            )
        except asyncio.TimeoutError:
            child_job.abort()
            logger.warning(
                "Subtask timed out after %.0fs: %s", SUBTASK_TIMEOUT, description,
            )
            # Still extract whatever output was produced before timeout
        except Exception as e:
            logger.exception("子任务助理执行异常")
            return ToolResult(error=f"子任务助理执行失败：{e}")

        # Extract text output and key tool results from child events
        output_parts: list[str] = []
        error_parts: list[str] = []
        tool_results: list[str] = []
        for event in child_job.events:
            if event.event == "text-delta":
                output_parts.append(event.data.get("text", ""))
            elif event.event == "tool-result":
                # Capture tool results so the parent agent has visibility
                # into what the subagent actually found/did.
                tool_name = event.data.get("tool", "")
                tool_output = event.data.get("output", "")
                if tool_name and tool_output:
                    # Truncate individual results to avoid overwhelming the parent
                    if len(tool_output) > 2000:
                        tool_output = tool_output[:2000] + "... [已截断]"
                    tool_results.append(f"[{tool_name}] {tool_output}")
            elif event.event == "error":
                error_parts.append(event.data.get("message", ""))

        output = "".join(output_parts)

        # Append the most recent tool results (last 5) so the parent agent
        # can see what the subagent discovered, not just its text summary.
        if tool_results:
            recent_results = tool_results[-5:]
            output += "\n\n--- 关键工具结果 ---\n"
            output += "\n\n".join(recent_results)

        if error_parts:
            output += "\n[错误：" + "; ".join(error_parts) + "]"
        if not output.strip():
            output = "（子任务助理没有产生文本输出）"

        return ToolResult(
            output=output,
            title=f"子任务助理（{agent_name}）：{description}",
            metadata={
                "task_id": child_session_id,
                "session_id": child_session_id,
                "parent_id": ctx.session_id,
                "agent": agent_name,
                "depth": parent_depth + 1,
                "resumed": resuming,
                "events": len(child_job.events),
                "tool_calls": len(tool_results),
            },
        )
