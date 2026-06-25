"""Search tool — full-text search across workspace files using built-in FTS5.

Complements grep (exact regex) with ranked full-text keyword search.
"""

from __future__ import annotations

import logging
from typing import Any

from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext

logger = logging.getLogger(__name__)


class SearchTool(ToolDefinition):

    @property
    def id(self) -> str:
        return "search"

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return (
            "仅在已建立索引的工作区文件中做全文搜索。"
            "只有用户选择了工作区文件夹且索引可用时才使用。"
            "如果没有工作区，或搜索结果不足，请改用 glob、grep、read 并提供明确路径。"
            "该工具按关键词查找相关文件和片段，并返回带路径和上下文片段的排序结果。"
            "广泛探索时使用 search；精确正则匹配时使用 grep。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "关键词或自然语言搜索查询",
                },
                "path": {
                    "type": "string",
                    "description": "限制搜索到某个子目录（可选）",
                },
                "file_types": {
                    "type": "string",
                    "description": "用逗号分隔的文件扩展名过滤条件（例如 'py,ts,md'）",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最多返回结果数量",
                    "default": 20,
                },
            },
            "required": ["query"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        workspace = ctx.workspace
        if not workspace:
            return ToolResult(
                output=(
                    "未设置工作区，无法使用工作区全文检索。\n\n"
                    "请先让用户在输入框下方选择一个文件夹作为工作区；如果用户选择“整个电脑”，"
                    "不要使用 `search`，请改用 `glob`、`grep`、`read` 或带明确路径的命令来查找文件。"
                ),
                title="未设置工作区",
                metadata={"reason": "workspace_required"},
            )

        index_manager = getattr(ctx, "index_manager", None)
        if index_manager is None:
            return ToolResult(
                error="Search tool requires FTS indexing to be enabled. "
                      "Set OPENYAK_FTS_ENABLED=true and select a workspace."
            )

        query = args["query"]
        search_path = args.get("path")
        file_types = args.get("file_types")
        max_results = args.get("max_results", 20)

        try:
            data = await index_manager.search(
                workspace,
                query,
                path_filter=search_path,
                file_types=file_types,
                limit=max_results,
            )
        except Exception as e:
            logger.error("FTS search failed: %s", e)
            return ToolResult(error=f"Search failed: {e}")

        results = data.get("results", [])
        if not results:
            return ToolResult(
                output="(no results)",
                title=f'No results for "{query}"',
                metadata={"count": 0},
            )

        lines = []
        for rank, match in enumerate(results, 1):
            filename = match.get("filename", "")
            highlight = (match.get("highlight") or "").strip()
            score = match.get("relevance_score")

            header = f"{rank}. {filename}"
            if score is not None:
                header += f"  [score: {score:.3f}]"
            lines.append(header)
            if highlight:
                lines.append(f"   {highlight}")
            lines.append("")

        output = "\n".join(lines).rstrip()
        return ToolResult(
            output=output,
            title=f'{len(results)} results for "{query}"',
            metadata={"count": len(results), "total": data.get("total", len(results)), "query": query, "source": "fts"},
        )
