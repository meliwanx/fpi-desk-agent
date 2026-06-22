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
            "Find files matching a glob pattern. "
            "Supports patterns like '**/*.py', 'src/**/*.ts', etc. "
            "Defaults to the active workspace; use an explicit absolute path "
            "to search another local folder read-only. "
            "Returns matching file paths sorted by modification time."
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files against (e.g. '**/*.py')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (defaults to project directory)",
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
