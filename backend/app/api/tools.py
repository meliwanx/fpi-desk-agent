"""Tool listing endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.connector.access import tool_registry_for_request
from app.dependencies import ToolRegistryDep

router = APIRouter()


@router.get("/tools")
async def list_tools(request: Request, registry: ToolRegistryDep) -> list[dict[str, Any]]:
    """List all registered tools with their descriptions."""
    request_registry = await tool_registry_for_request(request, registry)
    return [
        {"id": tool.id, "description": tool.description}
        for tool in request_registry.all_tools()
        if tool.id != "invalid"  # Hide internal fallback
    ]


@router.get("/tools/{tool_id}")
async def get_tool(request: Request, registry: ToolRegistryDep, tool_id: str) -> dict[str, Any]:
    """Get tool details including JSON Schema."""
    request_registry = await tool_registry_for_request(request, registry)
    tool = request_registry.get(tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")
    return {
        "id": tool.id,
        "description": tool.description,
        "parameters": tool.parameters_schema(),
    }
