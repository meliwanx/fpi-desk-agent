"""Convert parsed Claude plugin data to fpi-agent registry objects."""

from __future__ import annotations

from app.plugin.parser import PluginMcpServer, PluginMeta, PluginSkillRaw
from app.schemas.agent import AgentInfo, PermissionRule, Ruleset
from app.skill.model import SkillInfo


def convert_skill(raw: PluginSkillRaw, plugin: PluginMeta) -> SkillInfo:
    """Convert a raw Claude plugin skill to an fpi-agent SkillInfo.

    Skills are namespaced as "{plugin}:{skill}" to avoid conflicts.
    """
    return SkillInfo(
        name=f"{plugin.name}:{raw.name}",
        description=raw.description,
        location=str(raw.path),
        content=raw.content,
        scope="plugin",
        source=f"plugin:{plugin.name}",
    )


def convert_mcp_servers(
    servers: list[PluginMcpServer], plugin_name: str
) -> dict[str, dict]:
    """Convert plugin MCP server entries to a flat dict.

    Keys are the raw server name (no plugin namespace) so that
    ConnectorRegistry can deduplicate across plugins.
    """
    result: dict[str, dict] = {}
    for server in servers:
        result[server.name] = {
            "type": "remote",
            "url": server.url,
            "enabled": False,
        }
    return result


def create_plugin_agent(plugin: PluginMeta, skill_names: list[str]) -> AgentInfo:
    """Create a subagent for a plugin, scoped to its skills.

    The agent's system prompt includes the plugin description and lists
    available skills so the LLM knows what domain tools it has.
    """
    skills_list = "\n".join(f"- `{name}`" for name in skill_names)
    prompt = (
        f"你是专用于 **{plugin.name}** 的助理。\n\n"
        f"{plugin.description}\n\n"
        f"## 可用技能\n\n"
        f"{skills_list}\n\n"
        f"需要时使用 `skill` 工具加载上面的技能。所有思考、计划和回复必须使用中文。"
    )

    return AgentInfo(
        name=plugin.name,
        description=plugin.description,
        mode="subagent",
        tools=[],  # All tools available
        permissions=Ruleset(rules=[
            PermissionRule(action="allow", permission="*"),
        ]),
        system_prompt=prompt,
        metadata={"plugin": True, "plugin_version": plugin.version},
    )
