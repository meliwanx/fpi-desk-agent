"""Per-request connector access helpers."""

from __future__ import annotations

from typing import Any

from app.company_auth.remote_control import fetch_runtime_connector_policy
from app.mcp.tool_wrapper import McpToolWrapper
from app.tool.builtin.tool_search import ToolSearchTool
from app.tool.registry import ToolRegistry

_REMOTE_ALLOWED_CONNECTORS_ATTR = "allowed_connector_ids"


def _remote_allowed_connector_ids(state: Any) -> set[str] | None:
    value = getattr(state, _REMOTE_ALLOWED_CONNECTORS_ATTR, None)
    if value is None:
        return None
    if isinstance(value, (set, frozenset, list, tuple)):
        return {
            connector_id
            for raw in value
            for connector_id in [str(raw or "").strip()]
            if connector_id
        }
    return None


def connector_id_for_tool(tool: Any) -> str | None:
    if not isinstance(tool, McpToolWrapper):
        return None
    client = getattr(tool, "_client", None)
    connector_id = getattr(client, "name", "")
    return str(connector_id or "").strip() or None


async def sync_remote_connector_policy_for_request(request: Any) -> set[str] | None:
    """Attach centrally managed connector access for a desktop request.

    Centralized backends use ``company_auth_store`` directly. Desktop backends
    normally only have the company session token, so they must ask the enterprise
    control plane which connectors this user may see.
    """
    state = getattr(request, "state", None)
    if state is None:
        return None
    existing = _remote_allowed_connector_ids(state)
    if existing is not None:
        return existing

    app_state = getattr(getattr(request, "app", None), "state", None)
    settings = getattr(app_state, "settings", None)
    if settings is None:
        return None

    company_store = getattr(app_state, "company_auth_store", None)
    if company_store is not None and getattr(settings, "company_auth_enabled", False):
        return None

    headers = getattr(request, "headers", {}) or {}
    raw_token = headers.get("X-FPI-Session", "")
    if not isinstance(raw_token, str):
        return None
    token = raw_token.strip()
    if not token:
        return None

    allowed = await fetch_runtime_connector_policy(
        settings=settings,
        company_session_token=token,
    )
    if allowed is None:
        allowed = set()
    setattr(state, _REMOTE_ALLOWED_CONNECTORS_ATTR, set(allowed))
    return set(allowed)


async def connector_allowed_for_request(connector_id: str, request: Any) -> bool:
    state = getattr(request, "state", None)
    remote_allowed = _remote_allowed_connector_ids(state) if state is not None else None
    if remote_allowed is not None:
        return connector_id in remote_allowed

    store = getattr(getattr(request, "app", None), "state", None)
    company_store = getattr(store, "company_auth_store", None)
    if company_store is None:
        return True

    user = getattr(getattr(request, "state", None), "company_user", None)
    if user is None:
        return False

    checker = getattr(company_store, "is_connector_allowed", None)
    if checker is None:
        return True
    return bool(await checker(connector_id, user.id))


async def tool_registry_for_request(request: Any, registry: ToolRegistry) -> ToolRegistry:
    """Return a request-scoped registry with unauthorized MCP tools removed."""
    await sync_remote_connector_policy_for_request(request)

    store = getattr(getattr(request, "app", None), "state", None)
    state = getattr(request, "state", None)
    remote_allowed = _remote_allowed_connector_ids(state) if state is not None else None
    if getattr(store, "company_auth_store", None) is None and remote_allowed is None:
        return registry

    filtered = ToolRegistry()
    has_allowed_mcp_tool = False
    had_tool_search = registry.get("tool_search") is not None

    for tool in registry.all_tools():
        if tool.id == "tool_search":
            continue
        connector_id = connector_id_for_tool(tool)
        if connector_id is None:
            filtered.register(tool)
            continue
        if await connector_allowed_for_request(connector_id, request):
            has_allowed_mcp_tool = True
            filtered.register(tool)

    if had_tool_search and has_allowed_mcp_tool:
        filtered.register(ToolSearchTool(filtered))

    return filtered
