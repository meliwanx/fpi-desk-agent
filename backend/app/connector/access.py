"""Per-request connector access helpers."""

from __future__ import annotations

from typing import Any

from app.mcp.tool_wrapper import McpToolWrapper
from app.tool.builtin.tool_search import ToolSearchTool
from app.tool.registry import ToolRegistry


def connector_id_for_tool(tool: Any) -> str | None:
    if not isinstance(tool, McpToolWrapper):
        return None
    client = getattr(tool, "_client", None)
    connector_id = getattr(client, "name", "")
    return str(connector_id or "").strip() or None


async def connector_allowed_for_request(connector_id: str, request: Any) -> bool:
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
    store = getattr(getattr(request, "app", None), "state", None)
    if getattr(store, "company_auth_store", None) is None:
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
