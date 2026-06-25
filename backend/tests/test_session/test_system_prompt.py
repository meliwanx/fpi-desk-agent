"""System prompt assembly — integration tests against real Agent prompts.

These tests exercise ``assemble`` against real agent definitions from
``AgentRegistry`` and the real skill registry, with file-system project
instructions where applicable. Pure-function tests with pinned inputs live
in ``test_prompt_assembler.py``.

Per ADR-0009 (PromptAssembler extraction).
"""

from datetime import datetime
from pathlib import Path

from app.dependencies import set_skill_registry
from app.skill.model import SkillInfo
from app.skill.registry import SkillRegistry
from app.agent.agent import AgentRegistry
from app.session.system_prompt import (
    active_skills_from_registry,
    assemble,
    load_project_instructions,
    render_skills_section,
)


_PINNED = {
    "now": datetime(2026, 5, 4, 15, 30, 0),
    "tz_name": "PDT",
    "platform_name": "Darwin",
    "cwd": "/test/cwd",
}


def _resolve_io(directory: str | None = None) -> dict:
    """Mirror SessionPrompt._build_system_prompt_parts I/O resolution."""
    return {
        "project_instructions": load_project_instructions(directory),
        "skills_summary": render_skills_section(active_skills_from_registry()),
    }


class TestSystemPrompt:
    def test_build_agent_has_prompt(self):
        ar = AgentRegistry()
        build = ar.get("build")
        parts = assemble(build, **_resolve_io(), **_PINNED)
        prompt = parts.as_plain_text()
        assert "聚光办公助理" in prompt
        assert "所有思考、推理、计划、摘要和最终回复都必须使用中文" in prompt
        assert "默认不要输出英文" in prompt
        assert "Yakyak" not in prompt
        assert "fpi-agent agent assistant" not in prompt

    def test_includes_environment(self):
        ar = AgentRegistry()
        build = ar.get("build")
        parts = assemble(build, **_resolve_io(), **_PINNED)
        prompt = parts.as_plain_text()
        assert "工作目录" in prompt
        assert "运行平台" in prompt
        assert "当前日期" in prompt

    def test_no_workspace_disables_full_text_search_guidance(self):
        ar = AgentRegistry()
        build = ar.get("build")
        parts = assemble(build, workspace=None, fts_status=None, **_resolve_io(), **_PINNED)
        prompt = parts.as_plain_text()
        assert "用户选择工作区文件夹之前，全文 `search` 不可用。" in prompt

    def test_plan_agent_prompt(self):
        ar = AgentRegistry()
        plan = ar.get("plan")
        parts = assemble(plan, **_resolve_io(), **_PINNED)
        prompt = parts.as_plain_text()
        assert "计划模式" in prompt
        assert "只读" in prompt

    def test_with_project_instructions(self, tmp_path: Path):
        instructions = tmp_path / "AGENTS.md"
        instructions.write_text("# 自定义指令\n执行甲和乙。")

        ar = AgentRegistry()
        build = ar.get("build")
        pinned = {**_PINNED, "cwd": str(tmp_path)}
        parts = assemble(build, **_resolve_io(str(tmp_path)), **pinned)
        prompt = parts.as_plain_text()
        assert "自定义指令" in prompt
        assert "执行甲和乙" in prompt

    def test_without_project_instructions(self, tmp_path: Path):
        ar = AgentRegistry()
        build = ar.get("build")
        pinned = {**_PINNED, "cwd": str(tmp_path)}
        parts = assemble(build, **_resolve_io(str(tmp_path)), **pinned)
        prompt = parts.as_plain_text()
        assert "项目指令" not in prompt

    def test_cached_parts_separate_static_from_dynamic(self):
        ar = AgentRegistry()
        build = ar.get("build")
        parts = assemble(build, **_resolve_io(), **_PINNED)
        # Agent base prompt is in cached section
        assert "聚光办公助理" in parts.cached
        # Environment info is in dynamic section
        assert "工作目录" in parts.dynamic

    def test_as_cached_blocks_format(self):
        ar = AgentRegistry()
        build = ar.get("build")
        parts = assemble(build, **_resolve_io(), **_PINNED)
        blocks = parts.as_cached_blocks()
        assert len(blocks) == 2
        # First block (cached) has cache_control
        assert blocks[0]["type"] == "text"
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}
        # Second block (dynamic) has no cache_control
        assert blocks[1]["type"] == "text"
        assert "cache_control" not in blocks[1]

    def test_includes_skill_routing_when_skills_available(self, tmp_path: Path):
        skills_dir = tmp_path / ".openyak" / "skills" / "sheet-helper"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: sheet-helper\ndescription: Helps with spreadsheet workflows.\n---\nUse for sheets.",
            encoding="utf-8",
        )

        registry = SkillRegistry(project_dir=str(tmp_path))
        registry.scan(project_dir=str(tmp_path))
        set_skill_registry(registry)

        ar = AgentRegistry()
        build = ar.get("build")
        parts = assemble(build, **_resolve_io(), **_PINNED)

        assert "技能路由" in parts.dynamic
        assert "sheet-helper" in parts.dynamic

    def test_skill_routing_skips_non_implicit_skills(self):
        section = render_skills_section([
            SkillInfo(
                name="manual-only",
                description="Only load when explicitly requested.",
                location="/tmp/manual/SKILL.md",
                content="manual",
                allow_implicit_invocation=False,
            ),
            SkillInfo(
                name="auto-skill",
                description="Can be routed automatically.",
                location="/tmp/auto/SKILL.md",
                content="auto",
            ),
        ])

        assert section is not None
        assert "auto-skill" in section
        assert "manual-only" not in section

    def test_skill_routing_respects_context_budget(self):
        skills = [
            SkillInfo(
                name=f"skill-{i:03d}",
                description="x" * 500,
                location=f"/tmp/skill-{i}/SKILL.md",
                content="body",
            )
            for i in range(200)
        ]

        section = render_skills_section(skills)

        assert section is not None
        assert len(section) <= 8_000
        assert "skill-199" in section
        assert "more available via the `skill` tool" not in section
