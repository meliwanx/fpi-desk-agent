"""Connector management endpoints — individual MCP server connections."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.company_auth.store import CompanyConnectorPolicy, CompanyUser
from app.connector.access import (
    connector_allowed_for_request,
    sync_remote_connector_policy_for_request,
)

router = APIRouter(prefix="/connectors")


def _get_registry(request: Request):
    return getattr(request.app.state, "connector_registry", None)


def _allowed_connector_ids_for_user(
    policy: CompanyConnectorPolicy,
    user: CompanyUser,
) -> list[str]:
    return [
        entry.connector_id
        for entry in policy.connectors
        if user.id in entry.allowed_user_ids
    ]


async def _filter_allowed_connectors(
    status: dict[str, dict[str, Any]],
    request: Request,
) -> dict[str, dict[str, Any]]:
    filtered: dict[str, dict[str, Any]] = {}
    for connector_id, detail in status.items():
        if await connector_allowed_for_request(connector_id, request):
            filtered[connector_id] = detail
    return filtered


async def _ensure_connector_allowed(connector_id: str, request: Request) -> None:
    await sync_remote_connector_policy_for_request(request)
    if await connector_allowed_for_request(connector_id, request):
        return
    raise HTTPException(status_code=403, detail=f"Connector not available for this user: {connector_id}")


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------


@router.get("")
async def list_connectors(request: Request) -> dict[str, Any]:
    """Return all connectors with status."""
    registry = _get_registry(request)
    if registry is None:
        return {"connectors": {}}
    await sync_remote_connector_policy_for_request(request)
    return {"connectors": await _filter_allowed_connectors(registry.status(), request)}


# ------------------------------------------------------------------
# Runtime policy
# ------------------------------------------------------------------


class RuntimeConnectorPolicyResponse(BaseModel):
    connector_ids: list[str]


@router.get("/policy/runtime", response_model=RuntimeConnectorPolicyResponse)
async def get_runtime_connector_policy(request: Request) -> RuntimeConnectorPolicyResponse:
    """Return connector IDs available to the current company user.

    Desktop backends use this narrow runtime endpoint to obey the centrally
    managed connector allowlist without receiving the full admin policy.
    """
    store = getattr(request.app.state, "company_auth_store", None)
    settings = getattr(request.app.state, "settings", None)
    if store is None or not getattr(settings, "company_auth_enabled", False):
        return RuntimeConnectorPolicyResponse(connector_ids=[])

    token = request.headers.get("X-FPI-Session", "").strip()
    user = await store.get_session_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Company login required")

    policy = await store.get_connector_policy()
    return RuntimeConnectorPolicyResponse(
        connector_ids=_allowed_connector_ids_for_user(policy, user),
    )


# ------------------------------------------------------------------
# OAuth callback — MUST be before /{connector_id} to avoid conflict
# ------------------------------------------------------------------


class AuthCallbackBody(BaseModel):
    code: str
    state: str


@router.get("/oauth/callback")
async def oauth_callback(code: str, state: str, request: Request):
    """OAuth callback — receives auth code from provider redirect."""
    registry = _get_registry(request)
    if registry is None:
        return HTMLResponse("<p>Connector system not available</p>")

    success = await registry.complete_auth(state, code)

    from app.api.callback_html import render_callback
    return HTMLResponse(content=render_callback(
        success,
        extra_data={"state": state},
    ))


# ------------------------------------------------------------------
# Detail (after /oauth/callback to avoid route conflict)
# ------------------------------------------------------------------


@router.get("/{connector_id}")
async def connector_detail(connector_id: str, request: Request) -> dict[str, Any]:
    """Return details for a single connector."""
    registry = _get_registry(request)
    if registry is None:
        raise HTTPException(status_code=404, detail="Connector system not available")

    status = registry.status()
    detail = status.get(connector_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Connector not found: {connector_id}")
    await _ensure_connector_allowed(connector_id, request)
    return detail


# ------------------------------------------------------------------
# Custom connector CRUD
# ------------------------------------------------------------------


class AddConnectorBody(BaseModel):
    id: str
    name: str
    url: str
    description: str = ""
    category: str = "custom"


@router.post("")
async def add_custom_connector(body: AddConnectorBody, request: Request) -> dict[str, Any]:
    """Add a user-defined custom connector."""
    registry = _get_registry(request)
    if registry is None:
        return {"success": False, "error": "Connector system not available"}
    try:
        connector = registry.register_custom(
            id=body.id,
            name=body.name,
            url=body.url,
            description=body.description,
            category=body.category,
        )
        return {"success": True, "connector": connector.to_dict()}
    except ValueError as e:
        return {"success": False, "error": str(e)}


@router.delete("/{connector_id}")
async def remove_custom_connector(connector_id: str, request: Request) -> dict[str, Any]:
    """Remove a custom connector."""
    registry = _get_registry(request)
    if registry is None:
        return {"success": False, "error": "Connector system not available"}
    success = registry.remove_custom(connector_id)
    if not success:
        return {"success": False, "error": "Not found or not a custom connector"}
    return {"success": True}


# ------------------------------------------------------------------
# Token (PAT / API key)
# ------------------------------------------------------------------


class SetTokenBody(BaseModel):
    token: str


@router.post("/{connector_id}/token")
async def set_connector_token(
    connector_id: str, body: SetTokenBody, request: Request
) -> dict[str, Any]:
    """Set a bearer token (PAT / API key) for a connector and reconnect."""
    registry = _get_registry(request)
    if registry is None:
        return {"success": False, "error": "Connector system not available"}

    connector = registry.get(connector_id)
    if not connector:
        return {"success": False, "error": f"Connector not found: {connector_id}"}
    await _ensure_connector_allowed(connector_id, request)

    # Store the token and inject into MCP client
    mgr = registry.mcp_manager
    if mgr:
        client = mgr._clients.get(connector_id)
        if client:
            client.set_oauth_token(body.token)
        # Also persist in token store so it survives restarts
        mgr._token_store.save(
            connector_id,
            type("TokenSet", (), {
                "access_token": body.token,
                "refresh_token": None,
                "expires_at": 0,
                "token_type": "Bearer",
                "scope": "",
            })(),
        )

    # Enable if not already
    if not connector.enabled:
        await registry.enable(connector_id)
    else:
        await registry.reconnect(connector_id)

    return {"success": True, "connectors": await _filter_allowed_connectors(registry.status(), request)}


# ------------------------------------------------------------------
# Enable / disable
# ------------------------------------------------------------------


@router.post("/{connector_id}/enable")
async def enable_connector(connector_id: str, request: Request) -> dict[str, Any]:
    """Enable a connector."""
    registry = _get_registry(request)
    if registry is None:
        return {"success": False, "error": "Connector system not available"}
    await _ensure_connector_allowed(connector_id, request)
    success = await registry.enable(connector_id)
    return {"success": success, "connectors": await _filter_allowed_connectors(registry.status(), request)}


@router.post("/{connector_id}/disable")
async def disable_connector(connector_id: str, request: Request) -> dict[str, Any]:
    """Disable a connector."""
    registry = _get_registry(request)
    if registry is None:
        return {"success": False, "error": "Connector system not available"}
    await _ensure_connector_allowed(connector_id, request)
    success = await registry.disable(connector_id)
    return {"success": success, "connectors": await _filter_allowed_connectors(registry.status(), request)}


# ------------------------------------------------------------------
# OAuth connect / disconnect / reconnect
# ------------------------------------------------------------------


@router.post("/{connector_id}/connect")
async def connect_connector(connector_id: str, request: Request) -> dict[str, Any]:
    """Start OAuth flow for a connector."""
    registry = _get_registry(request)
    if registry is None:
        return {"success": False, "error": "Connector system not available"}
    await _ensure_connector_allowed(connector_id, request)

    settings = request.app.state.settings
    host = settings.host if settings.host != "0.0.0.0" else "localhost"
    redirect_uri = f"http://{host}:{settings.port}/api/connectors/oauth/callback"

    result = await registry.connect(connector_id, redirect_uri)
    if result is None:
        return {
            "success": False,
            "error": "Could not discover OAuth server for this connector",
        }
    return {"success": True, **result}


@router.post("/{connector_id}/auth-callback")
async def auth_callback_api(
    connector_id: str, body: AuthCallbackBody, request: Request
) -> dict[str, Any]:
    """API-based auth callback."""
    registry = _get_registry(request)
    if registry is None:
        return {"success": False, "error": "Connector system not available"}
    await _ensure_connector_allowed(connector_id, request)
    success = await registry.complete_auth(body.state, body.code)
    return {"success": success, "connectors": await _filter_allowed_connectors(registry.status(), request)}


@router.post("/{connector_id}/disconnect")
async def disconnect_connector(connector_id: str, request: Request) -> dict[str, Any]:
    """Remove OAuth tokens and disconnect a connector."""
    registry = _get_registry(request)
    if registry is None:
        return {"success": False, "error": "Connector system not available"}
    await _ensure_connector_allowed(connector_id, request)
    success = await registry.disconnect(connector_id)
    return {"success": success, "connectors": await _filter_allowed_connectors(registry.status(), request)}


@router.post("/{connector_id}/reconnect")
async def reconnect_connector(connector_id: str, request: Request) -> dict[str, Any]:
    """Reconnect a specific connector."""
    registry = _get_registry(request)
    if registry is None:
        return {"success": False, "error": "Connector system not available"}
    await _ensure_connector_allowed(connector_id, request)
    success = await registry.reconnect(connector_id)
    return {"success": success, "connectors": await _filter_allowed_connectors(registry.status(), request)}
