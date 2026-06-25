"""Enterprise desktop update policy endpoint."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import FileResponse, Response
from starlette.routing import NoMatchFound

from app.dependencies import SettingsDep

router = APIRouter()


class AppUpdatePolicyResponse(BaseModel):
    enabled: bool
    current_version: str
    current_package_sha256: str = ""
    latest_version: str
    min_supported_version: str
    update_available: bool
    force_update: bool
    release_notes: str
    latest_package_id: str = ""
    latest_package_name: str = ""
    latest_package_sha256: str = ""
    latest_package_md5: str = ""
    download_url: str
    download_filename: str = ""
    download_size_bytes: int = 0
    download_sha256: str = ""
    checked_at: str


class AppUpdateManifestPlatform(BaseModel):
    url: str
    signature: str


class AppUpdateManifestResponse(BaseModel):
    version: str
    notes: str = ""
    pub_date: str
    platforms: dict[str, AppUpdateManifestPlatform]


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


def _download_url_for_asset(request: Request, asset: Any) -> str:
    try:
        return str(request.url_for("website_download_asset", asset_id=asset.id))
    except NoMatchFound:
        return str(request.url_for("download_app_update_asset", asset_id=asset.id))


async def _local_download_info_for_platform(
    request: Request,
    policy: Any,
    platform: str,
) -> tuple[str, str, int, str, str, str, str, str]:
    asset_id = _asset_id_for_platform(policy, platform)
    if not asset_id:
        return "", "", 0, "", "", "", "", ""
    store = _company_store(request)
    if not hasattr(store, "get_update_asset"):
        return "", "", 0, "", "", "", "", ""
    asset = await store.get_update_asset(asset_id)
    if asset is None:
        return "", "", 0, "", "", "", "", ""
    return (
        _download_url_for_asset(request, asset),
        asset.original_filename or "",
        int(asset.size_bytes or 0),
        str(asset.version or ""),
        str(asset.sha256 or ""),
        str(asset.id or ""),
        str(getattr(asset, "name", "") or ""),
        str(getattr(asset, "md5", "") or ""),
    )


def _effective_min_supported_version(min_supported_version: str, latest_version: str) -> str:
    if not min_supported_version:
        return ""
    if latest_version and _compare_versions(min_supported_version, latest_version) > 0:
        return ""
    return min_supported_version


def build_update_response(
    policy: Any,
    *,
    current_version: str,
    current_package_sha256: str = "",
    platform: str,
    download_url: str | None = None,
    download_filename: str = "",
    download_size_bytes: int = 0,
    download_sha256: str = "",
    latest_package_id: str = "",
    latest_package_name: str = "",
    latest_package_md5: str = "",
    effective_latest_version: str | None = None,
) -> AppUpdatePolicyResponse:
    enabled = bool(_policy_value(policy, "enabled", False))
    policy_latest_version = str(_policy_value(policy, "latest_version", "") or "").strip()
    latest_version = (effective_latest_version or policy_latest_version).strip()
    min_supported_version = _effective_min_supported_version(
        str(_policy_value(policy, "min_supported_version", "") or "").strip(),
        latest_version,
    )
    current = (current_version or "").strip().lstrip("vV")
    current_sha256 = (current_package_sha256 or "").strip().lower()
    latest_sha256 = (download_sha256 or "").strip().lower()

    version_update_available = bool(latest_version) and _compare_versions(current, latest_version) < 0
    below_minimum = bool(min_supported_version) and _compare_versions(current, min_supported_version) < 0
    update_available = enabled and (version_update_available or below_minimum)
    force_update = bool(
        update_available
        and (bool(_policy_value(policy, "force_update", False)) or below_minimum)
    )

    return AppUpdatePolicyResponse(
        enabled=enabled,
        current_version=current,
        current_package_sha256=current_sha256,
        latest_version=latest_version,
        min_supported_version=min_supported_version,
        update_available=update_available,
        force_update=force_update,
        release_notes=str(_policy_value(policy, "release_notes", "") or ""),
        latest_package_id=latest_package_id,
        latest_package_name=latest_package_name,
        latest_package_sha256=latest_sha256,
        latest_package_md5=latest_package_md5,
        download_url=download_url if download_url is not None else _legacy_download_url_for_platform(policy, platform),
        download_filename=download_filename,
        download_size_bytes=download_size_bytes,
        download_sha256=download_sha256,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


def _company_store(request: Request):
    store = getattr(request.app.state, "company_auth_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Company auth store not initialized")
    return store


def _tauri_platform_keys(platform: str) -> list[str]:
    normalized = _normalized_platform(platform)
    if normalized == "macos":
        return ["darwin-aarch64-app", "darwin-aarch64"]
    if normalized == "windows":
        return ["windows-x86_64-nsis", "windows-x86_64"]
    if normalized == "linux":
        return ["linux-x86_64-appimage", "linux-x86_64"]
    return [
        "darwin-aarch64-app",
        "darwin-aarch64",
        "windows-x86_64-nsis",
        "windows-x86_64",
        "linux-x86_64-appimage",
        "linux-x86_64",
    ]


async def _update_asset_for_platform(request: Request, policy: Any, platform: str) -> Any | None:
    asset_id = _asset_id_for_platform(policy, platform)
    if not asset_id:
        return None
    store = _company_store(request)
    if not hasattr(store, "get_update_asset"):
        return None
    return await store.get_update_asset(asset_id)


async def _signed_manifest_platforms(
    request: Request,
    policy: Any,
    *,
    effective_version: str,
) -> dict[str, AppUpdateManifestPlatform]:
    platforms: dict[str, AppUpdateManifestPlatform] = {}
    seen_asset_ids: set[str] = set()
    for platform in ("macos", "windows", "linux", "default"):
        asset = await _update_asset_for_platform(request, policy, platform)
        if asset is None or asset.id in seen_asset_ids:
            continue
        seen_asset_ids.add(asset.id)
        if str(asset.version or "").strip() != effective_version:
            continue
        signature = str(getattr(asset, "signature", "") or "").strip()
        if not signature:
            continue
        entry = AppUpdateManifestPlatform(
            url=_download_url_for_asset(request, asset),
            signature=signature,
        )
        for key in _tauri_platform_keys(platform):
            platforms.setdefault(key, entry)
    return platforms


@router.get("/app/update-policy", response_model=AppUpdatePolicyResponse)
async def get_app_update_policy(
    request: Request,
    current_version: str = "",
    current_package_sha256: str = "",
    platform: str = "",
    arch: str = "",
) -> AppUpdatePolicyResponse:
    del arch
    policy = await _company_store(request).get_update_policy()
    (
        local_download_url,
        download_filename,
        download_size_bytes,
        asset_version,
        download_sha256,
        latest_package_id,
        latest_package_name,
        latest_package_md5,
    ) = await _local_download_info_for_platform(request, policy, platform)
    download_url = local_download_url or _legacy_download_url_for_platform(policy, platform)
    return build_update_response(
        policy,
        current_version=current_version,
        current_package_sha256=current_package_sha256,
        platform=platform,
        download_url=download_url,
        download_filename=download_filename,
        download_size_bytes=download_size_bytes,
        download_sha256=download_sha256,
        latest_package_id=latest_package_id,
        latest_package_name=latest_package_name,
        latest_package_md5=latest_package_md5,
        effective_latest_version=asset_version or None,
    )


@router.get(
    "/app/update-manifest/{target}/{arch}/{current_version}",
    response_model=AppUpdateManifestResponse,
    responses={204: {"description": "No update available"}},
)
async def get_app_update_manifest(
    request: Request,
    target: str,
    arch: str,
    current_version: str,
    bundle: str = "",
) -> AppUpdateManifestResponse | Response:
    del arch, bundle
    policy = await _company_store(request).get_update_policy()
    enabled = bool(_policy_value(policy, "enabled", False))
    if not enabled:
        return Response(status_code=204)

    target_platform = _normalized_platform(target)
    platform_asset = await _update_asset_for_platform(request, policy, target_platform)
    policy_latest_version = str(_policy_value(policy, "latest_version", "") or "").strip()
    effective_latest_version = str(getattr(platform_asset, "version", "") or "").strip() or policy_latest_version
    if not effective_latest_version or _compare_versions(current_version, effective_latest_version) >= 0:
        return Response(status_code=204)

    platforms = await _signed_manifest_platforms(
        request,
        policy,
        effective_version=effective_latest_version,
    )
    if not platforms:
        return Response(status_code=204)

    return AppUpdateManifestResponse(
        version=effective_latest_version,
        notes=str(_policy_value(policy, "release_notes", "") or ""),
        pub_date=datetime.now(timezone.utc).isoformat(),
        platforms=platforms,
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
