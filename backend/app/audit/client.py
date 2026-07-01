"""Client-side audit sync helpers for desktop backends."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import timedelta
import logging
import mimetypes
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.models.audit import AuditOutboxItem
from app.utils.id import generate_ulid
from app.utils.timezone import shanghai_now

logger = logging.getLogger(__name__)

_flush_lock = asyncio.Lock()


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


def _payload_with_context(payload: dict[str, Any], context: AuditContext) -> dict[str, Any]:
    if not context.source_client_id:
        return payload
    cloned = dict(payload)
    sessions: list[dict[str, Any]] = []
    changed = False
    for raw in payload.get("sessions") or []:
        if not isinstance(raw, dict):
            sessions.append(raw)
            continue
        item = dict(raw)
        if not item.get("source_client_id"):
            item["source_client_id"] = context.source_client_id
            changed = True
        sessions.append(item)
    if changed:
        cloned["sessions"] = sessions
    return cloned


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
        _enqueue_and_flush(
            payload=_payload_with_context(payload, context),
            server_url=server_url,
            company_session_token=context.company_session_token,
            settings=settings,
        ),
        name="audit-outbox-enqueue",
    )


def schedule_generated_file_audit(
    *,
    session_id: str,
    message_id: str,
    file_path: str,
    tool_id: str,
) -> None:
    """Queue an audit file part for an AI-generated local file."""
    path = Path(file_path).expanduser()
    try:
        stat = path.stat()
    except OSError:
        return
    if not path.is_file():
        return
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    schedule_audit_ingest(
        {
            "parts": [
                {
                    "id": generate_ulid(),
                    "message_id": message_id,
                    "session_id": session_id,
                    "data": {
                        "type": "file",
                        "name": path.name,
                        "path": str(path),
                        "source": "generated",
                        "mime_type": mime_type,
                        "size": stat.st_size,
                        "tool": tool_id,
                    },
                }
            ]
        }
    )


async def _enqueue_and_flush(
    *,
    payload: dict[str, Any],
    server_url: str,
    company_session_token: str,
    settings: Settings,
) -> None:
    try:
        from app.dependencies import get_session_factory

        session_factory = get_session_factory()
    except Exception:
        try:
            await _send_audit_payload(
                server_url=server_url,
                company_session_token=company_session_token,
                payload=payload,
                timeout=settings.audit_sync_timeout,
                file_upload_enabled=settings.audit_file_upload_enabled,
                max_file_bytes=settings.audit_file_upload_max_bytes,
            )
        except Exception as exc:
            logger.warning("Audit sync failed before outbox was available: %s", exc)
        return

    await enqueue_audit_payload(
        session_factory,
        payload=payload,
        server_url=server_url,
        company_session_token=company_session_token,
    )
    await flush_audit_outbox_once(session_factory, settings)


async def enqueue_audit_payload(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    payload: dict[str, Any],
    server_url: str,
    company_session_token: str,
) -> str:
    async with session_factory() as db:
        async with db.begin():
            item = AuditOutboxItem(
                payload=payload,
                server_url=server_url.rstrip("/"),
                company_session_token=company_session_token,
                status="pending",
                next_attempt_at=shanghai_now(),
            )
            db.add(item)
        return item.id


def _retry_after_seconds(attempts: int) -> int:
    return min(3600, max(5, 2 ** max(attempts - 1, 0) * 5))


async def flush_audit_outbox_once(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings | None = None,
    *,
    limit: int = 20,
) -> dict[str, int]:
    settings = settings or get_settings()
    if not settings.audit_sync_enabled:
        return {"attempted": 0, "succeeded": 0, "failed": 0}

    now = shanghai_now()
    async with _flush_lock:
        async with session_factory() as db:
            async with db.begin():
                rows = list(
                    (
                        await db.execute(
                            select(AuditOutboxItem)
                            .where(AuditOutboxItem.status.in_(("pending", "failed")))
                            .where(
                                or_(
                                    AuditOutboxItem.next_attempt_at.is_(None),
                                    AuditOutboxItem.next_attempt_at <= now,
                                )
                            )
                            .order_by(AuditOutboxItem.time_created.asc())
                            .limit(max(1, limit))
                        )
                    ).scalars().all()
                )
                attempts = []
                for row in rows:
                    row.status = "uploading"
                    row.attempts += 1
                    attempts.append(
                        {
                            "id": row.id,
                            "payload": row.payload,
                            "server_url": row.server_url or settings.audit_server_url.strip().rstrip("/"),
                            "company_session_token": row.company_session_token,
                            "attempts": row.attempts,
                        }
                    )

        succeeded = 0
        failed = 0
        for item in attempts:
            try:
                if not item["server_url"] or not item["company_session_token"]:
                    raise RuntimeError("audit outbox item missing server URL or company session token")
                await _send_audit_payload(
                    server_url=item["server_url"],
                    company_session_token=item["company_session_token"],
                    payload=item["payload"],
                    timeout=settings.audit_sync_timeout,
                    file_upload_enabled=settings.audit_file_upload_enabled,
                    max_file_bytes=settings.audit_file_upload_max_bytes,
                )
            except Exception as exc:
                failed += 1
                async with session_factory() as db:
                    async with db.begin():
                        row = await db.get(AuditOutboxItem, item["id"])
                        if row is not None:
                            row.status = "failed"
                            row.last_error = str(exc)
                            row.next_attempt_at = shanghai_now() + timedelta(seconds=_retry_after_seconds(item["attempts"]))
                logger.warning("Audit outbox upload failed: %s", exc)
            else:
                succeeded += 1
                async with session_factory() as db:
                    async with db.begin():
                        row = await db.get(AuditOutboxItem, item["id"])
                        if row is not None:
                            await db.delete(row)

        return {"attempted": len(attempts), "succeeded": succeeded, "failed": failed}


async def audit_outbox_worker(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    interval_seconds: float | None = None,
) -> None:
    interval = interval_seconds if interval_seconds is not None else settings.audit_outbox_flush_interval
    while True:
        try:
            await flush_audit_outbox_once(session_factory, settings)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Audit outbox worker failed: %s", exc)
        await asyncio.sleep(max(1.0, float(interval or 30.0)))


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
