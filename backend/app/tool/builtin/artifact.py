"""Artifact tool — create, update, and rewrite artifacts in the viewer panel.

Supports three commands modeled after Claude.ai:
  - create:  New artifact with full content
  - update:  Targeted old_str→new_str replacement (token-efficient)
  - rewrite: Full content replacement for major changes
"""

from __future__ import annotations

import logging
from typing import Any

from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext

log = logging.getLogger(__name__)


class ArtifactTool(ToolDefinition):

    @property
    def id(self) -> str:
        return "artifact"

    @property
    def description(self) -> str:
        return (
            "管理可视化预览面板中的 artifact。命令：\n"
            "- 'create'：使用完整内容创建新 artifact。\n"
            "- 'update'：通过 old_str/new_str 做定点字符串替换，节省上下文。\n"
            "- 'rewrite'：用于重大修改的完整内容替换。\n"
            "适用于交互式或可视化内容，例如 React 组件、HTML 页面、SVG 图形、代码文件、Markdown 文档或 Mermaid 图。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["create", "update", "rewrite"],
                    "description": (
                        "操作类型：'create' 创建新 artifact，"
                        "'update' 做 old_str→new_str 定点替换，"
                        "'rewrite' 做完整内容替换。"
                    ),
                },
                "identifier": {
                    "type": "string",
                    "description": (
                        "稳定的 kebab-case 标识符。"
                        "同一个 artifact 在 create/update/rewrite 中应复用同一 identifier，便于跨轮次追踪。"
                    ),
                },
                "type": {
                    "type": "string",
                    "enum": ["react", "html", "svg", "code", "markdown", "mermaid"],
                    "description": "artifact 类型（create 时必填）。",
                },
                "title": {
                    "type": "string",
                    "description": "简短清晰的标题（create 时必填）。",
                },
                "content": {
                    "type": "string",
                    "description": "create 或 rewrite 命令使用的完整内容。",
                },
                "old_str": {
                    "type": "string",
                    "description": "update 命令中要查找的精确字符串。",
                },
                "new_str": {
                    "type": "string",
                    "description": "update 命令中的替换字符串。",
                },
                "language": {
                    "type": "string",
                    "description": "code 类型使用的编程语言（例如 'python'）。",
                },
            },
            "required": ["command", "identifier"],
        }

    def _get_cache(self, ctx: ToolContext) -> dict[str, dict[str, Any]]:
        """Get the artifact cache from the GenerationJob."""
        job = getattr(ctx, "_job", None)
        if job is not None:
            return getattr(job, "artifact_cache", {})
        return {}

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        command = args.get("command", "create")
        identifier = args.get("identifier", "")
        artifact_type = args.get("type")
        title = args.get("title")
        language = args.get("language")
        cache = self._get_cache(ctx)

        if command == "create":
            content = args.get("content", "")
            if not artifact_type or not title or not content:
                return ToolResult(
                    error="'create' 需要提供 'type'、'title' 和 'content' 参数。",
                )

            cache[identifier] = {
                "content": content,
                "type": artifact_type,
                "title": title,
                "language": language,
            }

            return ToolResult(
                output=f"Artifact '{title}' 已创建。",
                metadata={
                    "command": "create",
                    "type": artifact_type,
                    "title": title,
                    "identifier": identifier,
                    "language": language,
                    "content": content,
                },
            )

        elif command == "update":
            old_str = args.get("old_str", "")
            new_str = args.get("new_str", "")
            if not old_str:
                return ToolResult(error="'update' 需要提供 'old_str' 参数。")

            cached = cache.get(identifier)
            if not cached:
                return ToolResult(
                    error=(
                        f"没有找到 identifier 为 '{identifier}' 的 artifact。"
                        "请先使用 'create' 命令。"
                    ),
                )

            current_content = cached["content"]
            if old_str not in current_content:
                return ToolResult(
                    error=(
                        f"在 artifact '{identifier}' 中没有找到 old_str。"
                        f"内容可能已经变化。"
                        f"当前内容长度：{len(current_content)} 个字符。"
                    ),
                )

            new_content = current_content.replace(old_str, new_str, 1)
            cached["content"] = new_content
            if title:
                cached["title"] = title
            if artifact_type:
                cached["type"] = artifact_type

            return ToolResult(
                output=f"Artifact '{identifier}' 已更新（替换 {len(old_str)} 个字符）。",
                metadata={
                    "command": "update",
                    "type": cached["type"],
                    "title": title or cached["title"],
                    "identifier": identifier,
                    "language": cached.get("language") or language,
                    "content": new_content,
                },
            )

        elif command == "rewrite":
            content = args.get("content", "")
            if not content:
                return ToolResult(error="'rewrite' 需要提供 'content' 参数。")

            cached = cache.get(identifier)
            if not cached:
                return ToolResult(
                    error=(
                        f"没有找到 identifier 为 '{identifier}' 的 artifact。"
                        "请先使用 'create' 命令。"
                    ),
                )

            cached["content"] = content
            if title:
                cached["title"] = title
            if artifact_type:
                cached["type"] = artifact_type

            return ToolResult(
                output=f"Artifact '{identifier}' 已重写。",
                metadata={
                    "command": "rewrite",
                    "type": artifact_type or cached["type"],
                    "title": title or cached["title"],
                    "identifier": identifier,
                    "language": cached.get("language") or language,
                    "content": content,
                },
            )

        else:
            return ToolResult(error=f"未知命令：'{command}'")
