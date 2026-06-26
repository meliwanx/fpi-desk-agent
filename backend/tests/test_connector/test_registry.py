"""Tests for app.connector.registry — MCP connector deduplication."""

from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from pathlib import Path
from unittest.mock import patch

from app.connector.registry import ConnectorRegistry


class RecordingMcpManager:
    def __init__(self) -> None:
        self._config = {}
        self.reconnect_calls = []

    async def reconnect(self, name: str) -> bool:
        self.reconnect_calls.append((name, dict(self._config.get(name, {}))))
        return name in self._config


class TestNormalizeUrl:
    def test_strips_trailing_slash(self):
        assert ConnectorRegistry._normalize_url("https://api.com/") == "https://api.com"

    def test_lowercases_host(self):
        assert ConnectorRegistry._normalize_url("https://API.COM/path") == "https://api.com/path"

    def test_preserves_path(self):
        assert ConnectorRegistry._normalize_url("https://api.com/v1/sse") == "https://api.com/v1/sse"

    def test_handles_no_path(self):
        assert ConnectorRegistry._normalize_url("https://api.com") == "https://api.com"


class TestRegisterFromPlugin:
    def _make_registry(self, tmp_path: Path) -> ConnectorRegistry:
        # Patch catalog loading to avoid missing data file
        with patch.object(ConnectorRegistry, "_load_catalog", return_value={}):
            return ConnectorRegistry(project_dir=str(tmp_path))

    def test_creates_connector(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        ids = reg.register_from_plugin("myplugin", {
            "sim-data-agent": {"url": "https://sim.example/mcp", "type": "remote"},
        })
        assert "sim-data-agent" in ids
        c = reg.get("sim-data-agent")
        assert c is not None
        assert c.url == "https://sim.example/mcp"

    def test_skips_bundled_connector_not_in_allowlist(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        ids = reg.register_from_plugin("myplugin", {
            "slack": {"url": "https://slack.mcp.io/sse", "type": "remote"},
        })
        assert ids == []
        assert reg.get("slack") is None

    def test_dedup_by_url(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        reg.register_from_plugin("plugin-a", {
            "sim-data-agent": {"url": "https://sim.example/mcp", "type": "remote"},
        })
        reg.register_from_plugin("plugin-b", {
            "sim-data-agent": {"url": "https://sim.example/mcp", "type": "remote"},
        })
        connectors = reg.list_connectors()
        sim_connectors = [c for c in connectors if c.id == "sim-data-agent"]
        assert len(sim_connectors) == 1
        assert "plugin-a" in sim_connectors[0].referenced_by
        assert "plugin-b" in sim_connectors[0].referenced_by

    def test_strips_namespace(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        ids = reg.register_from_plugin("eng", {
            "engineering:sim-data-agent": {"url": "https://sim.example/mcp", "type": "remote"},
        })
        assert "sim-data-agent" in ids

    def test_skips_remote_without_url(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        ids = reg.register_from_plugin("p", {
            "nourl": {"type": "remote"},
        })
        assert ids == []


class TestBuiltinCatalog:
    def test_registers_allowlisted_catalog_connectors_without_plugin(self, tmp_path: Path):
        with patch.object(
            ConnectorRegistry,
            "_load_catalog",
            return_value={
                "sim-data-agent": {
                    "name": "SIM 数据中台",
                    "url": "https://sim.example/mcp",
                    "description": "SIM connector",
                    "category": "data",
                    "icon_url": "/connectors/sim-data-agent.png",
                },
                "slack": {
                    "name": "Slack",
                    "url": "https://slack.example/mcp",
                },
            },
        ):
            reg = ConnectorRegistry(project_dir=str(tmp_path))

        sim = reg.get("sim-data-agent")
        assert sim is not None
        assert sim.name == "SIM 数据中台"
        assert sim.url == "https://sim.example/mcp"
        assert sim.enabled is False
        assert sim.source == "builtin"
        assert reg.get("slack") is None


class TestRegisterCustom:
    def _make_registry(self, tmp_path: Path) -> ConnectorRegistry:
        with patch.object(ConnectorRegistry, "_load_catalog", return_value={}):
            return ConnectorRegistry(project_dir=str(tmp_path))

    def test_creates_custom_connector(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        c = reg.register_custom("my-tool", "My Tool", "https://my.tool/sse")
        assert c.id == "my-tool"
        assert c.source == "custom"

    def test_duplicate_id_raises(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        reg.register_custom("my-tool", "My Tool", "https://my.tool/sse")
        with pytest.raises(ValueError):
            reg.register_custom("my-tool", "My Tool 2", "https://my.tool2/sse")

    @pytest.mark.asyncio
    async def test_custom_connector_syncs_to_mcp_config_before_enable(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        mcp_manager = RecordingMcpManager()
        reg._mcp_manager = mcp_manager

        reg.register_custom("my-tool", "My Tool", "https://my.tool/sse")

        assert mcp_manager._config["my-tool"] == {
            "type": "remote",
            "url": "https://my.tool/sse",
            "enabled": False,
        }

        assert await reg.enable("my-tool") is True
        assert mcp_manager.reconnect_calls == [
            (
                "my-tool",
                {
                    "type": "remote",
                    "url": "https://my.tool/sse",
                    "enabled": True,
                },
            )
        ]


class TestRemoveCustom:
    def _make_registry(self, tmp_path: Path) -> ConnectorRegistry:
        with patch.object(ConnectorRegistry, "_load_catalog", return_value={}):
            return ConnectorRegistry(project_dir=str(tmp_path))

    def test_removes_custom(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        reg.register_custom("my-tool", "My Tool", "https://my.tool/sse")
        assert reg.remove_custom("my-tool") is True
        assert reg.get("my-tool") is None

    def test_returns_false_for_builtin(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        reg.register_from_plugin("p", {"sim-data-agent": {"url": "https://sim.example/mcp", "type": "remote"}})
        assert reg.remove_custom("sim-data-agent") is False

    def test_returns_false_for_nonexistent(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        assert reg.remove_custom("nope") is False


class TestListAndGet:
    def _make_registry(self, tmp_path: Path) -> ConnectorRegistry:
        with patch.object(ConnectorRegistry, "_load_catalog", return_value={}):
            return ConnectorRegistry(project_dir=str(tmp_path))

    def test_list_sorted_by_name(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        reg.register_custom("zoom", "Zoom", "https://z.io")
        reg.register_custom("asana", "Asana", "https://a.io")
        reg.register_custom("slack", "Slack", "https://s.io")
        names = [c.name for c in reg.list_connectors()]
        assert names == ["Asana", "Slack", "Zoom"]

    def test_get_existing(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        reg.register_custom("my-tool", "My Tool", "https://my.tool/sse")
        assert reg.get("my-tool") is not None

    def test_get_nonexistent(self, tmp_path: Path):
        reg = self._make_registry(tmp_path)
        assert reg.get("nope") is None
