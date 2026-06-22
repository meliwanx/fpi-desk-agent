"""Enterprise admin API for user management and audit review."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from starlette.responses import FileResponse

from app.company_auth.model_policy_sync import sync_company_model_policy
from app.company_auth.store import (
    CompanyFeedback,
    CompanyModelPolicy,
    CompanySessionRecord,
    CompanyUpdateAsset,
    CompanyUpdatePolicy,
    CompanyUser,
)
from app.config import Settings
from app.dependencies import DbDep, SettingsDep
from app.models.audit import (
    AuditAdminAction,
    AuditFile,
    AuditMessage,
    AuditPart,
    AuditRiskFinding,
    AuditSession,
    AuditToolCall,
    AuditUsage,
)
from app.utils.id import generate_ulid

router = APIRouter()

_API_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9._-]{8,}\b")
_URL_RE = re.compile(r"https?://[^\s\"'<>）)]+", re.IGNORECASE)
_VPN_HINT_RE = re.compile(
    r"(订阅|subscription|clash|v2ray|trojan|shadowsocks|sing-box|surge|quantumult|proxy|vpn)",
    re.IGNORECASE,
)


class AdminUserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    is_active: bool


class AdminCreateUserRequest(BaseModel):
    email: str = Field(..., min_length=1)
    display_name: str = ""
    password: str = Field(..., min_length=1)
    role: str = "user"


class AdminUpdateUserRequest(BaseModel):
    display_name: str | None = None
    password: str | None = None
    role: str | None = None
    is_active: bool | None = None


class AdminModelPolicyEntryRequest(BaseModel):
    provider_id: str = Field(..., min_length=1)
    id: str = Field(..., min_length=1)
    name: str = ""
    protocol: str = "openai_compatible"
    base_url: str = ""
    api_key: str | None = None


class AdminModelPolicyEntryResponse(BaseModel):
    provider_id: str
    id: str
    name: str
    protocol: str
    base_url: str
    masked_key: str


class AdminModelPolicyRequest(BaseModel):
    default_provider_id: str = Field(..., min_length=1)
    default_model_id: str = Field(..., min_length=1)
    models: list[AdminModelPolicyEntryRequest] = Field(..., min_length=1)


class AdminModelPolicyResponse(BaseModel):
    default_provider_id: str
    default_model_id: str
    models: list[AdminModelPolicyEntryResponse]


class AdminUpdatePolicyRequest(BaseModel):
    enabled: bool = False
    latest_version: str = ""
    min_supported_version: str = ""
    force_update: bool = False
    release_notes: str = ""
    macos_asset_id: str = ""
    windows_asset_id: str = ""
    linux_asset_id: str = ""
    default_asset_id: str = ""
    macos_download_url: str = ""
    windows_download_url: str = ""
    linux_download_url: str = ""
    default_download_url: str = ""


class AdminUpdateAssetResponse(BaseModel):
    id: str
    platform: str
    version: str
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    uploaded_by_user_id: str
    uploaded_by_email: str
    uploaded_by_display_name: str
    download_count: int
    time_created: datetime
    time_updated: datetime


class AdminUpdatePolicyResponse(BaseModel):
    enabled: bool
    latest_version: str
    min_supported_version: str
    force_update: bool
    release_notes: str
    macos_asset_id: str
    windows_asset_id: str
    linux_asset_id: str
    default_asset_id: str
    macos_asset: AdminUpdateAssetResponse | None = None
    windows_asset: AdminUpdateAssetResponse | None = None
    linux_asset: AdminUpdateAssetResponse | None = None
    default_asset: AdminUpdateAssetResponse | None = None
    macos_download_url: str
    windows_download_url: str
    linux_download_url: str
    default_download_url: str


class AdminFeedbackResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_display_name: str
    description: str
    image_original_filename: str
    image_mime_type: str
    image_size_bytes: int
    image_sha256: str
    image_download_url: str | None = None
    time_created: datetime
    time_updated: datetime


class AdminFeedbackListResponse(BaseModel):
    items: list[AdminFeedbackResponse]


class AdminCompanySessionResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_display_name: str
    user_role: str
    user_is_active: bool
    device_id: str
    device_name: str
    platform: str
    app_version: str
    ip_address: str
    user_agent: str
    is_online: bool
    expires_at: datetime
    revoked_at: datetime | None = None
    time_created: datetime
    last_seen_at: datetime
    revoked_by_user_id: str = ""
    revoked_by_email: str = ""
    revoked_reason: str = ""


class AdminCompanySessionListResponse(BaseModel):
    total: int
    items: list[AdminCompanySessionResponse]


class AdminRevokeSessionsRequest(BaseModel):
    session_ids: list[str] = Field(default_factory=list)
    user_ids: list[str] = Field(default_factory=list)
    reason: str = ""


class AdminRevokeSessionRequest(BaseModel):
    reason: str = ""


class AdminRevokeSessionsResponse(BaseModel):
    revoked_count: int


class AdminActionResponse(BaseModel):
    id: str
    actor_user_id: str
    actor_email: str
    actor_display_name: str
    action: str
    target_type: str
    target_id: str
    metadata: dict[str, Any]
    time_created: datetime
    time_updated: datetime


class AdminActionListResponse(BaseModel):
    total: int
    items: list[AdminActionResponse]


class AuditIngestSession(BaseModel):
    id: str
    title: str | None = None
    workspace: str | None = None
    model_id: str | None = None
    provider_id: str | None = None
    source_client_id: str | None = None


class AuditIngestMessage(BaseModel):
    id: str
    session_id: str
    role: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class AuditIngestPart(BaseModel):
    id: str
    message_id: str
    session_id: str
    data: dict[str, Any] = Field(default_factory=dict)


class AuditIngestRequest(BaseModel):
    sessions: list[AuditIngestSession] = Field(default_factory=list)
    messages: list[AuditIngestMessage] = Field(default_factory=list)
    parts: list[AuditIngestPart] = Field(default_factory=list)


def _current_company_user(request: Request) -> CompanyUser:
    user = getattr(request.state, "company_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Company login required")
    return user


def _require_admin(request: Request) -> CompanyUser:
    user = _current_company_user(request)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def _public_user(user: CompanyUser) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
    )


def _masked_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}...{api_key[-4:]}"


def _public_model_policy(policy: CompanyModelPolicy) -> AdminModelPolicyResponse:
    return AdminModelPolicyResponse(
        default_provider_id=policy.default_provider_id,
        default_model_id=policy.default_model_id,
        models=[
            AdminModelPolicyEntryResponse(
                provider_id=model.provider_id,
                id=model.id,
                name=model.name,
                protocol=model.protocol,
                base_url=model.base_url,
                masked_key=_masked_api_key(model.api_key),
            )
            for model in policy.models
        ],
    )


def _update_policy_value(policy: CompanyUpdatePolicy | dict[str, Any], key: str, default: Any = "") -> Any:
    if isinstance(policy, dict):
        return policy.get(key, default)
    return getattr(policy, key, default)


def _public_update_asset(asset: CompanyUpdateAsset) -> AdminUpdateAssetResponse:
    return AdminUpdateAssetResponse(
        id=asset.id,
        platform=asset.platform,
        version=asset.version,
        original_filename=asset.original_filename,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
        uploaded_by_user_id=asset.uploaded_by_user_id,
        uploaded_by_email=asset.uploaded_by_email,
        uploaded_by_display_name=asset.uploaded_by_display_name,
        download_count=asset.download_count,
        time_created=asset.time_created,
        time_updated=asset.time_updated,
    )


async def _policy_asset(store: Any, asset_id: str) -> AdminUpdateAssetResponse | None:
    if not asset_id or not hasattr(store, "get_update_asset"):
        return None
    asset = await store.get_update_asset(asset_id)
    return _public_update_asset(asset) if asset is not None else None


async def _public_update_policy(
    policy: CompanyUpdatePolicy | dict[str, Any],
    store: Any,
) -> AdminUpdatePolicyResponse:
    macos_asset_id = str(_update_policy_value(policy, "macos_asset_id", "") or "")
    windows_asset_id = str(_update_policy_value(policy, "windows_asset_id", "") or "")
    linux_asset_id = str(_update_policy_value(policy, "linux_asset_id", "") or "")
    default_asset_id = str(_update_policy_value(policy, "default_asset_id", "") or "")
    return AdminUpdatePolicyResponse(
        enabled=bool(_update_policy_value(policy, "enabled", False)),
        latest_version=str(_update_policy_value(policy, "latest_version", "") or ""),
        min_supported_version=str(_update_policy_value(policy, "min_supported_version", "") or ""),
        force_update=bool(_update_policy_value(policy, "force_update", False)),
        release_notes=str(_update_policy_value(policy, "release_notes", "") or ""),
        macos_asset_id=macos_asset_id,
        windows_asset_id=windows_asset_id,
        linux_asset_id=linux_asset_id,
        default_asset_id=default_asset_id,
        macos_asset=await _policy_asset(store, macos_asset_id),
        windows_asset=await _policy_asset(store, windows_asset_id),
        linux_asset=await _policy_asset(store, linux_asset_id),
        default_asset=await _policy_asset(store, default_asset_id),
        macos_download_url=str(_update_policy_value(policy, "macos_download_url", "") or ""),
        windows_download_url=str(_update_policy_value(policy, "windows_download_url", "") or ""),
        linux_download_url=str(_update_policy_value(policy, "linux_download_url", "") or ""),
        default_download_url=str(_update_policy_value(policy, "default_download_url", "") or ""),
    )


def _company_store(request: Request):
    store = getattr(request.app.state, "company_auth_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Company auth store not initialized")
    return store


def _safe_filename(name: str | None) -> str:
    safe = Path(name or "attachment").name.replace("\x00", "").strip()
    return safe or "attachment"


def _audit_storage_dir(settings: Settings) -> Path:
    return Path(settings.audit_file_storage_dir).expanduser()


def _update_asset_storage_dir(settings: Settings) -> Path:
    return Path(settings.update_asset_storage_dir).expanduser()


def _feedback_storage_dir(settings: Settings) -> Path:
    return Path(settings.feedback_storage_dir).expanduser()


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
    except Exception:
        return str(value)


def _preview(value: Any, *, limit: int = 2000) -> str:
    text = value if isinstance(value, str) else _json_text(value)
    return text[:limit]


def _token_value(tokens: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = tokens.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def _redact_secret(text: str) -> str:
    return _API_KEY_RE.sub(lambda match: f"{match.group(0)[:7]}...{match.group(0)[-4:]}", text)


def _risk_stable_key(item: AuditIngestPart, *, kind: str, evidence: str) -> str:
    raw = f"{item.session_id}:{item.message_id}:{item.id}:{kind}:{evidence}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _detect_risks(item: AuditIngestPart) -> list[dict[str, str]]:
    text = _json_text(item.data or {})
    findings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for match in _API_KEY_RE.finditer(text):
        evidence = match.group(0)
        key = ("api_key", evidence)
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            {
                "kind": "api_key",
                "severity": "high",
                "summary": "疑似 API Key 或访问密钥出现在对话内容中",
                "evidence_preview": _redact_secret(evidence),
            }
        )

    has_vpn_context = _VPN_HINT_RE.search(text) is not None
    for match in _URL_RE.finditer(text):
        evidence = match.group(0)
        if not (has_vpn_context or _VPN_HINT_RE.search(evidence)):
            continue
        key = ("vpn_subscription_url", evidence)
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            {
                "kind": "vpn_subscription_url",
                "severity": "high",
                "summary": "疑似 VPN/代理订阅链接出现在对话或工具输出中",
                "evidence_preview": evidence[:500],
            }
        )

    return findings


async def _record_admin_action(
    db: AsyncSession,
    *,
    user: CompanyUser,
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditAdminAction(
            actor_user_id=user.id,
            actor_email=user.email,
            actor_display_name=user.display_name,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata or {},
        )
    )


def _public_admin_action(action: AuditAdminAction) -> AdminActionResponse:
    return AdminActionResponse(
        id=action.id,
        actor_user_id=action.actor_user_id,
        actor_email=action.actor_email,
        actor_display_name=action.actor_display_name,
        action=action.action,
        target_type=action.target_type,
        target_id=action.target_id,
        metadata=action.metadata_json or {},
        time_created=action.time_created,
        time_updated=action.time_updated,
    )


@router.get("/admin/users", response_model=list[AdminUserResponse])
async def list_admin_users(request: Request) -> list[AdminUserResponse]:
    _require_admin(request)
    users = await _company_store(request).list_users()
    return [_public_user(user) for user in users]


@router.post("/admin/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    request: Request,
    body: AdminCreateUserRequest,
) -> AdminUserResponse:
    _require_admin(request)
    try:
        user = await _company_store(request).create_user(
            email=body.email,
            display_name=body.display_name,
            password=body.password,
            role=body.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _public_user(user)


@router.patch("/admin/users/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: str,
    request: Request,
    body: AdminUpdateUserRequest,
) -> AdminUserResponse:
    _require_admin(request)
    try:
        user = await _company_store(request).update_user(
            user_id,
            display_name=body.display_name,
            password=body.password,
            role=body.role,
            is_active=body.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _public_user(user)


@router.get("/admin/sessions", response_model=AdminCompanySessionListResponse)
async def list_admin_company_sessions(
    request: Request,
    user_id: str | None = None,
    include_revoked: bool = False,
    online_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> AdminCompanySessionListResponse:
    _require_admin(request)
    store = _company_store(request)
    total, sessions = await store.list_sessions(
        include_revoked=include_revoked,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    now = datetime.now(timezone.utc)
    presence = getattr(request.app.state, "company_presence", None)
    online_session_ids = await presence.online_session_ids() if presence is not None and presence.available else set()
    items = [
        _public_company_session(session, now=now, online_session_ids=online_session_ids)
        for session in sessions
    ]
    if online_only:
        items = [session for session in items if session.is_online]
        total = len(items)
    return AdminCompanySessionListResponse(
        total=total,
        items=items,
    )


@router.post("/admin/sessions/{session_id}/revoke", response_model=AdminRevokeSessionsResponse)
async def revoke_admin_company_session(
    session_id: str,
    request: Request,
    db: DbDep,
    body: AdminRevokeSessionRequest | None = None,
) -> AdminRevokeSessionsResponse:
    admin = _require_admin(request)
    reason = (body.reason if body else "").strip()
    revoked_count = await _company_store(request).revoke_session_by_id(
        session_id,
        revoked_by_user_id=admin.id,
        revoked_by_email=admin.email,
        reason=reason,
    )
    if revoked_count:
        await _record_admin_action(
            db,
            user=admin,
            action="revoke_company_session",
            target_type="company_session",
            target_id=session_id,
            metadata={"reason": reason},
        )
    return AdminRevokeSessionsResponse(revoked_count=revoked_count)


@router.post("/admin/users/{user_id}/revoke-sessions", response_model=AdminRevokeSessionsResponse)
async def revoke_admin_user_company_sessions(
    user_id: str,
    request: Request,
    db: DbDep,
    body: AdminRevokeSessionRequest | None = None,
) -> AdminRevokeSessionsResponse:
    admin = _require_admin(request)
    reason = (body.reason if body else "").strip()
    revoked_count = await _company_store(request).revoke_sessions(
        user_ids=[user_id],
        revoked_by_user_id=admin.id,
        revoked_by_email=admin.email,
        reason=reason,
    )
    if revoked_count:
        await _record_admin_action(
            db,
            user=admin,
            action="revoke_company_user_sessions",
            target_type="company_user",
            target_id=user_id,
            metadata={"reason": reason, "revoked_count": revoked_count},
        )
    return AdminRevokeSessionsResponse(revoked_count=revoked_count)


@router.post("/admin/sessions/revoke-bulk", response_model=AdminRevokeSessionsResponse)
async def revoke_admin_company_sessions_bulk(
    request: Request,
    db: DbDep,
    body: AdminRevokeSessionsRequest,
) -> AdminRevokeSessionsResponse:
    admin = _require_admin(request)
    reason = body.reason.strip()
    revoked_count = await _company_store(request).revoke_sessions(
        session_ids=body.session_ids,
        user_ids=body.user_ids,
        revoked_by_user_id=admin.id,
        revoked_by_email=admin.email,
        reason=reason,
    )
    if revoked_count:
        await _record_admin_action(
            db,
            user=admin,
            action="revoke_company_sessions_bulk",
            target_type="company_session",
            target_id="bulk",
            metadata={
                "reason": reason,
                "session_ids": body.session_ids,
                "user_ids": body.user_ids,
                "revoked_count": revoked_count,
            },
        )
    return AdminRevokeSessionsResponse(revoked_count=revoked_count)


@router.get("/admin/model-policy", response_model=AdminModelPolicyResponse)
async def get_admin_model_policy(request: Request) -> AdminModelPolicyResponse:
    _require_admin(request)
    policy = await _company_store(request).get_model_policy()
    return _public_model_policy(policy)


@router.put("/admin/model-policy", response_model=AdminModelPolicyResponse)
async def update_admin_model_policy(
    request: Request,
    body: AdminModelPolicyRequest,
) -> AdminModelPolicyResponse:
    _require_admin(request)
    try:
        policy = await _company_store(request).update_model_policy(
            default_provider_id=body.default_provider_id,
            default_model_id=body.default_model_id,
            models=[model.model_dump() for model in body.models],
        )
        registry = getattr(request.app.state, "provider_registry", None)
        if registry is not None:
            await sync_company_model_policy(registry, policy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _public_model_policy(policy)


@router.get("/admin/update-policy", response_model=AdminUpdatePolicyResponse)
async def get_admin_update_policy(request: Request) -> AdminUpdatePolicyResponse:
    _require_admin(request)
    store = _company_store(request)
    policy = await store.get_update_policy()
    return await _public_update_policy(policy, store)


@router.put("/admin/update-policy", response_model=AdminUpdatePolicyResponse)
async def update_admin_update_policy(
    request: Request,
    body: AdminUpdatePolicyRequest,
) -> AdminUpdatePolicyResponse:
    _require_admin(request)
    store = _company_store(request)
    try:
        policy = await store.update_update_policy(
            enabled=body.enabled,
            latest_version=body.latest_version,
            min_supported_version=body.min_supported_version,
            force_update=body.force_update,
            release_notes=body.release_notes,
            macos_asset_id=body.macos_asset_id,
            windows_asset_id=body.windows_asset_id,
            linux_asset_id=body.linux_asset_id,
            default_asset_id=body.default_asset_id,
            macos_download_url=body.macos_download_url,
            windows_download_url=body.windows_download_url,
            linux_download_url=body.linux_download_url,
            default_download_url=body.default_download_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await _public_update_policy(policy, store)


@router.post("/admin/update-assets/upload", response_model=AdminUpdateAssetResponse)
async def upload_admin_update_asset(
    request: Request,
    settings: SettingsDep,
    platform: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
) -> AdminUpdateAssetResponse:
    user = _require_admin(request)
    store = _company_store(request)
    original_filename = _safe_filename(file.filename)
    storage_dir = _update_asset_storage_dir(settings)
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{generate_ulid()}-{original_filename}"
    target = storage_dir / stored_filename

    digest = hashlib.sha256()
    size = 0
    try:
        with target.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                digest.update(chunk)
                handle.write(chunk)
    except Exception:
        if target.exists():
            target.unlink(missing_ok=True)
        raise

    if size == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Update asset file cannot be empty")

    mime_type = file.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
    try:
        asset = await store.create_update_asset(
            platform=platform,
            version=version,
            original_filename=original_filename,
            stored_filename=stored_filename,
            mime_type=mime_type,
            size_bytes=size,
            sha256=digest.hexdigest(),
            uploaded_by_user_id=user.id,
            uploaded_by_email=user.email,
            uploaded_by_display_name=user.display_name,
        )
    except ValueError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _public_update_asset(asset)


def _public_feedback(request: Request, feedback: CompanyFeedback) -> AdminFeedbackResponse:
    image_download_url = None
    if feedback.image_stored_filename:
        image_download_url = str(request.url_for("download_admin_feedback_image", feedback_id=feedback.id))
    return AdminFeedbackResponse(
        id=feedback.id,
        user_id=feedback.user_id,
        user_email=feedback.user_email,
        user_display_name=feedback.user_display_name,
        description=feedback.description,
        image_original_filename=feedback.image_original_filename,
        image_mime_type=feedback.image_mime_type,
        image_size_bytes=feedback.image_size_bytes,
        image_sha256=feedback.image_sha256,
        image_download_url=image_download_url,
        time_created=feedback.time_created,
        time_updated=feedback.time_updated,
    )


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_session_online(
    session: CompanySessionRecord,
    *,
    now: datetime | None = None,
    online_session_ids: set[str] | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    if session.revoked_at is not None:
        return False
    if _as_aware_utc(session.expires_at) <= current:
        return False
    if online_session_ids is not None and session.id in online_session_ids:
        return True
    return _as_aware_utc(session.last_seen_at) >= current - timedelta(seconds=120)


def _public_company_session(
    session: CompanySessionRecord,
    *,
    now: datetime | None = None,
    online_session_ids: set[str] | None = None,
) -> AdminCompanySessionResponse:
    return AdminCompanySessionResponse(
        id=session.id,
        user_id=session.user_id,
        user_email=session.user_email,
        user_display_name=session.user_display_name,
        user_role=session.user_role,
        user_is_active=session.user_is_active,
        device_id=session.device_id,
        device_name=session.device_name,
        platform=session.platform,
        app_version=session.app_version,
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        is_online=_is_session_online(session, now=now, online_session_ids=online_session_ids),
        expires_at=session.expires_at,
        revoked_at=session.revoked_at,
        time_created=session.time_created,
        last_seen_at=session.last_seen_at,
        revoked_by_user_id=session.revoked_by_user_id,
        revoked_by_email=session.revoked_by_email,
        revoked_reason=session.revoked_reason,
    )


@router.get("/admin/feedback", response_model=AdminFeedbackListResponse)
async def list_admin_feedback(request: Request) -> AdminFeedbackListResponse:
    _require_admin(request)
    store = _company_store(request)
    if not hasattr(store, "list_feedback"):
        return AdminFeedbackListResponse(items=[])
    items = await store.list_feedback()
    return AdminFeedbackListResponse(items=[_public_feedback(request, item) for item in items])


@router.get("/admin/feedback/{feedback_id}/image", name="download_admin_feedback_image")
async def download_admin_feedback_image(
    request: Request,
    settings: SettingsDep,
    feedback_id: str,
) -> FileResponse:
    _require_admin(request)
    store = _company_store(request)
    if not hasattr(store, "get_feedback"):
        raise HTTPException(status_code=404, detail="Feedback not found")
    feedback = await store.get_feedback(feedback_id)
    if feedback is None or not feedback.image_stored_filename:
        raise HTTPException(status_code=404, detail="Feedback image not found")
    file_path = _feedback_storage_dir(settings) / Path(feedback.image_stored_filename).name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Feedback image file not found")
    return FileResponse(
        file_path,
        media_type=feedback.image_mime_type or "application/octet-stream",
        filename=feedback.image_original_filename or file_path.name,
    )


async def _upsert_audit_session(
    db: AsyncSession,
    *,
    user: CompanyUser,
    item: AuditIngestSession,
) -> None:
    existing = (
        await db.execute(select(AuditSession).where(AuditSession.local_session_id == item.id))
    ).scalar_one_or_none()
    values = {
        "user_id": user.id,
        "user_email": user.email,
        "user_display_name": user.display_name,
        "title": item.title or "",
        "workspace": item.workspace or "",
        "model_id": item.model_id,
        "provider_id": item.provider_id,
        "source_client_id": item.source_client_id or "",
    }
    if existing is None:
        db.add(AuditSession(local_session_id=item.id, **values))
    else:
        for key, value in values.items():
            setattr(existing, key, value)


async def _upsert_audit_message(db: AsyncSession, *, item: AuditIngestMessage) -> None:
    existing = (
        await db.execute(select(AuditMessage).where(AuditMessage.local_message_id == item.id))
    ).scalar_one_or_none()
    role = item.role or str(item.data.get("role", ""))
    values = {
        "local_session_id": item.session_id,
        "role": role,
        "data": item.data,
    }
    if existing is None:
        db.add(AuditMessage(local_message_id=item.id, **values))
    else:
        for key, value in values.items():
            setattr(existing, key, value)
        flag_modified(existing, "data")


async def _upsert_audit_file(db: AsyncSession, *, item: AuditIngestPart) -> None:
    data = item.data or {}
    if data.get("type") != "file":
        return
    existing = (
        await db.execute(select(AuditFile).where(AuditFile.local_part_id == item.id))
    ).scalar_one_or_none()
    values = {
        "local_message_id": item.message_id,
        "local_session_id": item.session_id,
        "name": str(data.get("name", "")),
        "original_path": str(data.get("path", "")),
        "source": str(data.get("source", "")),
        "mime_type": str(data.get("mime_type", "")),
        "size": int(data.get("size", 0) or 0),
        "content_hash": data.get("content_hash"),
    }
    if existing is None:
        db.add(AuditFile(local_part_id=item.id, **values))
    else:
        for key, value in values.items():
            setattr(existing, key, value)


async def _upsert_audit_tool_call(db: AsyncSession, *, item: AuditIngestPart) -> None:
    data = item.data or {}
    if data.get("type") != "tool":
        return
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    input_data = state.get("input", {})
    if not isinstance(input_data, dict):
        input_data = {"value": input_data}
    title = str(state.get("title") or "")
    output = state.get("output", "")
    existing = (
        await db.execute(select(AuditToolCall).where(AuditToolCall.local_part_id == item.id))
    ).scalar_one_or_none()
    values = {
        "local_message_id": item.message_id,
        "local_session_id": item.session_id,
        "tool_name": str(data.get("tool") or data.get("name") or ""),
        "call_id": str(data.get("call_id") or ""),
        "status": str(state.get("status") or ""),
        "input_json": input_data,
        "output_preview": _preview(
            {
                "title": title,
                "input": input_data,
                "output": output,
            },
            limit=4000,
        ),
        "title": title,
        "metadata_json": state.get("metadata") if isinstance(state.get("metadata"), dict) else {},
    }
    if existing is None:
        db.add(AuditToolCall(local_part_id=item.id, **values))
    else:
        for key, value in values.items():
            setattr(existing, key, value)
        flag_modified(existing, "input_json")
        flag_modified(existing, "metadata_json")


async def _upsert_audit_usage(db: AsyncSession, *, item: AuditIngestPart) -> None:
    data = item.data or {}
    if data.get("type") != "step-finish":
        return
    tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else {}
    input_tokens = _token_value(tokens, "input", "input_tokens", "prompt_tokens")
    output_tokens = _token_value(tokens, "output", "output_tokens", "completion_tokens")
    reasoning_tokens = _token_value(tokens, "reasoning", "reasoning_tokens")
    cache_read_tokens = _token_value(tokens, "cache_read", "cache_read_tokens", "cached_input_tokens")
    cache_write_tokens = _token_value(tokens, "cache_write", "cache_write_tokens")
    total_tokens = _token_value(tokens, "total", "total_tokens")
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens + reasoning_tokens
    try:
        cost = float(data.get("cost") or 0)
    except (TypeError, ValueError):
        cost = 0.0

    existing = (
        await db.execute(select(AuditUsage).where(AuditUsage.local_part_id == item.id))
    ).scalar_one_or_none()
    values = {
        "local_message_id": item.message_id,
        "local_session_id": item.session_id,
        "finish_reason": str(data.get("reason") or ""),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "total_tokens": total_tokens,
        "cost": cost,
    }
    if existing is None:
        db.add(AuditUsage(local_part_id=item.id, **values))
    else:
        for key, value in values.items():
            setattr(existing, key, value)


async def _upsert_audit_risks(db: AsyncSession, *, item: AuditIngestPart) -> None:
    for finding in _detect_risks(item):
        stable_key = _risk_stable_key(item, kind=finding["kind"], evidence=finding["evidence_preview"])
        existing = (
            await db.execute(select(AuditRiskFinding).where(AuditRiskFinding.stable_key == stable_key))
        ).scalar_one_or_none()
        values = {
            "local_session_id": item.session_id,
            "local_message_id": item.message_id,
            "local_part_id": item.id,
            "kind": finding["kind"],
            "severity": finding["severity"],
            "summary": finding["summary"],
            "evidence_preview": finding["evidence_preview"],
        }
        if existing is None:
            db.add(AuditRiskFinding(stable_key=stable_key, status="open", **values))
        else:
            for key, value in values.items():
                setattr(existing, key, value)


async def _upsert_audit_part(db: AsyncSession, *, item: AuditIngestPart) -> None:
    existing = (
        await db.execute(select(AuditPart).where(AuditPart.local_part_id == item.id))
    ).scalar_one_or_none()
    part_type = str((item.data or {}).get("type", ""))
    values = {
        "local_message_id": item.message_id,
        "local_session_id": item.session_id,
        "part_type": part_type,
        "data": item.data,
    }
    if existing is None:
        db.add(AuditPart(local_part_id=item.id, **values))
    else:
        for key, value in values.items():
            setattr(existing, key, value)
        flag_modified(existing, "data")
    await _upsert_audit_file(db, item=item)
    await _upsert_audit_tool_call(db, item=item)
    await _upsert_audit_usage(db, item=item)
    await _upsert_audit_risks(db, item=item)


@router.post("/audit/ingest")
async def ingest_audit(
    request: Request,
    body: AuditIngestRequest,
    db: DbDep,
) -> dict[str, int]:
    user = _current_company_user(request)
    for item in body.sessions:
        await _upsert_audit_session(db, user=user, item=item)
    for item in body.messages:
        await _upsert_audit_message(db, item=item)
    for item in body.parts:
        await _upsert_audit_part(db, item=item)
    await db.flush()
    return {
        "sessions": len(body.sessions),
        "messages": len(body.messages),
        "parts": len(body.parts),
    }


@router.post("/audit/files/upload")
async def upload_audit_file(
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    part_id: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    user = _current_company_user(request)
    record = (
        await db.execute(select(AuditFile).where(AuditFile.local_part_id == part_id))
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Audit file record not found")

    session = (
        await db.execute(select(AuditSession).where(AuditSession.local_session_id == record.local_session_id))
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Audit session not found")
    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Cannot upload a file for another user")

    max_bytes = settings.audit_file_upload_max_bytes
    storage_dir = _audit_storage_dir(settings)
    storage_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(file.filename or record.name)
    destination = storage_dir / f"{generate_ulid()}_{safe_name}"
    temp_destination = destination.with_suffix(destination.suffix + ".tmp")
    digest = hashlib.sha256()
    size = 0
    try:
        with temp_destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="Audit file is larger than the configured limit")
                digest.update(chunk)
                output.write(chunk)
        temp_destination.replace(destination)
    except Exception:
        temp_destination.unlink(missing_ok=True)
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise

    record.name = safe_name
    record.size = size
    record.mime_type = file.content_type or mimetypes.guess_type(safe_name)[0] or record.mime_type or "application/octet-stream"
    record.content_hash = digest.hexdigest()
    record.stored_path = str(destination)
    record.content_uploaded = True
    await db.flush()

    return {
        "part_id": part_id,
        "uploaded": True,
        "name": record.name,
        "size": record.size,
        "content_hash": record.content_hash,
    }


@router.get("/admin/audit/sessions")
async def list_audit_sessions(
    request: Request,
    db: DbDep,
    q: str = "",
    user_id: str | None = None,
    workspace: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    _require_admin(request)
    stmt = select(AuditSession)
    count_stmt = select(func.count()).select_from(AuditSession)
    filters = []
    if user_id:
        filters.append(AuditSession.user_id == user_id)
    if workspace:
        filters.append(AuditSession.workspace.like(f"%{workspace}%"))
    if q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(AuditSession.title.like(pattern), AuditSession.workspace.like(pattern), AuditSession.user_email.like(pattern)))
    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    stmt = stmt.order_by(AuditSession.time_updated.desc()).offset(offset).limit(min(max(limit, 1), 200))
    total = (await db.execute(count_stmt)).scalar_one()
    rows = list((await db.execute(stmt)).scalars().all())
    return {
        "total": total,
        "items": [
            {
                "id": row.local_session_id,
                "title": row.title,
                "workspace": row.workspace,
                "user_id": row.user_id,
                "user_email": row.user_email,
                "user_display_name": row.user_display_name,
                "model_id": row.model_id,
                "provider_id": row.provider_id,
                "time_created": row.time_created.isoformat(),
                "time_updated": row.time_updated.isoformat(),
            }
            for row in rows
        ],
    }


@router.get("/admin/audit/summary")
async def get_audit_summary(
    request: Request,
    db: DbDep,
) -> dict[str, Any]:
    _require_admin(request)
    now = datetime.now(timezone.utc)
    settings = getattr(request.app.state, "settings", None)
    activity_days = []
    online_users: set[str] = set()
    online_sessions = 0
    store = getattr(request.app.state, "company_auth_store", None)
    presence = getattr(request.app.state, "company_presence", None)
    online_session_ids = await presence.online_session_ids() if presence is not None and presence.available else set()
    if store is not None and hasattr(store, "activity_days"):
        activity_days = await store.activity_days(days=30)
    if store is not None and hasattr(store, "list_sessions"):
        _, company_sessions = await store.list_sessions(include_revoked=False, limit=10_000)
        for session in company_sessions:
            if _is_session_online(session, now=now, online_session_ids=online_session_ids):
                online_sessions += 1
                online_users.add(session.user_id)

    usage = (
        await db.execute(
            select(
                func.coalesce(func.sum(AuditUsage.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(AuditUsage.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(AuditUsage.reasoning_tokens), 0).label("reasoning_tokens"),
                func.coalesce(func.sum(AuditUsage.cache_read_tokens), 0).label("cache_read_tokens"),
                func.coalesce(func.sum(AuditUsage.cache_write_tokens), 0).label("cache_write_tokens"),
                func.coalesce(func.sum(AuditUsage.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(AuditUsage.cost), 0).label("cost"),
            )
        )
    ).mappings().one()
    sessions_total = (await db.execute(select(func.count()).select_from(AuditSession))).scalar_one()
    messages_total = (await db.execute(select(func.count()).select_from(AuditMessage))).scalar_one()
    files_total = (await db.execute(select(func.count()).select_from(AuditFile))).scalar_one()
    files_uploaded = (
        await db.execute(select(func.count()).select_from(AuditFile).where(AuditFile.content_uploaded.is_(True)))
    ).scalar_one()
    tool_calls_total = (await db.execute(select(func.count()).select_from(AuditToolCall))).scalar_one()
    risks_total = (await db.execute(select(func.count()).select_from(AuditRiskFinding))).scalar_one()
    risks_open = (
        await db.execute(
            select(func.count()).select_from(AuditRiskFinding).where(AuditRiskFinding.status == "open")
        )
    ).scalar_one()
    today = now.date().isoformat()
    today_activity = next((item for item in activity_days if item.date == today), None)
    return {
        "sessions": {"total": sessions_total},
        "messages": {"total": messages_total},
        "files": {"total": files_total, "uploaded": files_uploaded},
        "tool_calls": {"total": tool_calls_total},
        "risks": {"total": risks_total, "open": risks_open},
        "activity": {
            "daily_active_users": today_activity.active_users if today_activity else 0,
            "online_users": len(online_users),
            "online_sessions": online_sessions,
            "redis": {
                "enabled": bool(getattr(settings, "redis_enabled", False)),
                "available": bool(presence is not None and presence.available),
            },
            "series": [
                {
                    "date": item.date,
                    "active_users": item.active_users,
                    "session_count": item.session_count,
                }
                for item in activity_days
            ],
        },
        "usage": {
            "input_tokens": int(usage["input_tokens"] or 0),
            "output_tokens": int(usage["output_tokens"] or 0),
            "reasoning_tokens": int(usage["reasoning_tokens"] or 0),
            "cache_read_tokens": int(usage["cache_read_tokens"] or 0),
            "cache_write_tokens": int(usage["cache_write_tokens"] or 0),
            "total_tokens": int(usage["total_tokens"] or 0),
            "cost": float(usage["cost"] or 0),
        },
    }


@router.get("/admin/audit/admin-actions", response_model=AdminActionListResponse)
async def list_admin_actions(
    request: Request,
    db: DbDep,
    action: str | None = None,
    actor_user_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AdminActionListResponse:
    _require_admin(request)
    stmt = select(AuditAdminAction)
    count_stmt = select(func.count()).select_from(AuditAdminAction)
    filters = []
    if action:
        filters.append(AuditAdminAction.action == action.strip())
    if actor_user_id:
        filters.append(AuditAdminAction.actor_user_id == actor_user_id.strip())
    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    stmt = stmt.order_by(AuditAdminAction.time_created.desc()).offset(max(0, int(offset or 0))).limit(
        min(max(int(limit or 100), 1), 500)
    )
    total = (await db.execute(count_stmt)).scalar_one()
    rows = list((await db.execute(stmt)).scalars().all())
    return AdminActionListResponse(total=int(total or 0), items=[_public_admin_action(row) for row in rows])


@router.get("/admin/audit/risks")
async def list_audit_risks(
    request: Request,
    db: DbDep,
    severity: str | None = None,
    status: str | None = None,
    kind: str | None = None,
    session_id: str | None = None,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    _require_admin(request)
    stmt = select(AuditRiskFinding, AuditSession).outerjoin(
        AuditSession,
        AuditSession.local_session_id == AuditRiskFinding.local_session_id,
    )
    count_stmt = select(func.count()).select_from(AuditRiskFinding)
    filters = []
    if severity:
        filters.append(AuditRiskFinding.severity == severity)
    if status:
        filters.append(AuditRiskFinding.status == status)
    if kind:
        filters.append(AuditRiskFinding.kind == kind)
    if session_id:
        filters.append(AuditRiskFinding.local_session_id == session_id)
    if q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                AuditRiskFinding.summary.like(pattern),
                AuditRiskFinding.evidence_preview.like(pattern),
                AuditRiskFinding.local_session_id.like(pattern),
            )
        )
    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    stmt = stmt.order_by(AuditRiskFinding.time_updated.desc()).offset(offset).limit(min(max(limit, 1), 200))
    total = (await db.execute(count_stmt)).scalar_one()
    rows = list((await db.execute(stmt)).all())
    return {
        "total": total,
        "items": [
            {
                "id": finding.id,
                "session_id": finding.local_session_id,
                "message_id": finding.local_message_id,
                "part_id": finding.local_part_id,
                "kind": finding.kind,
                "severity": finding.severity,
                "status": finding.status,
                "summary": finding.summary,
                "evidence_preview": finding.evidence_preview,
                "employee": (
                    {
                        "id": session.user_id,
                        "email": session.user_email,
                        "display_name": session.user_display_name,
                    }
                    if session is not None
                    else None
                ),
                "workspace": session.workspace if session is not None else "",
                "session_title": session.title if session is not None else "",
                "time_created": finding.time_created.isoformat(),
                "time_updated": finding.time_updated.isoformat(),
            }
            for finding, session in rows
        ],
    }


@router.get("/admin/audit/tool-calls")
async def list_audit_tool_calls(
    request: Request,
    db: DbDep,
    tool: str | None = None,
    status: str | None = None,
    session_id: str | None = None,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    _require_admin(request)
    stmt = select(AuditToolCall, AuditSession).outerjoin(
        AuditSession,
        AuditSession.local_session_id == AuditToolCall.local_session_id,
    )
    count_stmt = select(func.count()).select_from(AuditToolCall)
    filters = []
    if tool:
        filters.append(AuditToolCall.tool_name == tool)
    if status:
        filters.append(AuditToolCall.status == status)
    if session_id:
        filters.append(AuditToolCall.local_session_id == session_id)
    if q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                AuditToolCall.tool_name.like(pattern),
                AuditToolCall.title.like(pattern),
                AuditToolCall.output_preview.like(pattern),
                AuditToolCall.call_id.like(pattern),
            )
        )
    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    stmt = stmt.order_by(AuditToolCall.time_updated.desc()).offset(offset).limit(min(max(limit, 1), 200))
    total = (await db.execute(count_stmt)).scalar_one()
    rows = list((await db.execute(stmt)).all())
    return {
        "total": total,
        "items": [
            {
                "id": tool_call.id,
                "session_id": tool_call.local_session_id,
                "message_id": tool_call.local_message_id,
                "part_id": tool_call.local_part_id,
                "tool": tool_call.tool_name,
                "call_id": tool_call.call_id,
                "status": tool_call.status,
                "title": tool_call.title,
                "input": tool_call.input_json,
                "output_preview": tool_call.output_preview,
                "metadata": tool_call.metadata_json,
                "employee": (
                    {
                        "id": session.user_id,
                        "email": session.user_email,
                        "display_name": session.user_display_name,
                    }
                    if session is not None
                    else None
                ),
                "workspace": session.workspace if session is not None else "",
                "session_title": session.title if session is not None else "",
                "time_created": tool_call.time_created.isoformat(),
                "time_updated": tool_call.time_updated.isoformat(),
            }
            for tool_call, session in rows
        ],
    }


@router.get("/admin/audit/sessions/{session_id}/messages")
async def get_audit_session_messages(
    session_id: str,
    request: Request,
    db: DbDep,
) -> dict[str, Any]:
    _require_admin(request)
    messages = list(
        (
            await db.execute(
                select(AuditMessage)
                .where(AuditMessage.local_session_id == session_id)
                .order_by(AuditMessage.time_created.asc())
            )
        ).scalars().all()
    )
    message_ids = [message.local_message_id for message in messages]
    parts_by_message: dict[str, list[AuditPart]] = {message_id: [] for message_id in message_ids}
    files_by_part: dict[str, AuditFile] = {}
    tools_by_part: dict[str, AuditToolCall] = {}
    usage_by_part: dict[str, AuditUsage] = {}
    risks_by_part: dict[str, list[AuditRiskFinding]] = {}
    if message_ids:
        parts = list(
            (
                await db.execute(
                    select(AuditPart)
                    .where(AuditPart.local_message_id.in_(message_ids))
                    .order_by(AuditPart.time_created.asc())
                )
            ).scalars().all()
        )
        for part in parts:
            parts_by_message.setdefault(part.local_message_id, []).append(part)
        part_ids = [part.local_part_id for part in parts]
        if part_ids:
            files = list(
                (
                    await db.execute(select(AuditFile).where(AuditFile.local_part_id.in_(part_ids)))
                ).scalars().all()
            )
            files_by_part = {file.local_part_id: file for file in files}
            tools = list(
                (
                    await db.execute(select(AuditToolCall).where(AuditToolCall.local_part_id.in_(part_ids)))
                ).scalars().all()
            )
            tools_by_part = {tool.local_part_id: tool for tool in tools}
            usage_rows = list(
                (
                    await db.execute(select(AuditUsage).where(AuditUsage.local_part_id.in_(part_ids)))
                ).scalars().all()
            )
            usage_by_part = {usage.local_part_id: usage for usage in usage_rows}
            risk_rows = list(
                (
                    await db.execute(select(AuditRiskFinding).where(AuditRiskFinding.local_part_id.in_(part_ids)))
                ).scalars().all()
            )
            for risk in risk_rows:
                risks_by_part.setdefault(risk.local_part_id, []).append(risk)
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": message.local_message_id,
                "role": message.role,
                "data": message.data,
                "time_created": message.time_created.isoformat(),
                "parts": [
                    {
                        "id": part.local_part_id,
                        "type": part.part_type,
                        "data": part.data,
                        "tool_call": (
                            {
                                "tool": tools_by_part[part.local_part_id].tool_name,
                                "call_id": tools_by_part[part.local_part_id].call_id,
                                "status": tools_by_part[part.local_part_id].status,
                                "title": tools_by_part[part.local_part_id].title,
                                "input": tools_by_part[part.local_part_id].input_json,
                                "output_preview": tools_by_part[part.local_part_id].output_preview,
                                "metadata": tools_by_part[part.local_part_id].metadata_json,
                            }
                            if part.local_part_id in tools_by_part
                            else None
                        ),
                        "usage": (
                            {
                                "finish_reason": usage_by_part[part.local_part_id].finish_reason,
                                "input_tokens": usage_by_part[part.local_part_id].input_tokens,
                                "output_tokens": usage_by_part[part.local_part_id].output_tokens,
                                "reasoning_tokens": usage_by_part[part.local_part_id].reasoning_tokens,
                                "cache_read_tokens": usage_by_part[part.local_part_id].cache_read_tokens,
                                "cache_write_tokens": usage_by_part[part.local_part_id].cache_write_tokens,
                                "total_tokens": usage_by_part[part.local_part_id].total_tokens,
                                "cost": usage_by_part[part.local_part_id].cost,
                            }
                            if part.local_part_id in usage_by_part
                            else None
                        ),
                        "risks": [
                            {
                                "id": risk.id,
                                "kind": risk.kind,
                                "severity": risk.severity,
                                "status": risk.status,
                                "summary": risk.summary,
                                "evidence_preview": risk.evidence_preview,
                            }
                            for risk in risks_by_part.get(part.local_part_id, [])
                        ],
                        "file": (
                            {
                                "name": files_by_part[part.local_part_id].name,
                                "size": files_by_part[part.local_part_id].size,
                                "mime_type": files_by_part[part.local_part_id].mime_type,
                                "content_hash": files_by_part[part.local_part_id].content_hash,
                                "content_uploaded": files_by_part[part.local_part_id].content_uploaded,
                                "download_url": (
                                    f"/api/admin/audit/files/{part.local_part_id}/download"
                                    if files_by_part[part.local_part_id].content_uploaded
                                    else None
                                ),
                            }
                            if part.local_part_id in files_by_part
                            else None
                        ),
                        "time_created": part.time_created.isoformat(),
                    }
                    for part in parts_by_message.get(message.local_message_id, [])
                ],
            }
            for message in messages
        ],
    }


@router.get("/admin/audit/files/{part_id}/download")
async def download_audit_file(
    part_id: str,
    request: Request,
    db: DbDep,
) -> FileResponse:
    admin = _require_admin(request)
    record = (
        await db.execute(select(AuditFile).where(AuditFile.local_part_id == part_id))
    ).scalar_one_or_none()
    if record is None or not record.content_uploaded or not record.stored_path:
        raise HTTPException(status_code=404, detail="Audit file content not found")
    path = Path(record.stored_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audit file content missing from storage")
    media_type = record.mime_type or mimetypes.guess_type(record.name)[0] or "application/octet-stream"
    await _record_admin_action(
        db,
        user=admin,
        action="audit.file.download",
        target_type="audit_file",
        target_id=part_id,
        metadata={
            "name": record.name,
            "local_session_id": record.local_session_id,
            "local_message_id": record.local_message_id,
            "content_hash": record.content_hash,
            "size": record.size,
        },
    )
    await db.flush()
    return FileResponse(path, media_type=media_type, filename=record.name or path.name)
