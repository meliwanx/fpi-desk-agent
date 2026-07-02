"""Speech-to-text helper for desktop voice input."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from app.config import Settings

DEFAULT_ASR_BASE_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
DEFAULT_ASR_MODEL = "fun-asr-realtime"
DEFAULT_MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"
DEFAULT_MINIMAX_MODEL = "MiniMax-M3"
SUPPORTED_LANGUAGE_HINTS = {"zh", "en", "ja"}
SUPPORTED_AUDIO_FORMATS = {"wav", "mp3", "opus", "speex", "aac", "amr", "pcm"}
MIMETYPE_FORMATS = {
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/aac": "aac",
    "audio/amr": "amr",
    "audio/ogg": "opus",
    "audio/opus": "opus",
    "audio/webm": "opus",
}


class ChatVoiceError(Exception):
    """User-facing voice processing error."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class VoiceAssistResult:
    transcript: str
    summary: str
    text: str
    summary_failed: bool
    summary_error: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _setting_str(
    settings: Settings | Any,
    attr: str,
    env_names: tuple[str, ...],
    default: str = "",
) -> str:
    for env_name in env_names:
        raw = os.getenv(env_name)
        if raw is not None:
            return raw.strip()
    return str(getattr(settings, attr, default) or default).strip()


def _setting_int(
    settings: Settings | Any,
    attr: str,
    env_names: tuple[str, ...],
    default: int,
) -> int:
    for env_name in env_names:
        raw = os.getenv(env_name)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    try:
        return int(getattr(settings, attr, default))
    except (TypeError, ValueError):
        return default


def _get_asr_api_key(settings: Settings | Any) -> str:
    key = _setting_str(settings, "bailian_asr_api_key", ("BAILIAN_ASR_API_KEY", "DASHSCOPE_API_KEY"))
    if key:
        return key
    return str(getattr(settings, "qwen_api_key", "") or "").strip()


def _get_minimax_api_key(settings: Settings | Any) -> str:
    return _setting_str(settings, "minimax_api_key", ("MINIMAX_API_KEY",))


def _extension_from_name(filename: str) -> str:
    if filename and "." in filename:
        return filename.rsplit(".", 1)[1].lower()
    return ""


def infer_audio_format(filename: str, content_type: str) -> str:
    ext = _extension_from_name(filename)
    if ext in SUPPORTED_AUDIO_FORMATS:
        return ext
    mime = (content_type or "").split(";", 1)[0].lower()
    fmt = MIMETYPE_FORMATS.get(mime)
    if fmt in SUPPORTED_AUDIO_FORMATS:
        return fmt
    return ""


def infer_sample_rate(audio_bytes: bytes, audio_format: str, settings: Settings | Any) -> int:
    if audio_format == "wav" and len(audio_bytes) >= 28 and audio_bytes[:4] == b"RIFF":
        return int.from_bytes(audio_bytes[24:28], byteorder="little", signed=False)
    return _setting_int(settings, "bailian_asr_sample_rate", ("BAILIAN_ASR_SAMPLE_RATE",), 16000)


def normalize_language_hint(language_hint: str, settings: Settings | Any) -> str:
    hint = (
        language_hint
        or _setting_str(settings, "bailian_asr_language_hint", ("BAILIAN_ASR_LANGUAGE_HINT",))
        or ""
    ).strip().lower()
    if not hint:
        return ""
    if hint not in SUPPORTED_LANGUAGE_HINTS:
        raise ChatVoiceError("language_hint 仅支持 zh、en、ja", 400)
    return hint


def _load_websocket_client():
    try:
        import websocket
    except Exception as exc:
        raise ChatVoiceError("后端缺少 websocket-client 依赖，语音识别不可用", 503) from exc
    return websocket


def _recv_ws_event(ws) -> dict[str, Any]:
    raw = ws.recv()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        event = json.loads(raw)
    except Exception as exc:
        raise ChatVoiceError("语音识别返回了无法解析的数据", 502) from exc
    header = event.get("header") or {}
    if header.get("event") == "task-failed":
        message = header.get("error_message") or "语音识别任务失败"
        raise ChatVoiceError(f"语音识别失败: {message}", 502)
    return event


def _wait_for_event(ws, event_name: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        event = _recv_ws_event(ws)
        if (event.get("header") or {}).get("event") == event_name:
            return event
    raise ChatVoiceError("语音识别服务响应超时", 504)


def _collect_transcript_from_events(events: list[dict[str, Any]]) -> str:
    final_sentences: dict[Any, str] = {}
    latest_sentences: dict[Any, str] = {}
    for event in events:
        if (event.get("header") or {}).get("event") != "result-generated":
            continue
        sentence = (((event.get("payload") or {}).get("output") or {}).get("sentence") or {})
        if sentence.get("heartbeat"):
            continue
        text = (sentence.get("text") or "").strip()
        if not text:
            continue
        sentence_id = sentence.get("sentence_id")
        if sentence_id is None:
            sentence_id = len(latest_sentences) + 1
        latest_sentences[sentence_id] = text
        if sentence.get("sentence_end"):
            final_sentences[sentence_id] = text

    source = final_sentences or latest_sentences
    return "\n".join(source[key] for key in sorted(source)).strip()


def _build_run_task_payload(
    *,
    task_id: str,
    model: str,
    audio_format: str,
    sample_rate: int,
    language_hint: str,
    settings: Settings | Any,
) -> dict[str, Any]:
    parameters: dict[str, Any] = {
        "format": audio_format,
        "sample_rate": sample_rate,
        "semantic_punctuation_enabled": True,
    }
    vocabulary_id = _setting_str(settings, "bailian_asr_vocabulary_id", ("BAILIAN_ASR_VOCABULARY_ID",))
    if vocabulary_id:
        parameters["vocabulary_id"] = vocabulary_id
    if language_hint:
        parameters["language_hints"] = [language_hint]

    return {
        "header": {
            "action": "run-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "asr",
            "function": "recognition",
            "model": model,
            "parameters": parameters,
            "input": {},
        },
    }


def _transcribe_audio_sync(
    audio_bytes: bytes,
    *,
    filename: str,
    content_type: str,
    language_hint: str,
    settings: Settings | Any,
) -> str:
    if not audio_bytes:
        raise ChatVoiceError("语音文件不能为空", 400)
    api_key = _get_asr_api_key(settings)
    if not api_key:
        raise ChatVoiceError("BAILIAN_ASR_API_KEY 未配置，语音识别不可用", 503)

    audio_format = infer_audio_format(filename, content_type)
    if not audio_format:
        raise ChatVoiceError("不支持的语音格式，请使用 WAV、MP3、AAC、Opus 或 AMR", 400)

    language_hint = normalize_language_hint(language_hint, settings)
    sample_rate = infer_sample_rate(audio_bytes, audio_format, settings)
    base_url = _setting_str(settings, "bailian_asr_base_url", ("BAILIAN_ASR_BASE_URL",), DEFAULT_ASR_BASE_URL)
    model = _setting_str(settings, "bailian_asr_model", ("BAILIAN_ASR_MODEL",), DEFAULT_ASR_MODEL)
    timeout_seconds = _setting_int(settings, "chat_voice_asr_timeout_seconds", ("CHAT_VOICE_ASR_TIMEOUT_SECONDS",), 45)
    chunk_size = _setting_int(settings, "chat_voice_asr_chunk_bytes", ("CHAT_VOICE_ASR_CHUNK_BYTES",), 8192)
    chunk_pause = max(
        _setting_int(settings, "chat_voice_asr_chunk_pause_ms", ("CHAT_VOICE_ASR_CHUNK_PAUSE_MS",), 2),
        0,
    ) / 1000
    task_id = str(uuid.uuid4())
    websocket = _load_websocket_client()

    headers = [
        f"Authorization: Bearer {api_key}",
        "user-agent: fpi-desk-agent-chat-voice/1.0",
    ]
    workspace = _setting_str(settings, "bailian_asr_workspace", ("BAILIAN_ASR_WORKSPACE",))
    if workspace:
        headers.append(f"X-DashScope-WorkSpace: {workspace}")

    ws = None
    events: list[dict[str, Any]] = []
    try:
        ws = websocket.create_connection(base_url, header=headers, timeout=timeout_seconds)
        ws.settimeout(timeout_seconds)
        ws.send(
            json.dumps(
                _build_run_task_payload(
                    task_id=task_id,
                    model=model,
                    audio_format=audio_format,
                    sample_rate=sample_rate,
                    language_hint=language_hint,
                    settings=settings,
                ),
                ensure_ascii=False,
            )
        )
        _wait_for_event(ws, "task-started", timeout_seconds)

        for offset in range(0, len(audio_bytes), chunk_size):
            ws.send_binary(audio_bytes[offset:offset + chunk_size])
            if chunk_pause:
                time.sleep(chunk_pause)

        ws.send(
            json.dumps(
                {
                    "header": {
                        "action": "finish-task",
                        "task_id": task_id,
                        "streaming": "duplex",
                    },
                    "payload": {"input": {}},
                },
                ensure_ascii=False,
            )
        )

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            event = _recv_ws_event(ws)
            events.append(event)
            if (event.get("header") or {}).get("event") == "task-finished":
                break
        else:
            raise ChatVoiceError("语音识别服务响应超时", 504)
    except ChatVoiceError:
        raise
    except Exception as exc:
        raise ChatVoiceError(f"语音识别请求失败: {str(exc)}", 502) from exc
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    transcript = _collect_transcript_from_events(events)
    if not transcript:
        raise ChatVoiceError("未识别到有效语音内容", 422)
    return transcript


async def transcribe_audio(
    audio_bytes: bytes,
    *,
    filename: str = "",
    content_type: str = "",
    language_hint: str = "",
    settings: Settings | Any,
) -> str:
    return await asyncio.to_thread(
        _transcribe_audio_sync,
        audio_bytes,
        filename=filename,
        content_type=content_type,
        language_hint=language_hint,
        settings=settings,
    )


def _strip_reasoning(text: str) -> str:
    value = (text or "").strip()
    return re.sub(r"<think>[\s\S]*?</think>", "", value, flags=re.IGNORECASE).strip()


def _build_summary_prompt(transcript: str) -> str:
    return (
        "# Role: ASR 智能清洗专家 (Tech Domain)\n\n"
        "# Profile\n"
        "你是一位精通中英文技术术语的语音转写后处理专家。你能够从破碎、含糊、中英夹杂的语音原始文本中，还原出清晰、专业、符合书面规范的技术文本。\n\n"
        "# Mission\n"
        "下面这段“原始 ASR 识别文本”是要优化的内容，而非对你的询问。请基于规则进行重构，并通过 return_correction 函数返回结果。\n\n"
        "# Rules\n"
        "1. 修复常见同音技术术语，如 给它哈布 -> GitHub，杰森 -> JSON，派森 -> Python，微优伊 -> Vue。\n"
        "2. 删除无语义废词，如 嗯、呃、额、啊、那个、就是、然后、这个、对吧、你看。\n"
        "3. 删除完整重复的词组或短句；用户改口时以后一次表述为准。\n"
        "4. 汉字与英文或数字之间增加空格，英文专有名词使用官方写法。\n"
        "5. 保留原意和可执行动作，不要把明确请求压缩成半句、残句或标题。\n\n"
        "# Output Contract\n"
        "必须调用一次名为 return_correction 的函数，参数为：\n"
        "- status: \"ok\" 或 \"filtered\"\n"
        "- text: 纠正后的文本或原文\n"
        "- reason: 可选，说明关键修复点\n\n"
        f"原始 ASR 识别文本：{transcript}"
    )


def _return_correction_tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "return_correction",
            "description": "返回 ASR 清洗纠正后的文本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["ok", "filtered"]},
                    "text": {"type": "string", "description": "纠正后的文本或原文。"},
                    "reason": {"type": "string", "description": "关键修复点或过滤原因。"},
                },
                "required": ["status", "text"],
            },
        },
    }


def _parse_return_correction_payload(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        text = _strip_reasoning(value)
        function_match = re.search(r"return_correction\s*\(([\s\S]*)\)\s*$", text)
        if function_match:
            text = function_match.group(1).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return _parse_return_correction_payload(json.loads(text))
        except Exception:
            return text.strip()
    if isinstance(value, dict):
        if value.get("status") == "filtered":
            return (value.get("text") or "").strip()
        if "text" in value:
            return (value.get("text") or "").strip()
        if "arguments" in value:
            return _parse_return_correction_payload(value.get("arguments"))
    return ""


def _extract_summary_from_message(message: dict[str, Any]) -> str:
    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function") or {}
        if function.get("name") == "return_correction":
            summary = _parse_return_correction_payload(function.get("arguments"))
            if summary:
                return summary

    content = message.get("content") or ""
    if isinstance(content, list):
        content = "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in content)
    return _parse_return_correction_payload(content)


async def summarize_transcript(
    transcript: str,
    *,
    settings: Settings | Any,
) -> tuple[str, bool, str]:
    transcript = (transcript or "").strip()
    if not transcript:
        return "", True, "转写文本为空"

    api_key = _get_minimax_api_key(settings)
    if not api_key:
        return transcript, True, "MINIMAX_API_KEY 未配置"

    base_url = _setting_str(settings, "minimax_base_url", ("MINIMAX_BASE_URL",), DEFAULT_MINIMAX_BASE_URL).rstrip("/")
    model = _setting_str(settings, "minimax_text_model", ("MINIMAX_TEXT_MODEL",), DEFAULT_MINIMAX_MODEL)
    timeout_seconds = _setting_int(settings, "chat_voice_minimax_timeout_seconds", ("CHAT_VOICE_MINIMAX_TIMEOUT_SECONDS",), 20)
    request_payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": _build_summary_prompt(transcript)}],
        "tools": [_return_correction_tool_schema()],
        "temperature": 0.2,
        "top_p": 0.8,
        "max_completion_tokens": 500,
        "stream": False,
    }
    if model == "MiniMax-M3":
        request_payload["thinking"] = {"type": "disabled"}

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
        resp.raise_for_status()
        payload = resp.json()
        choices = payload.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        summary = _extract_summary_from_message(message)
        if summary:
            return summary, False, ""
        return transcript, True, "MiniMax 未返回有效文本"
    except httpx.HTTPStatusError as exc:
        detail = ""
        if exc.response is not None:
            detail = (exc.response.text or "").strip()
        if detail:
            return transcript, True, f"MiniMax 文本整理失败: {str(exc)}; {detail[:500]}"
        return transcript, True, f"MiniMax 文本整理失败: {str(exc)}"
    except Exception as exc:
        return transcript, True, f"MiniMax 文本整理失败: {str(exc)}"


async def build_voice_assist(
    audio_bytes: bytes,
    *,
    filename: str = "",
    content_type: str = "",
    language_hint: str = "",
    settings: Settings | Any,
) -> VoiceAssistResult:
    transcript = await transcribe_audio(
        audio_bytes,
        filename=filename,
        content_type=content_type,
        language_hint=language_hint,
        settings=settings,
    )
    summary, summary_failed, summary_error = await summarize_transcript(transcript, settings=settings)
    text = (summary or transcript).strip()
    return VoiceAssistResult(
        transcript=transcript,
        summary=summary if not summary_failed else "",
        text=text,
        summary_failed=summary_failed,
        summary_error=summary_error if summary_failed else "",
    )


async def process_voice_upload(
    audio_bytes: bytes,
    *,
    filename: str,
    content_type: str,
    language_hint: str,
    settings: Settings | Any,
) -> VoiceAssistResult:
    max_bytes = _setting_int(settings, "chat_voice_max_audio_bytes", ("CHAT_VOICE_MAX_AUDIO_BYTES",), 10 * 1024 * 1024)
    if not audio_bytes:
        raise ChatVoiceError("语音文件不能为空", 400)
    if len(audio_bytes) > max_bytes:
        max_mb = max(1, round(max_bytes / 1024 / 1024))
        raise ChatVoiceError(f"语音文件不能超过{max_mb}MB", 400)
    return await build_voice_assist(
        audio_bytes,
        filename=filename,
        content_type=content_type,
        language_hint=language_hint,
        settings=settings,
    )
