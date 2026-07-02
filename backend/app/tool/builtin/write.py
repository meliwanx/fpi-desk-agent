"""Write tool — create or overwrite a file."""

from __future__ import annotations

import os
from typing import Any

from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext
from app.tool.workspace import WorkspaceViolation, resolve_for_write


class WriteTool(ToolDefinition):

    @property
    def id(self) -> str:
        return "write"

    @property
    def description(self) -> str:
        return (
            "创建新文件，或用指定内容覆盖已有文件。"
            "自包含的可视化 artifact 应使用 artifact 工具。"
            "写入最终面向用户的文件后，调用 present_file 展示。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要写入的绝对路径或相对路径",
                },
                "content": {
                    "type": "string",
                    "description": "要写入文件的内容",
                },
            },
            "required": ["file_path", "content"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        file_path = args["file_path"]

        # Workspace restriction check (relative paths default to fpiagent_written/)
        try:
            file_path = resolve_for_write(file_path, ctx.workspace)
        except WorkspaceViolation as e:
            return ToolResult(error=str(e))

        content = args["content"]

        try:
            # Create parent directories if needed
            parent = os.path.dirname(file_path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            existed = os.path.exists(file_path)

            with open(file_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)

            lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            action = "Updated" if existed else "Created"

            return ToolResult(
                output=f"{action} {file_path} ({lines} lines)",
                title=f"{action} {os.path.basename(file_path)}",
                metadata={"file_path": file_path},
            )

        except PermissionError:
            return ToolResult(error=f"Permission denied: {file_path}")
