"""Glob tool — file pattern matching using pathlib."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.tool.base import ToolDefinition, ToolResult
from app.tool.builtin.glob_utils import wc_glob_files
from app.tool.context import ToolContext
from app.tool.workspace import WorkspaceViolation, resolve_for_read


class GlobTool(ToolDefinition):

    @property
    def id(self) -> str:
        return "glob"

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return (
            "按 glob 模式查找文件。支持 '**/*.py'、'src/**/*.ts' 等模式。"
            "默认在当前工作区搜索；也可以提供明确绝对路径，只读搜索本机其他目录。"
            "结果按修改时间排序返回匹配文件路径。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "用于匹配文件的 glob 模式（例如 '**/*.py'）",
                },
                "path": {
                    "type": "string",
                    "description": "搜索目录（默认当前项目目录）",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        pattern = args["pattern"]
        search_dir = args.get("path", ".")

        # Default to workspace when configured and no explicit path given
        if ctx.workspace and search_dir == ".":
            search_dir = ctx.workspace

        # Resolve search directory. Defaults stay in the workspace; explicit
        # absolute paths may inspect the local computer outside it.
        try:
            search_dir = resolve_for_read(search_dir, ctx.workspace)
        except WorkspaceViolation as e:
            return ToolResult(error=str(e))

        base = Path(search_dir).resolve()
        if not base.exists():
            return ToolResult(error=f"Directory not found: {search_dir}")

        try:
            matches = wc_glob_files(base, pattern)
        except ValueError as e:
            return ToolResult(error=f"Invalid glob pattern: {e}")

        # Filter to files only, sort by mtime (newest first)
        files = [m for m in matches if m.is_file()]

        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Limit output
        max_results = 500
        truncated = len(files) > max_results
        files = files[:max_results]

        # Format as absolute paths (avoids LLM path-joining errors)
        output_lines = []
        for f in files:
            output_lines.append(str(f))

        output = "\n".join(output_lines)
        if truncated:
            output += f"\n\n... ({len(matches) - max_results} more matches)"

        return ToolResult(
            output=output if output else "(no matches)",
            title=f"{len(files)} files matching {pattern}",
            metadata={"count": len(files), "truncated": truncated, "source": "filesystem"},
        )
