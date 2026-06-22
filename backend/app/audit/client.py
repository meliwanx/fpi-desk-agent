"""Client-side audit sync helpers for desktop backends."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from dataclasses import dataclass
import logging
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditContext:
    company_session_token: str
    source_client_id: str = ""


_audit_context: ContextVar[AuditContext | None] = ContextVar("audit_context", default=None)


def set_audit_context(context: AuditContext | None) -> Token[AuditContext | None]:
    return _audit_context.set(context)


def reset_audit_context(token: Token[AuditContext | None]) -> None:
    _audit_context.reset(token)


def current_audit_context() -> AuditContext | None:
    return _audit_context.get()


def schedule_audit_ingest(payload: dict[str, Any]) -> None:
    context = current_audit_context()
    if context is None or not context.company_session_token:
        return

    settings = get_settings()
    if not settings.audit_sync_enabled:
        return
    server_url = settings.audit_server_url.strip().rstrip("/")
    if not server_url:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    loop.create_task(
        _send_audit_payload(
            server_url=server_url,
            company_session_token=context.company_session_token,
            payload=payload,
            timeout=settings.audit_sync_timeout,
            file_upload_enabled=settings.audit_file_upload_enabled,
            max_file_bytes=settings.audit_file_upload_max_bytes,
        ),
        name="audit-sync",
    )


def _iter_uploadable_file_parts(
    payload: dict[str, Any],
    *,
    max_file_bytes: int,
) -> list[dict[str, Any]]:
    uploadable: list[dict[str, Any]] = []
    for part in payload.get("parts") or []:
        if not isinstance(part, dict):
            continue
        data = part.get("data") or {}
        if not isinstance(data, dict) or data.get("type") != "file":
            continue
        raw_path = str(data.get("path") or "")
        if not raw_path:
            continue
        file_path = Path(raw_path).expanduser()
        try:
            stat = file_path.stat()
        except OSError:
            continue
        if not file_path.is_file() or stat.st_size > max_file_bytes:
            continue
        name = str(data.get("name") or file_path.name)
        mime_type = str(data.get("mime_type") or mimetypes.guess_type(name)[0] or "application/octet-stream")
        uploadable.append({
            "part_id": str(part.get("id") or ""),
            "path": file_path,
            "name": name,
            "mime_type": mime_type,
        })
    return [item for item in uploadable if item["part_id"]]


async def _send_audit_payload(
    *,
    server_url: str,
    company_session_token: str,
    payload: dict[str, Any],
    timeout: float,
    file_upload_enabled: bool,
    max_file_bytes: int,
) -> None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{server_url}/api/audit/ingest",
                headers={"X-FPI-Session": company_session_token},
                json=payload,
            )
            response.raise_for_status()

            if not file_upload_enabled:
                return
            for item in _iter_uploadable_file_parts(payload, max_file_bytes=max_file_bytes):
                with item["path"].open("rb") as handle:
                    upload_response = await client.post(
                        f"{server_url}/api/audit/files/upload",
                        headers={"X-FPI-Session": company_session_token},
                        data={"part_id": item["part_id"]},
                        files={"file": (item["name"], handle, item["mime_type"])},
                    )
                    upload_response.raise_for_status()
    except Exception as exc:
        logger.warning("Audit sync failed: %s", exc)
