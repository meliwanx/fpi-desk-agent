"""Tests for the SkillTool."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from app.schemas.agent import AgentInfo, Ruleset
from app.skill.registry import SkillRegistry
from app.tool.builtin.skill import SkillTool
from app.tool.context import ToolContext


def _make_ctx() -> ToolContext:
    """Create a minimal ToolContext for testing."""
    return ToolContext(
        session_id="test-session",
        message_id="msg-1",
        agent=AgentInfo(name="build", description="test agent", mode="primary"),
        call_id="call-1",
    )


class TestSkillToolProperties:
    def test_id(self):
        tool = SkillTool()
        assert tool.id == "skill"

    def test_description_no_skills(self):
        tool = SkillTool()
        assert "当前没有可用技能" in tool.description

    def test_description_no_registry(self):
        tool = SkillTool(skill_registry=None)
        assert "当前没有可用技能" in tool.description

    def test_description_with_skills(self, tmp_path: Path):
        skills_dir = tmp_path / ".fpiagent" / "skills" / "test-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: A test.\n---\nContent",
            encoding="utf-8",
        )
        registry = SkillRegistry()
        registry.scan(project_dir=str(tmp_path))

        tool = SkillTool(skill_registry=registry)
        desc = tool.description

        assert "test-skill" in desc
        assert "A test." not in desc

    def test_parameters_schema(self):
        tool = SkillTool()
        schema = tool.parameters_schema()
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "name" in schema["required"]


class TestSkillToolExecute:
    @pytest.mark.asyncio
    async def test_execute_loads_skill(self, tmp_path: Path):
        skills_dir = tmp_path / ".fpiagent" / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: 我的技能。\n---\n\n# 技能正文\n这里是指令。",
            encoding="utf-8",
        )
        registry = SkillRegistry()
        registry.scan(project_dir=str(tmp_path))

        tool = SkillTool(skill_registry=registry)
        result = await tool.execute({"name": "my-skill"}, _make_ctx())

        assert result.success
        assert '<skill_content name="my-skill">' in result.output
        assert "# 技能正文" in result.output
        assert "这里是指令。" in result.output
        assert result.title == "已加载技能：my-skill"

    @pytest.mark.asyncio
    async def test_execute_skill_not_found(self):
        registry = SkillRegistry()
        registry.scan()

        tool = SkillTool(skill_registry=registry)
        result = await tool.execute({"name": "nonexistent"}, _make_ctx())

        assert not result.success
        assert "不存在或已禁用" in result.error

    @pytest.mark.asyncio
    async def test_execute_no_registry(self):
        tool = SkillTool(skill_registry=None)
        result = await tool.execute({"name": "anything"}, _make_ctx())

        assert not result.success
        assert "尚未初始化" in result.error

    @pytest.mark.asyncio
    async def test_execute_lists_bundled_files(self, tmp_path: Path):
        skills_dir = tmp_path / ".fpiagent" / "skills" / "rich-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: rich-skill\ndescription: Has extra files.\n---\n\nMain content.",
            encoding="utf-8",
        )
        # Create a bundled reference file
        (skills_dir / "reference.md").write_text("Extra reference.", encoding="utf-8")

        registry = SkillRegistry()
        registry.scan(project_dir=str(tmp_path))

        tool = SkillTool(skill_registry=registry)
        result = await tool.execute({"name": "rich-skill"}, _make_ctx())

        assert result.success
        assert "<skill_files>" in result.output
        assert "reference.md" in result.output

    @pytest.mark.asyncio
    async def test_execute_includes_codex_metadata(self, tmp_path: Path):
        skills_dir = tmp_path / ".agents" / "skills" / "metadata-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: metadata-skill\ndescription: Has metadata.\n---\n\nMain content.",
            encoding="utf-8",
        )
        metadata_dir = skills_dir / "agents"
        metadata_dir.mkdir()
        (metadata_dir / "openai.yaml").write_text(
            """
interface:
  display_name: Metadata Skill
policy:
  allow_implicit_invocation: false
dependencies:
  tools:
    - id: spreadsheet
      reason: Read spreadsheet files
""".strip(),
            encoding="utf-8",
        )

        registry = SkillRegistry()
        registry.scan(project_dir=str(tmp_path))

        tool = SkillTool(skill_registry=registry)
        result = await tool.execute({"name": "metadata-skill"}, _make_ctx())

        assert result.success
        assert "<skill_metadata>" in result.output
        assert "<scope>repo</scope>" in result.output
        assert "<display_name>Metadata Skill</display_name>" in result.output
        assert "<allow_implicit_invocation>false</allow_implicit_invocation>" in result.output
        assert '"id": "spreadsheet"' in result.output
        assert result.metadata["scope"] == "repo"
        assert result.metadata["allow_implicit_invocation"] is False
