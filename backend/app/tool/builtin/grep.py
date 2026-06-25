"""Grep tool — regex content search across files."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from app.tool.base import ToolDefinition, ToolResult
from app.tool.builtin.glob_utils import wc_glob_files
from app.tool.context import ToolContext
from app.tool.workspace import WorkspaceViolation, resolve_for_read

logger = logging.getLogger(__name__)


class GrepTool(ToolDefinition):

    @property
    def id(self) -> str:
        return "grep"

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return (
            "使用正则表达式搜索文件内容。支持文件类型过滤和上下文行。"
            "默认在当前工作区搜索；也可以提供明确绝对路径，只读搜索本机其他文件或目录。"
            "返回匹配行、文件路径和行号。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "要搜索的正则表达式",
                },
                "path": {
                    "type": "string",
                    "description": "要搜索的文件或目录（默认当前目录）",
                },
                "glob": {
                    "type": "string",
                    "description": "用于过滤文件的 glob 模式（例如 '*.py'、'*.{ts,tsx}'）",
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "是否忽略大小写",
                    "default": False,
                },
                "context": {
                    "type": "integer",
                    "description": "匹配行前后各返回多少上下文行",
                    "default": 0,
                },
                "max_results": {
                    "type": "integer",
                    "description": "最多返回匹配行数量",
                    "default": 100,
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return await self._filesystem_execute(args, ctx)

    # ------------------------------------------------------------------
    # Filesystem path
    # ------------------------------------------------------------------

    async def _filesystem_execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        pattern_str = args["pattern"]
        search_path = args.get("path", ".")

        # Default to workspace when configured and no explicit path given
        if ctx.workspace and search_path == ".":
            search_path = ctx.workspace

        # Resolve search path. Defaults stay in the workspace; explicit
        # absolute paths may inspect the local computer outside it.
        try:
            search_path = resolve_for_read(search_path, ctx.workspace)
        except WorkspaceViolation as e:
            return ToolResult(error=str(e))

        file_glob = args.get("glob")
        case_insensitive = args.get("case_insensitive", False)
        context_lines = args.get("context", 0)
        max_results = args.get("max_results", 100)

        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern_str, flags)
        except re.error as e:
            return ToolResult(error=f"Invalid regex: {e}")

        base = Path(search_path).resolve()

        # Collect files to search
        if base.is_file():
            files = [base]
        elif base.is_dir():
            if file_glob:
                files = sorted(wc_glob_files(base, file_glob, recursive=True))
            else:
                files = sorted(base.rglob("*"))
            files = [f for f in files if f.is_file()]
        else:
            return ToolResult(error=f"Path not found: {search_path}")

        results = []
        total_matches = 0

        for file_path in files:
            if total_matches >= max_results:
                break

            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except (PermissionError, OSError):
                continue

            lines = text.splitlines()
            for i, line in enumerate(lines):
                if total_matches >= max_results:
                    break
                if regex.search(line):
                    total_matches += 1
                    try:
                        rel = file_path.relative_to(base if base.is_dir() else base.parent)
                    except ValueError:
                        rel = file_path

                    if context_lines > 0:
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        for j in range(start, end):
                            prefix = ">" if j == i else " "
                            results.append(f"{rel}:{j + 1}{prefix} {lines[j]}")
                        results.append("")  # separator
                    else:
                        results.append(f"{rel}:{i + 1}: {line}")

        output = "\n".join(results) if results else "(no matches)"
        if total_matches >= max_results:
            output += f"\n\n... (truncated at {max_results} matches)"

        return ToolResult(
            output=output,
            title=f"{total_matches} matches for /{pattern_str}/",
            metadata={"matches": total_matches},
        )
