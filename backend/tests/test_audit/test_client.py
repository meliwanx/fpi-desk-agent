"""Tests for client-side audit sync hooks."""

from __future__ import annotations

import asyncio

import pytest

import app.audit.client as audit_client
from app.audit.client import AuditContext, reset_audit_context, set_audit_context
from app.config import Settings
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
