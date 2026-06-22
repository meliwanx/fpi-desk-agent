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
            "Load a specialised skill that provides domain-specific "
            "instructions and workflows.\n\n"
            "When you recognise that a task matches one of the available "
            "skills listed below, use this tool to load the full skill "
            "instructions. The skill content and bundled resource file "
            "paths will be returned.\n\n"
            "IMPORTANT: Do NOT load a skill just to read a file. The `read` "
            "tool already handles ALL file types natively (PDF, DOCX, XLSX, "
            "PPTX, images, etc.). Simply call `read` directly — no skill "
            "needed.\n\n"
            "Available skills:"
        )

        active = self._skill_registry.active_skills() if self._skill_registry else []
        if not active:
            return base + "\n\nNo skills are currently available."

        lines = [base, ""]
        shown = 0
        total = len(active)
        for skill in active:
            desc = _truncate(skill.description or "", self._MAX_DESC_CHARS)
            implicit = getattr(skill, "allow_implicit_invocation", True)
            suffix = "" if implicit else " [explicit only]"
            line = f"- {skill.name}{suffix}: {desc}"
            remaining_after = total - shown - 1
            reserve = (
                len(f"\n  (and {remaining_after} more — invoke by name to check availability)")
                if remaining_after > 0
                else 0
            )
            if len("\n".join([*lines, line])) + reserve > self._MAX_DESCRIPTION_CHARS:
                break
            lines.append(line)
            shown += 1

        remaining = total - shown
        if remaining > 0:
            lines.append(f"  (and {remaining} more — invoke by name to check availability)")
        return "\n".join(lines)

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the skill to load (from available_skills).",
                },
            },
            "required": ["name"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        name: str = args["name"]

        if not self._skill_registry:
            return ToolResult(error="Skill system is not initialised.")

        skill = self._skill_registry.get(name)
        if skill is None or self._skill_registry.is_disabled(name):
            available = ", ".join(self._skill_registry.active_skill_names()) or "none"
            return ToolResult(
                error=f'Skill "{name}" not found or disabled. Available skills: {available}',
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
            f"\n\nBase directory for this skill: {skill_dir}\n"
            "Relative paths in this skill (e.g., scripts/, reference/) "
            "are relative to this base directory."
        )
        metadata_block = _metadata_block(skill)

        output = (
            f'<skill_content name="{skill.name}">\n'
            f"{metadata_block}\n\n"
            f"# Skill: {skill.name}\n\n"
            f"{skill.content.strip()}\n"
            f"{base_dir_hint}\n"
            f"{files_block}\n"
            f"</skill_content>"
        )

        ctx.publish_metadata(title=f"Loaded skill: {skill.name}")
        return ToolResult(
            output=output,
            title=f"Loaded skill: {skill.name}",
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
        ("description", skill.description),
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
