"""Present file tool — explicitly open an existing file for the user."""

from __future__ import annotations

import os
from typing import Any

from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext
from app.tool.workspace import WorkspaceViolation, resolve_for_read


class PresentFileTool(ToolDefinition):

    @property
    def id(self) -> str:
        return "present_file"

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return (
            "在用户的可视化预览面板中打开已有文件。"
            "当你创建了用户要求的最终交付文件，或需要展示一个有价值的已有文件时使用。"
            "不要用于临时脚本、草稿文件、日志或辅助文件。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要展示的文件绝对路径或工作区相对路径",
                },
                "title": {
                    "type": "string",
                    "description": "预览面板中可选的展示标题",
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        file_path = args["file_path"]
        try:
            resolved = resolve_for_read(file_path, ctx.workspace)
        except WorkspaceViolation as e:
            return ToolResult(error=str(e))

        if not os.path.exists(resolved):
            return ToolResult(error=f"File not found: {file_path}")
        if os.path.isdir(resolved):
            return ToolResult(error=f"Cannot present a directory: {file_path}")

        title = args.get("title") or os.path.basename(resolved) or "File Preview"
        return ToolResult(
            output=f"Presented {resolved}",
            title=f"Presented {title}",
            metadata={"file_path": resolved, "title": title},
        )
