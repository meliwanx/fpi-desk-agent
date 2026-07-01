"""Tests for client-side audit sync hooks."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

import app.audit.client as audit_client
from app.audit.client import AuditContext, reset_audit_context, set_audit_context
from app.config import Settings
from app.dependencies import set_session_factory
from app.models.audit import AuditOutboxItem
from app.session.manager import create_message, create_part, create_session

pytestmark = pytest.mark.asyncio


async def test_session_message_and_part_creation_schedule_audit_sync(db, monkeypatch):
    sent: list[dict] = []

    async def fake_send_audit_payload(**kwargs):
        sent.append(kwargs["payload"])

    monkeypatch.setattr(audit_client, "_send_audit_payload", fake_send_audit_payload)
    monkeypatch.setattr(
        audit_client,
        "get_settings",
        lambda: Settings(
            audit_sync_enabled=True,
            audit_server_url="http://audit.example.test",
            audit_sync_timeout=1,
        ),
    )

    token = set_audit_context(AuditContext(company_session_token="company-session-token"))
    try:
        session = await create_session(db, id="session-1", directory="/workspace", title="Audit")
        message = await create_message(db, session_id=session.id, data={"role": "user"})
        await create_part(
            db,
            message_id=message.id,
            session_id=session.id,
            part_id="part-1",
            data={"type": "text", "text": "hello"},
        )
        await asyncio.sleep(0)
    finally:
        reset_audit_context(token)

    assert {"sessions": [{"id": "session-1", "title": "Audit", "workspace": "/workspace", "model_id": None, "provider_id": None}]} in sent
    assert {"messages": [{"id": message.id, "session_id": "session-1", "role": "user", "data": {"role": "user"}}]} in sent
    assert {"parts": [{"id": "part-1", "message_id": message.id, "session_id": "session-1", "data": {"type": "text", "text": "hello"}}]} in sent


async def test_send_audit_payload_uploads_file_part(tmp_path, monkeypatch):
    attached = tmp_path / "report.txt"
    attached.write_text("audit file content", encoding="utf-8")
    posts: list[dict] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, **kwargs):
            captured = {"url": url, **kwargs}
            upload = kwargs.get("files", {}).get("file")
            if upload is not None:
                filename, handle, mime_type = upload
                captured["uploaded_name"] = filename
                captured["uploaded_mime_type"] = mime_type
                captured["uploaded_content"] = handle.read()
            posts.append(captured)
            return FakeResponse()

    monkeypatch.setattr(audit_client.httpx, "AsyncClient", FakeClient)

    await audit_client._send_audit_payload(
        server_url="http://audit.example.test",
        company_session_token="company-session-token",
        payload={
            "parts": [
                {
                    "id": "part-file-1",
                    "message_id": "message-1",
                    "session_id": "session-1",
                    "data": {
                        "type": "file",
                        "name": "report.txt",
                        "path": str(attached),
                        "size": attached.stat().st_size,
                        "mime_type": "text/plain",
                    },
                }
            ]
        },
        timeout=1,
        file_upload_enabled=True,
        max_file_bytes=1024,
    )

    assert posts[0]["url"] == "http://audit.example.test/api/audit/ingest"
    assert posts[1]["url"] == "http://audit.example.test/api/audit/files/upload"
    assert posts[1]["headers"] == {"X-FPI-Session": "company-session-token"}
    assert posts[1]["data"] == {"part_id": "part-file-1"}
    assert posts[1]["uploaded_name"] == "report.txt"
    assert posts[1]["uploaded_mime_type"] == "text/plain"
    assert posts[1]["uploaded_content"] == b"audit file content"


async def test_schedule_audit_ingest_persists_failed_payload_for_retry(session_factory, monkeypatch):
    sent: list[dict] = []

    async def fake_send_audit_payload(**kwargs):
        sent.append(kwargs["payload"])
        raise RuntimeError("audit server offline")

    set_session_factory(session_factory)
    monkeypatch.setattr(audit_client, "_send_audit_payload", fake_send_audit_payload)
    monkeypatch.setattr(
        audit_client,
        "get_settings",
        lambda: Settings(
            audit_sync_enabled=True,
            audit_server_url="http://audit.example.test",
            audit_sync_timeout=1,
        ),
    )

    token = set_audit_context(AuditContext(company_session_token="company-session-token"))
    try:
        audit_client.schedule_audit_ingest({"parts": [{"id": "part-queued", "data": {"type": "text", "text": "hello"}}]})
        for _ in range(20):
            await asyncio.sleep(0.01)
            if sent:
                break
    finally:
        reset_audit_context(token)

    async with session_factory() as db:
        rows = list((await db.execute(select(AuditOutboxItem))).scalars().all())

    assert sent == [{"parts": [{"id": "part-queued", "data": {"type": "text", "text": "hello"}}]}]
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert rows[0].attempts == 1
    assert "audit server offline" in rows[0].last_error


async def test_flush_audit_outbox_uploads_pending_file_and_removes_success(tmp_path, session_factory, monkeypatch):
    generated = tmp_path / "analysis.xlsx"
    generated.write_bytes(b"generated-data")
    sent: list[dict] = []

    async def fake_send_audit_payload(**kwargs):
        sent.append(kwargs["payload"])

    async with session_factory() as db:
        async with db.begin():
            db.add(
                AuditOutboxItem(
                    server_url="http://audit.example.test",
                    company_session_token="company-session-token",
                    payload={
                        "parts": [
                            {
                                "id": "generated-file-part",
                                "message_id": "assistant-message",
                                "session_id": "session-1",
                                "data": {
                                    "type": "file",
                                    "name": "analysis.xlsx",
                                    "path": str(generated),
                                    "source": "generated",
                                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    "size": generated.stat().st_size,
                                },
                            }
                        ]
                    }
                )
            )

    monkeypatch.setattr(audit_client, "_send_audit_payload", fake_send_audit_payload)

    result = await audit_client.flush_audit_outbox_once(
        session_factory,
        Settings(
            audit_sync_enabled=True,
            audit_server_url="http://audit.example.test",
            audit_sync_timeout=1,
        ),
    )

    async with session_factory() as db:
        remaining = list((await db.execute(select(AuditOutboxItem))).scalars().all())

    assert result == {"attempted": 1, "succeeded": 1, "failed": 0}
    assert sent[0]["parts"][0]["data"]["source"] == "generated"
    assert remaining == []


async def test_schedule_generated_file_audit_enqueues_generated_file_part(tmp_path, session_factory, monkeypatch):
    generated = tmp_path / "report.pdf"
    generated.write_bytes(b"%PDF generated")

    set_session_factory(session_factory)
    monkeypatch.setattr(
        audit_client,
        "get_settings",
        lambda: Settings(
            audit_sync_enabled=True,
            audit_server_url="http://audit.example.test",
            audit_sync_timeout=1,
        ),
    )

    async def fake_flush(*args, **kwargs):
        return {"attempted": 0, "succeeded": 0, "failed": 0}

    monkeypatch.setattr(audit_client, "flush_audit_outbox_once", fake_flush)

    token = set_audit_context(AuditContext(company_session_token="company-session-token"))
    try:
        audit_client.schedule_generated_file_audit(
            session_id="session-1",
            message_id="assistant-message",
            file_path=str(generated),
            tool_id="artifact",
        )
        await asyncio.sleep(0)
    finally:
        reset_audit_context(token)

    async with session_factory() as db:
        row = (await db.execute(select(AuditOutboxItem))).scalar_one()

    part = row.payload["parts"][0]
    assert part["message_id"] == "assistant-message"
    assert part["session_id"] == "session-1"
    assert part["data"]["type"] == "file"
    assert part["data"]["source"] == "generated"
    assert part["data"]["name"] == "report.pdf"
    assert part["data"]["tool"] == "artifact"
