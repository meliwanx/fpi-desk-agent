"""Plan tool — switch between build and plan mode mid-conversation.

The processor detects the "switch_agent" metadata in the ToolResult
and changes the active agent for subsequent loop iterations.
"""

from __future__ import annotations

from typing import Any

from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext


class PlanTool(ToolDefinition):
    """Switch between plan (read-only) and build (full access) modes."""

    @property
    def id(self) -> str:
        return "plan"

    @property
    def description(self) -> str:
        return (
            "在计划模式和构建模式之间切换。"
            "使用 command='enter' 进入计划模式（只读分析），"
            "使用 command='exit' 返回构建模式（完整工具权限）。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["enter", "exit"],
                    "description": "'enter' 表示切换到只读计划模式，'exit' 表示返回构建模式",
                },
            },
            "required": ["command"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        command = args["command"]

        if command == "enter":
            # Guard: already in plan mode
            if ctx.agent.name == "plan":
                return ToolResult(error="当前已经是计划模式。")

            return ToolResult(
                output=(
                    "已切换到计划模式。现在只有只读权限，可用于分析和制定计划。"
                    "准备开始实施时，使用 plan(command='exit') 返回构建模式。"
                ),
                metadata={"switch_agent": "plan"},
            )
        else:  # exit
            # Guard: not in plan mode
            if ctx.agent.name != "plan":
                return ToolResult(error="当前不在计划模式。")

            return ToolResult(
                output="已切换到构建模式，完整工具权限已恢复。",
                metadata={"switch_agent": "build"},
            )
