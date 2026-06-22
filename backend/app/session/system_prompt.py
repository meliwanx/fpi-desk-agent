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
_SKILL_ROUTING_DESC_CHARS = 180


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
                    return f"# Project Instructions\n{content}"
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
        "# Skill Routing",
        "If the task matches one of the skills below, call the `skill` tool before major work.",
        "Use skills for specialised workflows or output-generation tasks. Do not load a skill just to read a file.",
        "",
        "Currently available skills:",
    ]

    shown = 0
    total = len(skills)
    for skill in skills:
        desc = _truncate((skill.description or "").strip(), _SKILL_ROUTING_DESC_CHARS)
        label = _skill_label(skill)
        line = f"- {label}: {desc}" if desc else f"- {label}"
        remaining_after = total - shown - 1
        reserve = (
            len(f"\n- (and {remaining_after} more available via the `skill` tool)")
            if remaining_after > 0
            else 0
        )
        if len("\n".join([*lines, line])) + reserve > _SKILL_ROUTING_BUDGET_CHARS:
            break
        lines.append(line)
        shown += 1

    remaining = total - shown
    if remaining > 0:
        summary = f"- (and {remaining} more available via the `skill` tool)"
        if len("\n".join([*lines, summary])) <= _SKILL_ROUTING_BUDGET_CHARS:
            lines.append(summary)

    return "\n".join(lines)


def _skill_label(skill: Any) -> str:
    display_name = getattr(skill, "display_name", None)
    if display_name and display_name != skill.name:
        return f"{skill.name} ({display_name})"
    return str(skill.name)


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


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

    section = f"""# Environment
- Working directory: {cwd}
- Platform: {platform_name}
- Current date: {today} ({current_time} {tz_name})
- Current year: {now.year}"""

    if workspace:
        output_dir = str(Path(workspace) / "openyak_written")
        section += f"""

# Workspace Access
The active workspace is: {workspace}
Use it as the default context for project files, relative paths, full-text `search`, \
and generated outputs. If the user asks about local computer state or a file is not \
found in the workspace, you may use read-only tools (`read`, `glob`, `grep`) or shell \
commands with explicit absolute paths to inspect other local locations.
File writes, edits, patches, and generated outputs must stay inside the workspace unless \
the user explicitly chooses a different workspace in a new chat.

# Default Output Directory
When creating new files and the user does not specify a location, \
place them in: {output_dir}
This directory is auto-created for you. Use it to keep generated files organized.
If the user explicitly specifies a different path (within the workspace), use that instead."""
    else:
        section += f"""

# File Reference Format
You are not restricted to a workspace for this session.
When referencing local files in your response, prefer absolute paths rooted from the working directory: {cwd}
Do not return relative paths like `src/main.py` when an absolute path is available.

# Full-Text Search
Full-text `search` is unavailable until the user selects a workspace folder.
When no workspace is selected, use `glob`, `grep`, `read`, or shell commands with explicit paths instead."""

    if fts_status:
        status = fts_status.get("status", "unknown")
        file_count = fts_status.get("file_count")
        count_str = f" ({file_count:,} files)" if file_count else ""
        if status == "indexed":
            section += f"""

# Full-Text Search
- FTS: enabled, workspace indexed{count_str}
- Full-text search available via `search` tool — use it for broad keyword discovery
- Use `grep` for exact regex pattern matching"""
        elif status == "indexing":
            section += """

# Full-Text Search
- FTS: enabled, workspace indexing in progress
- Full-text `search` tool will be available once indexing completes"""

    return section
