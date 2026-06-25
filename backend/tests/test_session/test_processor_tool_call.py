"""Session processor edge-case tests."""

from app.session.processor import _repair_streamed_tool_call
from app.session.processor import SessionProcessor
from app.session.manager import create_message, create_session
from app.streaming.manager import GenerationJob
from types import SimpleNamespace

import pytest


def test_repair_streamed_tool_call_drops_blank_tool_name() -> None:
    repaired = _repair_streamed_tool_call({
        "id": "call_1",
        "name": "",
        "arguments": {"query": "hello"},
    })

    assert repaired is None


def test_repair_streamed_tool_call_recovers_function_wrapped_name() -> None:
    repaired = _repair_streamed_tool_call({
        "id": "call_1",
        "name": "",
        "arguments": [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "parameters": {"query": "workspace overview"},
                },
            }
        ],
    })

    assert repaired == {
        "id": "call_1",
        "name": "search",
        "arguments": {"query": "workspace overview"},
    }


@pytest.mark.asyncio
async def test_empty_model_stream_becomes_visible_error(session_factory) -> None:
    async with session_factory() as db:
        async with db.begin():
            await create_session(db, id="empty-stream-session")
            assistant = await create_message(
                db,
                session_id="empty-stream-session",
                data={
                    "role": "assistant",
                    "agent": "build",
                    "model_id": "gpt-5.5",
                    "provider_id": "custom_npimvg",
                },
            )

    job = GenerationJob("stream-empty", "empty-stream-session")
    processor = SessionProcessor(
        SimpleNamespace(
            job=job,
            session_factory=session_factory,
            total_cost=0.0,
            provider=SimpleNamespace(id="custom_npimvg"),
            model_id="gpt-5.5",
        ),
        [],
        assistant.id,
    )
    processor._accumulated_text = ""
    processor._accumulated_reasoning = ""
    processor._has_tool_calls = False
    processor._stream_error = None

    should_continue = await processor._handle_empty_output_after_retries()

    assert should_continue is False
    assert processor.finish_reason == "error"
    assert "custom_npimvg/gpt-5.5" in processor._accumulated_text
    event_names = [event.event for event in job.events]
    assert "text-delta" in event_names
    assert "agent-error" in event_names
