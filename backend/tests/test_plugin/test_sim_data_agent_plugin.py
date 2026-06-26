from __future__ import annotations

from pathlib import Path

from app.connector.registry import ConnectorRegistry
from app.plugin.loader import load_plugin


def test_project_sim_data_agent_plugin_declares_mcp_and_skill():
    repo_root = Path(__file__).resolve().parents[3]
    plugin_dir = repo_root / ".fpiagent" / "plugins" / "sim-data-agent"

    result = load_plugin(plugin_dir)

    assert not result.errors
    assert "sim-data-agent" in result.meta_map
    assert "sim-data-agent" in result.mcp_by_plugin
    assert result.mcp_by_plugin["sim-data-agent"]["sim-data-agent"]["url"].endswith(
        "/mcp/sim-data/mcp"
    )
    assert [skill.name for skill in result.skills] == ["sim-data-agent:data-tools"]
    assert "租户 3" in result.skills[0].content
    assert [agent.name for agent in result.agents] == ["sim-data-agent"]


def test_project_sim_data_agent_connector_uses_data_catalog_metadata(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    plugin_dir = repo_root / ".fpiagent" / "plugins" / "sim-data-agent"
    result = load_plugin(plugin_dir)
    registry = ConnectorRegistry(project_dir=str(tmp_path))

    registry.register_from_plugin(
        "sim-data-agent",
        result.mcp_by_plugin["sim-data-agent"],
    )

    connector = registry.get("sim-data-agent")
    assert connector is not None
    assert connector.name == "SIM 数据中台"
    assert connector.category == "data"
    assert connector.icon_url == "/connectors/sim-data-agent.png"
