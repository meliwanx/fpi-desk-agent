"""Tests for connector management API endpoints."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.company_auth.store import (
    CompanyConnectorPolicy,
    CompanyConnectorPolicyEntry,
)
from app.connector import access as connector_access
from app.connector.access import tool_registry_for_request
from app.company_auth.store import CompanyUser
from app.mcp.tool_wrapper import McpToolWrapper
from app.tool.base import ToolDefinition, ToolResult
from app.tool.builtin.tool_search import ToolSearchTool
from app.tool.registry import ToolRegistry

pytestmark = pytest.mark.asyncio


@pytest.fixture
def _mock_cr(app_client):
    """Inject a richer mock ConnectorRegistry."""
    cr = MagicMock()
    cr.status.return_value = {
        "github": {"status": "connected", "error": None, "type": "remote", "tools": 3},
        "slack": {"status": "needs_auth", "error": None, "type": "remote", "tools": 0},
    }
    cr.enable = AsyncMock(return_value=True)
    cr.disable = AsyncMock(return_value=True)
    cr.reconnect = AsyncMock(return_value=True)
    cr.connect = AsyncMock(return_value={"auth_url": "https://ex.com/auth", "state": "abc"})
    cr.complete_auth = AsyncMock(return_value=True)
    cr.disconnect = AsyncMock(return_value=True)
    cr.get.return_value = MagicMock(enabled=True)
    cr.mcp_manager = MagicMock(_clients={}, _token_store=MagicMock())

    conn = MagicMock()
    conn.to_dict.return_value = {"id": "c1", "name": "Custom"}
    cr.register_custom.return_value = conn
    cr.remove_custom.return_value = True

    app_client.app.state.connector_registry = cr
    return cr


class _ConnectorPolicyStore:
    def __init__(self, allowed: set[str]) -> None:
        self.allowed = allowed

    async def is_connector_allowed(self, connector_id: str, user_id: str) -> bool:
        return user_id == "user-1" and connector_id in self.allowed


class _RuntimeConnectorPolicyStore:
    async def get_session_user(self, token: str):
        if token != "company-token":
            return None
        return CompanyUser(
            id="user-1",
            email="user@example.com",
            display_name="User One",
            role="user",
            is_active=True,
        )

    async def get_connector_policy(self):
        return CompanyConnectorPolicy(
            connectors=[
                CompanyConnectorPolicyEntry(
                    connector_id="github",
                    allowed_user_ids=["other-user"],
                ),
                CompanyConnectorPolicyEntry(
                    connector_id="slack",
                    allowed_user_ids=["user-1"],
                ),
            ]
        )


def _inject_company_user(app_client, *, allowed: set[str]) -> None:
    app_client.app.state.company_auth_store = _ConnectorPolicyStore(allowed)
    app_client.app.middleware_stack = None

    async def inject_user(request, call_next):
        request.state.company_user = CompanyUser(
            id="user-1",
            email="user@example.com",
            display_name="User One",
            role="user",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_user)


class _BasicTool(ToolDefinition):
    @property
    def id(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "Read files"

    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, args: dict, ctx):
        return ToolResult(output="ok")


def _mcp_tool(connector_id: str, tool_name: str) -> McpToolWrapper:
    client = MagicMock()
    client.name = connector_id
    client.tool_id.side_effect = lambda name: f"{connector_id}_{name}".replace("-", "_")
    mcp_tool = MagicMock()
    mcp_tool.name = tool_name
    mcp_tool.description = f"{connector_id} {tool_name}"
    mcp_tool.inputSchema = {"type": "object", "properties": {}}
    return McpToolWrapper(client, mcp_tool)


async def test_request_tool_registry_filters_unauthorized_mcp_tools(app_client):
    registry = ToolRegistry()
    sim_tool = _mcp_tool("sim-data-agent", "query")
    github_tool = _mcp_tool("github", "issues")
    registry.register(_BasicTool())
    registry.register(sim_tool)
    registry.register(github_tool)
    registry.register(ToolSearchTool(registry))

    _inject_company_user(app_client, allowed={"sim-data-agent"})
    request = MagicMock()
    request.app = app_client.app
    request.state = MagicMock(company_user=CompanyUser(
        id="user-1",
        email="user@example.com",
        display_name="User One",
        role="user",
        is_active=True,
    ))

    filtered = await tool_registry_for_request(request, registry)

    assert filtered.get("read") is not None
    assert filtered.get(sim_tool.id) is not None
    assert filtered.get(github_tool.id) is None
    search = filtered.get("tool_search")
    assert search is not None
    assert [tool.id for tool in search._get_deferred_tools()] == [sim_tool.id]


class TestListConnectors:
    async def test_with_registry(self, app_client, _mock_cr):
        resp = await app_client.get("/api/connectors")
        assert resp.status_code == 200
        assert "github" in resp.json()["connectors"]

    async def test_filters_connectors_by_company_policy(self, app_client, _mock_cr):
        _inject_company_user(app_client, allowed={"slack"})
        resp = await app_client.get("/api/connectors")
        assert resp.status_code == 200
        assert list(resp.json()["connectors"]) == ["slack"]

    async def test_syncs_remote_connector_policy_before_filtering(self, app_client, _mock_cr, monkeypatch):
        class LocalEmptyPolicyStore:
            async def is_connector_allowed(self, connector_id: str, user_id: str) -> bool:
                return False

        app_client.app.state.company_auth_store = LocalEmptyPolicyStore()
        app_client.app.state.settings.company_auth_enabled = False
        app_client.app.middleware_stack = None

        async def inject_user(request, call_next):
            request.state.company_user = CompanyUser(
                id="user-1",
                email="user@example.com",
                display_name="User One",
                role="user",
                is_active=True,
            )
            return await call_next(request)

        async def fake_fetch(*, settings, company_session_token):
            assert company_session_token == "company-token"
            return {"slack"}

        app_client.app.middleware("http")(inject_user)
        monkeypatch.setattr(connector_access, "fetch_runtime_connector_policy", fake_fetch)

        resp = await app_client.get("/api/connectors", headers={"X-FPI-Session": "company-token"})

        assert resp.status_code == 200
        assert list(resp.json()["connectors"]) == ["slack"]

    async def test_remote_connector_policy_fetch_failure_fails_closed(self, app_client, _mock_cr, monkeypatch):
        app_client.app.state.company_auth_store = None
        app_client.app.state.settings.company_auth_enabled = False

        async def fake_fetch(*, settings, company_session_token):
            return None

        monkeypatch.setattr(connector_access, "fetch_runtime_connector_policy", fake_fetch)

        resp = await app_client.get("/api/connectors", headers={"X-FPI-Session": "company-token"})

        assert resp.status_code == 200
        assert resp.json()["connectors"] == {}

    async def test_no_registry(self, app_client):
        app_client.app.state.connector_registry = None
        resp = await app_client.get("/api/connectors")
        assert resp.status_code == 200
        assert resp.json() == {"connectors": {}}

    async def test_runtime_connector_policy_returns_current_user_connectors(self, app_client):
        app_client.app.state.company_auth_store = _RuntimeConnectorPolicyStore()
        app_client.app.state.settings.company_auth_enabled = True

        resp = await app_client.get("/api/connectors/policy/runtime", headers={"X-FPI-Session": "company-token"})

        assert resp.status_code == 200
        assert resp.json() == {"connector_ids": ["slack"]}

    async def test_runtime_connector_policy_requires_company_session(self, app_client):
        app_client.app.state.company_auth_store = _RuntimeConnectorPolicyStore()
        app_client.app.state.settings.company_auth_enabled = True

        resp = await app_client.get("/api/connectors/policy/runtime")

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Company login required"


class TestConnectorDetail:
    async def test_existing(self, app_client, _mock_cr):
        resp = await app_client.get("/api/connectors/github")
        assert resp.status_code == 200
        assert resp.json()["status"] == "connected"

    async def test_not_found(self, app_client, _mock_cr):
        resp = await app_client.get("/api/connectors/nonexistent")
        assert resp.status_code == 404


class TestAddCustom:
    async def test_success(self, app_client, _mock_cr):
        resp = await app_client.post("/api/connectors", json={
            "id": "c1", "name": "Custom", "url": "https://ex.com",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_duplicate(self, app_client, _mock_cr):
        _mock_cr.register_custom.side_effect = ValueError("Dup")
        resp = await app_client.post("/api/connectors", json={
            "id": "dup", "name": "D", "url": "https://ex.com",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is False


class TestRemoveCustom:
    async def test_success(self, app_client, _mock_cr):
        resp = await app_client.delete("/api/connectors/c1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_not_custom(self, app_client, _mock_cr):
        _mock_cr.remove_custom.return_value = False
        resp = await app_client.delete("/api/connectors/builtin")
        assert resp.status_code == 200
        assert resp.json()["success"] is False


class TestEnableDisable:
    async def test_enable(self, app_client, _mock_cr):
        resp = await app_client.post("/api/connectors/github/enable")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_enable_rejects_user_without_connector_policy_access(self, app_client, _mock_cr):
        _inject_company_user(app_client, allowed={"slack"})
        resp = await app_client.post("/api/connectors/github/enable")
        assert resp.status_code == 403
        assert "not available" in resp.json()["detail"]
        _mock_cr.enable.assert_not_awaited()

    async def test_disable(self, app_client, _mock_cr):
        resp = await app_client.post("/api/connectors/slack/disable")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestOAuthCallback:
    async def test_callback(self, app_client, _mock_cr):
        resp = await app_client.get("/api/connectors/oauth/callback", params={"code": "c", "state": "s"})
        assert resp.status_code == 200
        _mock_cr.complete_auth.assert_awaited_once_with("s", "c")
