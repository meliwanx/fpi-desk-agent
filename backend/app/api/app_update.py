"""Enterprise desktop update policy endpoint."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class AppUpdatePolicyResponse(BaseModel):
    enabled: bool
    current_version: str
    latest_version: str
    min_supported_version: str
    update_available: bool
    force_update: bool
    release_notes: str
    download_url: str
    checked_at: str


def _policy_value(policy: Any, key: str, default: Any = "") -> Any:
    if isinstance(policy, dict):
        return policy.get(key, default)
    return getattr(policy, key, default)


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", (value or "").lstrip("vV"))
    return tuple(int(part) for part in parts[:4]) if parts else (0,)


def _compare_versions(left: str, right: str) -> int:
    lhs = list(_version_tuple(left))
    rhs = list(_version_tuple(right))
    length = max(len(lhs), len(rhs))
    lhs.extend([0] * (length - len(lhs)))
    rhs.extend([0] * (length - len(rhs)))
    if lhs == rhs:
        return 0
    return -1 if lhs < rhs else 1


def _download_url_for_platform(policy: Any, platform: str) -> str:
    normalized = (platform or "").lower()
    if normalized in {"darwin", "mac", "macos", "osx"}:
        return str(_policy_value(policy, "macos_download_url") or _policy_value(policy, "default_download_url") or "")
    if normalized in {"windows", "win", "win32", "win64"}:
        return str(_policy_value(policy, "windows_download_url") or _policy_value(policy, "default_download_url") or "")
    if normalized in {"linux", "linux-x64", "ubuntu", "debian"}:
        return str(_policy_value(policy, "linux_download_url") or _policy_value(policy, "default_download_url") or "")
    return str(_policy_value(policy, "default_download_url") or "")


def build_update_response(
    policy: Any,
    *,
    current_version: str,
    platform: str,
) -> AppUpdatePolicyResponse:
    enabled = bool(_policy_value(policy, "enabled", False))
    latest_version = str(_policy_value(policy, "latest_version", "") or "").strip()
    min_supported_version = str(_policy_value(policy, "min_supported_version", "") or "").strip()
    current = (current_version or "").strip().lstrip("vV")

    update_available = enabled and bool(latest_version) and _compare_versions(current, latest_version) < 0
    below_minimum = bool(min_supported_version) and _compare_versions(current, min_supported_version) < 0
    force_update = bool(update_available and (bool(_policy_value(policy, "force_update", False)) or below_minimum))

    return AppUpdatePolicyResponse(
        enabled=enabled,
        current_version=current,
        latest_version=latest_version,
        min_supported_version=min_supported_version,
        update_available=update_available,
        force_update=force_update,
        release_notes=str(_policy_value(policy, "release_notes", "") or ""),
        download_url=_download_url_for_platform(policy, platform),
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


def _company_store(request: Request):
    store = getattr(request.app.state, "company_auth_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Company auth store not initialized")
    return store


@router.get("/app/update-policy", response_model=AppUpdatePolicyResponse)
async def get_app_update_policy(
    request: Request,
    current_version: str = "",
    platform: str = "",
    arch: str = "",
) -> AppUpdatePolicyResponse:
    del arch
    policy = await _company_store(request).get_update_policy()
    return build_update_response(policy, current_version=current_version, platform=platform)
