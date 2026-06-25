"""ToolSearch — lets agents discover deferred MCP tool schemas on demand.

MCP tools are not included in the LLM ``tools`` parameter by default to save
tokens.  Instead, their names are listed in the ToolSearch description.  When
the LLM calls ``tool_search``, matching tool schemas are returned as text and
the tools are marked "discovered" so they appear in subsequent LLM calls.
"""

from __future__ import annotations

import json
from typing import Any

from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext
from app.tool.registry import ToolRegistry


class ToolSearchTool(ToolDefinition):
    """Meta-tool that discovers deferred (MCP) tool schemas on demand."""

    # Budget: max tools listed in description, max chars per description line.
    _MAX_LISTED = 50
    _MAX_DESC_CHARS = 80

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry

    # ------------------------------------------------------------------
    # ToolDefinition interface
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return "tool_search"

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    @property
    def description(self) -> str:
        """Dynamic description listing deferred tool names."""
        base = (
            "获取延迟加载工具的完整 schema，使这些工具可被调用。\n\n"
            "下面只列出延迟加载工具名称。调用本工具获取 schema 之前，"
            "这些工具不会进入模型的可调用工具列表。\n\n"
            "调用本工具后，匹配到的工具会在后续轮次中带完整 schema 可用。\n\n"
            "查询格式：\n"
            '- "select:tool_name" 或 "select:tool1,tool2"：按名称精确获取工具\n'
            '- "关键词1 关键词2"：关键词搜索，最多返回 max_results 个匹配项'
        )

        deferred = self._get_deferred_tools()
        if not deferred:
            return base + "\n\n当前没有可延迟加载的工具。"

        shown = deferred[: self._MAX_LISTED]
        remaining = len(deferred) - len(shown)

        lines = [base, "", "可延迟加载工具："]
        for tool in shown:
            lines.append(f"- {tool.id}")

        if remaining > 0:
            lines.append(f"  （还有 {remaining} 个，可通过关键词搜索查找）")

        return "\n".join(lines)

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        '搜索查询。使用 "select:tool_name" 精确匹配，'
                        "或使用关键词进行模糊搜索。"
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "最多返回结果数量（默认 5）。",
                },
            },
            "required": ["query"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query: str = args.get("query", "")
        max_results: int = args.get("max_results", 5)

        deferred = self._get_deferred_tools()
        if not deferred:
            return ToolResult(output="当前没有可延迟加载的工具。", title="工具搜索")

        # --- Match ---
        if query.startswith("select:"):
            names = {n.strip() for n in query[7:].split(",") if n.strip()}
            matches = [t for t in deferred if t.id in names]
        else:
            matches = self._keyword_search(query, deferred, max_results)

        if not matches:
            available = ", ".join(t.id for t in deferred[:20])
            return ToolResult(
                output=f"没有找到匹配的延迟加载工具：{query}\n\n可用工具：{available}",
                title="工具搜索：没有结果",
            )

        # --- Mark discovered ---
        if ctx.discovered_tools is not None:
            for tool in matches:
                ctx.discovered_tools.add(tool.id)

        # --- Return full schemas ---
        sections: list[str] = []
        for tool in matches:
            spec = tool.to_openai_spec()["function"]
            sections.append(
                f"### {spec['name']}\n"
                f"{spec['description']}\n\n"
                f"参数：\n```json\n"
                f"{json.dumps(spec['parameters'], indent=2, ensure_ascii=False)}\n"
                f"```"
            )

        output = "\n\n".join(sections)
        ctx.publish_metadata(title=f"找到 {len(matches)} 个工具")
        return ToolResult(
            output=output,
            title=f"找到 {len(matches)} 个工具",
            metadata={"discovered": [t.id for t in matches]},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_deferred_tools(self) -> list[ToolDefinition]:
        """Return all MCP-wrapped tools (candidates for deferral)."""
        from app.mcp.tool_wrapper import McpToolWrapper

        return [
            t for t in self._tool_registry.all_tools()
            if isinstance(t, McpToolWrapper)
        ]

    @staticmethod
    def _keyword_search(
        query: str,
        tools: list[ToolDefinition],
        max_results: int,
    ) -> list[ToolDefinition]:
        """Simple keyword scoring on tool id + description."""
        keywords = query.lower().split()
        if not keywords:
            return tools[:max_results]

        scored: list[tuple[int, ToolDefinition]] = []
        for tool in tools:
            text = f"{tool.id} {tool.description}".lower()
            score = 0
            for kw in keywords:
                if kw in text:
                    # Exact word in id scores higher
                    if kw in tool.id.lower().split("_"):
                        score += 3
                    else:
                        score += 1
            if score > 0:
                scored.append((score, tool))

        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored[:max_results]]
