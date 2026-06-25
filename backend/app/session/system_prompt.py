"""System prompt assembly.

``assemble`` is a pure function: every input is supplied by the caller. It
performs no filesystem reads, no skill-registry lookups, and no clock or
platform calls. Callers (today: ``SessionPrompt``) resolve the impure
inputs upstream — project instructions from disk, the active skill list
from the registry, the wall-clock time, the timezone name, the platform
name, and the working directory — then hand them in.

Resolve helpers exposed publicly: ``load_project_instructions``,
``render_skills_section``, ``active_skills_from_registry``,
``default_tz_name``.

Per ADR-0009 (PromptAssembler extraction).
"""

from __future__ import annotations

import os
import platform as _platform
import time as _time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from app.schemas.agent import AgentInfo

_SKILL_ROUTING_BUDGET_CHARS = 8_000


@dataclass(frozen=True)
class SystemPromptParts:
    """System prompt split into cached (static) and dynamic sections.

    Semantically equivalent to ADR-0009's ``list[SystemPart]`` of length two —
    the cached segment plus the dynamic segment. ``as_cached_blocks()``
    materialises the list-of-dict form expected by ``BaseProvider.stream_chat``
    and Anthropic prompt caching.
    """

    cached: str
    dynamic: str

    def as_plain_text(self) -> str:
        """Join both parts into a single string (for non-caching providers)."""
        parts = [p for p in (self.cached, self.dynamic) if p]
        return "\n\n".join(parts)

    def as_cached_blocks(self) -> list[dict[str, Any]]:
        """Format as Anthropic system message blocks with cache_control.

        The cached block gets a ``cache_control`` marker so it is stored
        server-side and reused across turns within the same session.
        """
        blocks: list[dict[str, Any]] = []
        if self.cached:
            blocks.append({
                "type": "text",
                "text": self.cached,
                "cache_control": {"type": "ephemeral"},
            })
        if self.dynamic:
            blocks.append({
                "type": "text",
                "text": self.dynamic,
            })
        return blocks


def assemble(
    agent: AgentInfo,
    *,
    cwd: str,
    workspace: str | None = None,
    fts_status: dict | None = None,
    workspace_memory_section: str | None = None,
    project_instructions: str | None = None,
    skills_summary: str | None = None,
    now: datetime,
    tz_name: str,
    platform_name: str,
) -> SystemPromptParts:
    """Assemble the system prompt from caller-resolved inputs.

    Pure: no filesystem reads, no registry lookups, no clock or platform
    calls. The caller supplies every value, including ``cwd`` (typically
    ``self.directory or os.getcwd()``). Use the module's resolve helpers
    (:func:`load_project_instructions`, :func:`render_skills_section`,
    :func:`active_skills_from_registry`, :func:`default_tz_name`) to gather
    the inputs.

    Tests pin all inputs to assert exact output.
    """
    cached_parts: list[str] = []

    if agent.system_prompt:
        cached_parts.append(agent.system_prompt)

    if project_instructions:
        cached_parts.append(project_instructions)

    dynamic_parts: list[str] = []

    if workspace_memory_section:
        dynamic_parts.append(workspace_memory_section)

    if skills_summary:
        dynamic_parts.append(skills_summary)

    env_info = _environment_section(
        cwd=cwd,
        workspace=workspace,
        fts_status=fts_status,
        now=now,
        tz_name=tz_name,
        platform_name=platform_name,
    )
    dynamic_parts.append(env_info)

    return SystemPromptParts(
        cached="\n\n".join(cached_parts),
        dynamic="\n\n".join(dynamic_parts),
    )


def default_tz_name() -> str:
    """Return the local timezone name, matching the existing prompt's format."""
    return _time.tzname[_time.daylight] if _time.daylight else _time.tzname[0]


def default_platform_name() -> str:
    """Return the OS platform name."""
    return _platform.system()


def load_project_instructions(directory: str | None) -> str | None:
    """Load project-specific instructions from conventional locations.

    Returns the formatted ``# Project Instructions`` section or ``None`` if
    no instruction file is found. Public helper — callers resolve this and
    pass the result to :func:`assemble`.
    """
    if not directory:
        return None

    candidates = [
        os.path.join(directory, "AGENTS.md"),
        os.path.join(directory, ".openyak", "instructions.md"),
        os.path.join(directory, ".openyak", "instructions"),
    ]

    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    return f"# 项目指令\n{content}"
            except OSError:
                continue

    return None


def render_skills_section(active_skills: Iterable[Any]) -> str | None:
    """Render the skill-routing section from a sorted list of active skills.

    Each skill must expose ``.name`` and ``.description`` attributes. Returns
    ``None`` when no skills are active. Public helper — callers fetch the
    skill list (e.g. via :func:`active_skills_from_registry`) and pass it
    to :func:`assemble`.

    The list is duplicated in the system prompt because many models route
    better when relevant capabilities are surfaced there in addition to the
    skill tool's own description.
    """
    skills = [
        skill
        for skill in active_skills
        if getattr(skill, "allow_implicit_invocation", True)
    ]
    if not skills:
        return None

    lines = [
        "# 技能路由",
        "如果任务匹配下面任一技能，请在主要工作前调用 `skill` 工具。",
        "技能用于专业工作流或输出生成任务；不要只为了读取文件而加载技能。",
        "",
        "当前可用技能：",
    ]

    shown = 0
    total = len(skills)
    for skill in skills:
        label = _skill_label(skill)
        line = f"- {label}"
        remaining_after = total - shown - 1
        reserve = (
            len(f"\n- （还有 {remaining_after} 个技能可通过 `skill` 工具加载）")
            if remaining_after > 0
            else 0
        )
        if len("\n".join([*lines, line])) + reserve > _SKILL_ROUTING_BUDGET_CHARS:
            break
        lines.append(line)
        shown += 1

    remaining = total - shown
    if remaining > 0:
        summary = f"- （还有 {remaining} 个技能可通过 `skill` 工具加载）"
        if len("\n".join([*lines, summary])) <= _SKILL_ROUTING_BUDGET_CHARS:
            lines.append(summary)

    return "\n".join(lines)


def _skill_label(skill: Any) -> str:
    display_name = getattr(skill, "display_name", None)
    if display_name and display_name != skill.name:
        return f"{skill.name} ({display_name})"
    return str(skill.name)


def active_skills_from_registry() -> list[Any]:
    """Best-effort fetch of currently active skills, sorted by name.

    Returns an empty list if the registry is unavailable.
    """
    try:
        from app.dependencies import get_skill_registry

        registry = get_skill_registry()
        return sorted(registry.active_skills(), key=lambda s: s.name.lower())
    except Exception:
        return []


def _environment_section(
    *,
    cwd: str,
    workspace: str | None,
    fts_status: dict | None,
    now: datetime,
    tz_name: str,
    platform_name: str,
) -> str:
    """Render the environment section from already-resolved values."""
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    section = f"""# 环境信息
- 工作目录：{cwd}
- 运行平台：{platform_name}
- 当前日期：{today}（{current_time} {tz_name}）
- 当前年份：{now.year}
- 语言要求：所有思考、推理、计划、摘要和最终回复都必须使用中文。除代码、命令、路径、文件名、接口字段、JSON/XML 标签、工具名、模型名、品牌名、专有名词和引用原文外，默认不要输出英文。"""

    if workspace:
        output_dir = str(Path(workspace) / "openyak_written")
        section += f"""

# 工作区访问
当前工作区是：{workspace}
默认将它作为项目文件、相对路径、全文 `search` 和生成输出的上下文。如果用户询问本地电脑状态，或文件不在工作区内，可以使用只读工具（`read`、`glob`、`grep`）或带明确绝对路径的 shell 命令检查其他本地位置。
除非用户在新对话中明确选择其他工作区，否则写入、编辑、补丁和生成输出都必须留在当前工作区内。

# 默认输出目录
如果创建新文件且用户没有指定位置，请放在：{output_dir}
该目录会自动创建，用于保持生成文件有序。如果用户明确指定工作区内其他路径，则使用用户指定路径。"""
    else:
        section += f"""

# 文件引用格式
本次会话没有绑定工作区。
回复中引用本地文件时，优先使用从工作目录开始的绝对路径：{cwd}
如果可以提供绝对路径，不要只返回类似 `src/main.py` 的相对路径。

# 全文搜索
用户选择工作区文件夹之前，全文 `search` 不可用。
没有工作区时，请改用 `glob`、`grep`、`read` 或带明确路径的 shell 命令。"""

    if fts_status:
        status = fts_status.get("status", "unknown")
        file_count = fts_status.get("file_count")
        count_str = f"（{file_count:,} 个文件）" if file_count else ""
        if status == "indexed":
            section += f"""

# 全文搜索
- FTS：已启用，工作区已建立索引{count_str}
- 可以通过 `search` 工具进行全文搜索，适合宽泛关键词发现
- 精确正则匹配仍使用 `grep`"""
        elif status == "indexing":
            section += """

# 全文搜索
- FTS：已启用，工作区正在建立索引
- 索引完成后即可使用全文 `search` 工具"""

    return section
