"""Voice input API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from typing import Any

from app.dependencies import SettingsDep
from app.services.chat_voice import ChatVoiceError, process_voice_upload

router = APIRouter()


async def _voice_assist_response(
    *,
    audio: UploadFile | None,
    language_hint: str,
    settings,
) -> dict | JSONResponse:
    if audio is None:
        return JSONResponse(status_code=400, content={"code": 400, "message": "请选择语音文件"})

    try:
        audio_bytes = await audio.read()
        result = await process_voice_upload(
            audio_bytes,
            filename=audio.filename or "",
            content_type=audio.content_type or "",
            language_hint=language_hint,
            settings=settings,
        )
        return {
            "code": 0,
            "message": "语音处理完成",
            "data": result.to_dict(),
        }
    except ChatVoiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "message": exc.message},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"语音输入处理失败: {str(exc)}"},
        )


@router.post("/voice/transcribe", response_model=None)
async def transcribe_voice_input(
    settings: SettingsDep,
    audio: UploadFile | None = File(default=None),
    language_hint: str = Form(default="zh"),
) -> Any:
    """Transcribe a recorded voice input and return text for the composer."""
    return await _voice_assist_response(
        audio=audio,
        language_hint=language_hint,
        settings=settings,
    )


@router.post("/chat/sessions/{session_id}/voice-assist", response_model=None)
async def chat_session_voice_assist(
    session_id: str,
    settings: SettingsDep,
    audio: UploadFile | None = File(default=None),
    language_hint: str = Form(default="zh"),
) -> Any:
    """Compatibility endpoint matching the existing web-agent voice API."""
    _ = session_id
    return await _voice_assist_response(
        audio=audio,
        language_hint=language_hint,
        settings=settings,
    )
