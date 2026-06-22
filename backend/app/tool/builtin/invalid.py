"""Invalid tool fallback — catches unrecognized tool calls."""

from __future__ import annotations

from typing import Any

from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext


class InvalidTool(ToolDefinition):
    """Fallback tool for unrecognized tool calls.

    Returns an error message telling the LLM the tool doesn't exist.
    This is part of tool call repair (OpenCode pattern).
    """

    @property
    def id(self) -> str:
        return "invalid"

    @property
    def description(self) -> str:
        return "Fallback for unrecognized tool calls"

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The unrecognized tool name"},
            },
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        raw_name = args.get("name")
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        display_name = name or "未命名工具"
        return ToolResult(
            output=(
                f"工具 `{display_name}` 不可用。\n\n"
                "请改用当前系统提示中列出的可用工具名称。如果只是普通回复，不要调用工具，直接回答用户。"
            ),
            title="工具不可用",
            metadata={"reason": "unknown_tool", "name": display_name},
        )
