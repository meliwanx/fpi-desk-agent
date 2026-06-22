"""Skill data model and SKILL.md frontmatter parser."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SkillInfo:
    """A discovered skill definition."""

    name: str
    description: str
    location: str  # Absolute path to SKILL.md
    content: str  # Markdown content after frontmatter
    scope: str = "project"
    source: str | None = None
    display_name: str | None = None
    short_description: str | None = None
    icon_small: str | None = None
    icon_large: str | None = None
    brand_color: str | None = None
    default_prompt: str | None = None
    allow_implicit_invocation: bool = True
    tool_dependencies: list[dict[str, Any]] = field(default_factory=list)
    metadata_path: str | None = None
    frontmatter: dict[str, Any] = field(default_factory=dict)


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split YAML frontmatter from markdown body.

    Returns (frontmatter_string, body_string).
    If no valid frontmatter delimiters found, returns (None, original_text).
    """
    if not text.startswith("---"):
        return None, text

    # Find the closing ---
    end = text.find("\n---", 3)
    if end == -1:
        return None, text

    frontmatter = text[3:end].strip()
    body = text[end + 4:].strip()  # skip past \n---
    return frontmatter, body


def parse_skill_file(
    path: Path,
    *,
    scope: str = "project",
    source: str | None = None,
) -> SkillInfo | None:
    """Parse a SKILL.md file into a SkillInfo.

    Returns None if the file cannot be parsed or lacks required fields.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        logger.debug("Cannot read skill file: %s", path)
        return None

    frontmatter_str, body = _split_frontmatter(text)
    if frontmatter_str is None:
        logger.debug("No frontmatter in %s", path)
        return None

    try:
        data = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as e:
        logger.warning("Invalid YAML in %s: %s", path, e)
        return None

    if not isinstance(data, dict):
        logger.debug("Frontmatter is not a mapping in %s", path)
        return None

    name = data.get("name")
    description = data.get("description")

    if not name or not isinstance(name, str):
        logger.debug("Missing or invalid 'name' in %s", path)
        return None
    if not description or not isinstance(description, str):
        logger.debug("Missing or invalid 'description' in %s", path)
        return None

    metadata = _read_openai_metadata(path.parent)
    interface = _mapping(metadata.get("interface"))
    policy = _mapping(metadata.get("policy"))
    dependencies = _mapping(metadata.get("dependencies"))

    return SkillInfo(
        name=name,
        description=description,
        location=str(path.resolve()),
        content=body,
        scope=scope,
        source=source or str(path.parent.resolve()),
        display_name=_string_value(interface.get("display_name") or interface.get("displayName") or data.get("display_name")),
        short_description=_string_value(interface.get("short_description") or interface.get("shortDescription") or data.get("short_description")),
        icon_small=_string_value(interface.get("icon_small") or interface.get("iconSmall")),
        icon_large=_string_value(interface.get("icon_large") or interface.get("iconLarge")),
        brand_color=_string_value(interface.get("brand_color") or interface.get("brandColor")),
        default_prompt=_string_value(interface.get("default_prompt") or interface.get("defaultPrompt")),
        allow_implicit_invocation=_bool_value(
            policy.get("allow_implicit_invocation")
            if "allow_implicit_invocation" in policy
            else policy.get("allowImplicitInvocation"),
            default=True,
        ),
        tool_dependencies=_tool_dependencies(dependencies.get("tools")),
        metadata_path=metadata.get("_path") if isinstance(metadata.get("_path"), str) else None,
        frontmatter=data,
    )


def _read_openai_metadata(skill_dir: Path) -> dict[str, Any]:
    """Read optional Codex-style agents/openai.yaml metadata."""
    path = skill_dir / "agents" / "openai.yaml"
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        logger.warning("Invalid OpenAI skill metadata in %s: %s", path, e)
        return {}
    if not isinstance(raw, dict):
        logger.warning("OpenAI skill metadata is not a mapping in %s", path)
        return {}
    raw["_path"] = str(path.resolve())
    return raw


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _bool_value(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "on"}:
            return True
        if lowered in {"false", "no", "0", "off"}:
            return False
    return default


def _tool_dependencies(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    deps: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            deps.append({"id": item.strip()})
        elif isinstance(item, dict):
            clean = {str(k): v for k, v in item.items() if isinstance(k, str)}
            if clean:
                deps.append(clean)
    return deps
