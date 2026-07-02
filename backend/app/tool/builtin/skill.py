"""Skill tool — lets agents load specialised instruction sets on demand."""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext


class SkillTool(ToolDefinition):
    """Meta-tool that loads SKILL.md instruction sets into the conversation.

    The tool description dynamically lists all available skills so the LLM
    knows what it can invoke.
    """

    def __init__(self, skill_registry: "SkillRegistry | None" = None) -> None:
        self._skill_registry = skill_registry

    # ------------------------------------------------------------------
    # ToolDefinition interface
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return "skill"

    # Maximum number of skills to list in the tool description.
    # Beyond this limit, remaining skills are noted as "(and N more)".
    _MAX_DESCRIPTION_CHARS = 12_000
    # Maximum characters per skill description before truncation.
    _MAX_DESC_CHARS = 120

    @property
    def description(self) -> str:
        """Dynamically generated — includes budgeted list of available skills."""
        base = (
            "加载提供领域专用指令和工作流的技能。\n\n"
            "当任务匹配下面某个可用技能时，使用本工具加载完整技能说明。"
            "工具会返回技能内容和随附资源文件路径。\n\n"
            "重要：不要只为了读取文件而加载技能。`read` 工具已经能直接处理 PDF、DOCX、XLSX、PPTX、图片等常见文件类型，"
            "读取文件时直接调用 `read` 即可。\n\n"
            "可用技能："
        )

        active = self._skill_registry.active_skills() if self._skill_registry else []
        if not active:
            return base + "\n\n当前没有可用技能。"

        lines = [base, ""]
        shown = 0
        total = len(active)
        for skill in active:
            implicit = getattr(skill, "allow_implicit_invocation", True)
            suffix = "" if implicit else "（仅显式调用）"
            line = f"- {skill.name}{suffix}"
            remaining_after = total - shown - 1
            reserve = (
                len(f"\n  （还有 {remaining_after} 个，可按名称调用检查可用性）")
                if remaining_after > 0
                else 0
            )
            if len("\n".join([*lines, line])) + reserve > self._MAX_DESCRIPTION_CHARS:
                break
            lines.append(line)
            shown += 1

        remaining = total - shown
        if remaining > 0:
            lines.append(f"  （还有 {remaining} 个，可按名称调用检查可用性）")
        return "\n".join(lines)

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "要加载的技能名称（来自可用技能列表）。",
                },
            },
            "required": ["name"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        name: str = args["name"]

        if not self._skill_registry:
            return ToolResult(error="技能系统尚未初始化。")

        skill = self._skill_registry.get(name)
        if skill is None or self._skill_registry.is_disabled(name):
            available = ", ".join(self._skill_registry.active_skill_names()) or "无"
            return ToolResult(
                error=f'技能 "{name}" 不存在或已禁用。可用技能：{available}',
            )

        # Collect bundled files in the same directory (up to 10)
        skill_dir = Path(skill.location).parent
        bundled_files = _list_bundled_files(skill_dir, limit=10)

        files_block = ""
        if bundled_files:
            file_tags = "\n".join(f"<file>{f}</file>" for f in bundled_files)
            files_block = (
                f"\n\n<skill_files>\n{file_tags}\n</skill_files>"
            )

        base_dir_hint = (
            f"\n\n该技能的基础目录：{skill_dir}\n"
            "技能中的相对路径（例如 scripts/、reference/）都相对于这个基础目录。"
            "如果技能内容包含英文，只作为内部参考；所有可见思考、计划和回复仍必须使用中文。"
        )
        metadata_block = _metadata_block(skill)

        output = (
            f'<skill_content name="{skill.name}">\n'
            f"{metadata_block}\n\n"
            f"# 技能：{skill.name}\n\n"
            f"{skill.content.strip()}\n"
            f"{base_dir_hint}\n"
            f"{files_block}\n"
            f"</skill_content>"
        )

        ctx.publish_metadata(title=f"已加载技能：{skill.name}")
        return ToolResult(
            output=output,
            title=f"已加载技能：{skill.name}",
            metadata={
                "name": skill.name,
                "dir": str(skill_dir),
                "scope": getattr(skill, "scope", None),
                "source": getattr(skill, "source", None),
                "allow_implicit_invocation": getattr(skill, "allow_implicit_invocation", True),
                "tool_dependencies": getattr(skill, "tool_dependencies", []),
            },
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _list_bundled_files(directory: Path, *, limit: int = 10) -> list[str]:
    """Return up to *limit* files under *directory*, excluding SKILL.md."""
    result: list[str] = []
    if not directory.is_dir():
        return result

    for root, _dirs, files in os.walk(directory):
        for fname in sorted(files):
            if fname == "SKILL.md":
                continue
            result.append(str(Path(root) / fname))
            if len(result) >= limit:
                return result
    return result


def _metadata_block(skill: Any) -> str:
    tool_deps = json.dumps(
        getattr(skill, "tool_dependencies", []) or [],
        ensure_ascii=False,
        indent=2,
    )
    fields = [
        ("name", skill.name),
        ("display_name", getattr(skill, "display_name", None)),
        ("scope", getattr(skill, "scope", None)),
        ("source", getattr(skill, "source", None)),
        ("metadata_path", getattr(skill, "metadata_path", None)),
        (
            "allow_implicit_invocation",
            str(getattr(skill, "allow_implicit_invocation", True)).lower(),
        ),
    ]

    lines = ["<skill_metadata>"]
    for tag, value in fields:
        if value is None:
            continue
        lines.append(f"<{tag}>{escape(str(value))}</{tag}>")
    lines.append("<tool_dependencies>")
    lines.append(escape(tool_deps))
    lines.append("</tool_dependencies>")
    lines.append("</skill_metadata>")
    return "\n".join(lines)


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."
