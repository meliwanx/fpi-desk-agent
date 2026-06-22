"""Enterprise desktop update policy endpoint."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import FileResponse
from starlette.routing import NoMatchFound

from app.dependencies import SettingsDep

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
    download_filename: str = ""
    download_size_bytes: int = 0
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


def _normalized_platform(platform: str) -> str:
    normalized = (platform or "").lower()
    if normalized in {"darwin", "mac", "macos", "osx"}:
        return "macos"
    if normalized in {"windows", "win", "win32", "win64"}:
        return "windows"
    if normalized in {"linux", "linux-x64", "ubuntu", "debian"}:
        return "linux"
    return "default"


def _legacy_download_url_for_platform(policy: Any, platform: str) -> str:
    normalized = _normalized_platform(platform)
    if normalized == "macos":
        return str(_policy_value(policy, "macos_download_url") or _policy_value(policy, "default_download_url") or "")
    if normalized == "windows":
        return str(_policy_value(policy, "windows_download_url") or _policy_value(policy, "default_download_url") or "")
    if normalized == "linux":
        return str(_policy_value(policy, "linux_download_url") or _policy_value(policy, "default_download_url") or "")
    return str(_policy_value(policy, "default_download_url") or "")


def _asset_id_for_platform(policy: Any, platform: str) -> str:
    normalized = _normalized_platform(platform)
    if normalized == "macos":
        asset_id = _policy_value(policy, "macos_asset_id")
    elif normalized == "windows":
        asset_id = _policy_value(policy, "windows_asset_id")
    elif normalized == "linux":
        asset_id = _policy_value(policy, "linux_asset_id")
    else:
        asset_id = ""
    return str(asset_id or _policy_value(policy, "default_asset_id") or "")


async def _local_download_info_for_platform(request: Request, policy: Any, platform: str) -> tuple[str, str, int]:
    asset_id = _asset_id_for_platform(policy, platform)
    if not asset_id:
        return "", "", 0
    store = _company_store(request)
    if not hasattr(store, "get_update_asset"):
        return "", "", 0
    asset = await store.get_update_asset(asset_id)
    if asset is None:
        return "", "", 0
    try:
        download_url = str(request.url_for("website_download_asset", asset_id=asset.id))
    except NoMatchFound:
        download_url = str(request.url_for("download_app_update_asset", asset_id=asset.id))
    return download_url, asset.original_filename or "", int(asset.size_bytes or 0)


def build_update_response(
    policy: Any,
    *,
    current_version: str,
    platform: str,
    download_url: str | None = None,
    download_filename: str = "",
    download_size_bytes: int = 0,
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
        download_url=download_url if download_url is not None else _legacy_download_url_for_platform(policy, platform),
        download_filename=download_filename,
        download_size_bytes=download_size_bytes,
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
    local_download_url, download_filename, download_size_bytes = await _local_download_info_for_platform(
        request,
        policy,
        platform,
    )
    download_url = local_download_url or _legacy_download_url_for_platform(policy, platform)
    return build_update_response(
        policy,
        current_version=current_version,
        platform=platform,
        download_url=download_url,
        download_filename=download_filename,
        download_size_bytes=download_size_bytes,
    )


@router.get("/app/update-download/{asset_id}", name="download_app_update_asset")
async def download_app_update_asset(
    request: Request,
    settings: SettingsDep,
    asset_id: str,
) -> FileResponse:
    store = _company_store(request)
    if not hasattr(store, "get_update_asset"):
        raise HTTPException(status_code=404, detail="Update asset not found")
    asset = await store.get_update_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Update asset not found")

    storage_dir = Path(settings.update_asset_storage_dir).expanduser()
    file_path = storage_dir / Path(asset.stored_filename).name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Update asset file not found")

    if hasattr(store, "increment_update_asset_download_count"):
        await store.increment_update_asset_download_count(asset.id)

    return FileResponse(
        file_path,
        media_type=asset.mime_type or "application/octet-stream",
        filename=asset.original_filename or file_path.name,
    )
