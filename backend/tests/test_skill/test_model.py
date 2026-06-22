"""Tests for skill model and frontmatter parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.skill.model import SkillInfo, parse_skill_file, _split_frontmatter


# ---------------------------------------------------------------------------
# _split_frontmatter
# ---------------------------------------------------------------------------


class TestSplitFrontmatter:
    def test_valid_frontmatter(self):
        text = "---\nname: test\ndescription: hello\n---\nBody content here"
        fm, body = _split_frontmatter(text)
        assert fm == "name: test\ndescription: hello"
        assert body == "Body content here"

    def test_no_frontmatter(self):
        text = "Just regular markdown\nwith multiple lines"
        fm, body = _split_frontmatter(text)
        assert fm is None
        assert body == text

    def test_unclosed_frontmatter(self):
        text = "---\nname: test\nNo closing delimiter"
        fm, body = _split_frontmatter(text)
        assert fm is None
        assert body == text

    def test_empty_frontmatter(self):
        text = "---\n---\nBody only"
        fm, body = _split_frontmatter(text)
        assert fm == ""
        assert body == "Body only"

    def test_frontmatter_with_blank_body(self):
        text = "---\nname: test\n---\n"
        fm, body = _split_frontmatter(text)
        assert fm == "name: test"
        assert body == ""


# ---------------------------------------------------------------------------
# parse_skill_file
# ---------------------------------------------------------------------------


class TestParseSkillFile:
    def test_valid_skill(self, tmp_path: Path):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\nname: test-skill\ndescription: A test skill.\n---\n\n# Content\nHello world",
            encoding="utf-8",
        )
        skill = parse_skill_file(skill_file)
        assert skill is not None
        assert skill.name == "test-skill"
        assert skill.description == "A test skill."
        assert "# Content" in skill.content
        assert "Hello world" in skill.content
        assert skill.location == str(skill_file.resolve())

    def test_missing_name(self, tmp_path: Path):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\ndescription: No name field.\n---\nContent",
            encoding="utf-8",
        )
        assert parse_skill_file(skill_file) is None

    def test_missing_description(self, tmp_path: Path):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\nname: no-desc\n---\nContent",
            encoding="utf-8",
        )
        assert parse_skill_file(skill_file) is None

    def test_no_frontmatter(self, tmp_path: Path):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("# Just markdown\nNo frontmatter.", encoding="utf-8")
        assert parse_skill_file(skill_file) is None

    def test_invalid_yaml(self, tmp_path: Path):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\n: invalid: yaml: {{{\n---\nContent",
            encoding="utf-8",
        )
        assert parse_skill_file(skill_file) is None

    def test_nonexistent_file(self, tmp_path: Path):
        assert parse_skill_file(tmp_path / "does_not_exist.md") is None

    def test_frontmatter_not_a_dict(self, tmp_path: Path):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\n- just\n- a\n- list\n---\nContent",
            encoding="utf-8",
        )
        assert parse_skill_file(skill_file) is None

    def test_name_not_string(self, tmp_path: Path):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\nname: 123\ndescription: Number name.\n---\nContent",
            encoding="utf-8",
        )
        # 123 is an int, not a string
        assert parse_skill_file(skill_file) is None

    def test_parse_codex_openai_metadata(self, tmp_path: Path):
        skill_dir = tmp_path / "sheet-helper"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\nname: sheet-helper\ndescription: Helps with spreadsheets.\n---\n\n# Use sheets",
            encoding="utf-8",
        )
        metadata_dir = skill_dir / "agents"
        metadata_dir.mkdir()
        (metadata_dir / "openai.yaml").write_text(
            """
interface:
  display_name: Sheet Helper
  short_description: Spreadsheet workflows
  icon_small: icons/small.png
  icon_large: icons/large.png
  brand_color: "#1455cc"
  default_prompt: Review the workbook.
policy:
  allow_implicit_invocation: false
dependencies:
  tools:
    - id: spreadsheets
      reason: Read workbook files
    - name: shell
""".strip(),
            encoding="utf-8",
        )

        skill = parse_skill_file(skill_file, scope="user", source="~/.agents/skills")

        assert skill is not None
        assert skill.display_name == "Sheet Helper"
        assert skill.short_description == "Spreadsheet workflows"
        assert skill.icon_small == "icons/small.png"
        assert skill.icon_large == "icons/large.png"
        assert skill.brand_color == "#1455cc"
        assert skill.default_prompt == "Review the workbook."
        assert skill.allow_implicit_invocation is False
        assert skill.scope == "user"
        assert skill.source == "~/.agents/skills"
        assert skill.metadata_path == str((metadata_dir / "openai.yaml").resolve())
        assert skill.tool_dependencies == [
            {"id": "spreadsheets", "reason": "Read workbook files"},
            {"name": "shell"},
        ]

    def test_invalid_openai_metadata_is_ignored(self, tmp_path: Path):
        skill_dir = tmp_path / "plain"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\nname: plain\ndescription: Plain skill.\n---\nContent",
            encoding="utf-8",
        )
        metadata_dir = skill_dir / "agents"
        metadata_dir.mkdir()
        (metadata_dir / "openai.yaml").write_text(
            "interface: [not: valid: yaml", encoding="utf-8"
        )

        skill = parse_skill_file(skill_file)

        assert skill is not None
        assert skill.allow_implicit_invocation is True
        assert skill.display_name is None
        assert skill.tool_dependencies == []
