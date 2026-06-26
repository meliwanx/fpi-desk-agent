"""Tests for desktop voice input API endpoints."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.asyncio


async def test_voice_transcribe_endpoint_returns_compat_shape(app_client, monkeypatch):
    from app.api import voice as voice_api
    from app.services.chat_voice import VoiceAssistResult

    captured = {}

    async def fake_process_voice_upload(
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: str,
        language_hint: str,
        settings,
    ) -> VoiceAssistResult:
        captured.update(
            {
                "audio_bytes": audio_bytes,
                "filename": filename,
                "content_type": content_type,
                "language_hint": language_hint,
                "settings": settings,
            }
        )
        return VoiceAssistResult(
            transcript="嗯请查一下昨天签到人数。",
            summary="请查一下昨天签到人数。",
            text="请查一下昨天签到人数。",
            summary_failed=False,
            summary_error="",
        )

    monkeypatch.setattr(voice_api, "process_voice_upload", fake_process_voice_upload)

    resp = await app_client.post(
        "/api/voice/transcribe",
        data={"language_hint": "zh"},
        files={"audio": ("voice.wav", b"RIFF....WAVEdata", "audio/wav")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "code": 0,
        "message": "语音处理完成",
        "data": {
            "transcript": "嗯请查一下昨天签到人数。",
            "summary": "请查一下昨天签到人数。",
            "text": "请查一下昨天签到人数。",
            "summary_failed": False,
            "summary_error": "",
        },
    }
    assert captured["audio_bytes"] == b"RIFF....WAVEdata"
    assert captured["filename"] == "voice.wav"
    assert captured["content_type"] == "audio/wav"
    assert captured["language_hint"] == "zh"


async def test_voice_assist_session_alias_uses_same_service(app_client, monkeypatch):
    from app.api import voice as voice_api
    from app.services.chat_voice import VoiceAssistResult

    called = {"count": 0}

    async def fake_process_voice_upload(*args, **kwargs) -> VoiceAssistResult:
        called["count"] += 1
        return VoiceAssistResult(
            transcript="原始文本",
            summary="整理文本",
            text="整理文本",
            summary_failed=False,
            summary_error="",
        )

    monkeypatch.setattr(voice_api, "process_voice_upload", fake_process_voice_upload)

    resp = await app_client.post(
        "/api/chat/sessions/test-session/voice-assist",
        data={"language_hint": "zh"},
        files={"audio": ("voice.wav", b"RIFF....WAVEdata", "audio/wav")},
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["text"] == "整理文本"
    assert called["count"] == 1


async def test_voice_transcribe_requires_audio(app_client):
    resp = await app_client.post("/api/voice/transcribe", data={"language_hint": "zh"})

    assert resp.status_code == 400
    assert resp.json()["message"] == "请选择语音文件"


async def test_summarize_transcript_uses_minimax_tool_contract(monkeypatch):
    from app.services import chat_voice

    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "return_correction",
                                        "arguments": json.dumps(
                                            {
                                                "status": "ok",
                                                "text": "请把代码提交到 GitHub，并检查分支。",
                                                "reason": "修复术语和重复短语。",
                                            },
                                            ensure_ascii=False,
                                        ),
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(chat_voice.httpx, "AsyncClient", FakeClient)

    summary, failed, error = await chat_voice.summarize_transcript(
        "你把那个代码代码提交到给它哈布上，还有就是检查一下分支。",
        settings=SimpleNamespace(
            minimax_api_key="test-minimax-key",
            minimax_base_url="https://api.minimaxi.com/v1",
            minimax_text_model="MiniMax-M3",
            chat_voice_minimax_timeout_seconds=20,
        ),
    )

    assert failed is False
    assert error == ""
    assert summary == "请把代码提交到 GitHub，并检查分支。"
    request_payload = captured["json"]
    assert captured["url"] == "https://api.minimaxi.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-minimax-key"
    assert request_payload["model"] == "MiniMax-M3"
    assert request_payload["tools"][0]["function"]["name"] == "return_correction"
    assert "tool_choice" not in request_payload
    assert request_payload["thinking"] == {"type": "disabled"}
