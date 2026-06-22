"""Session processor tool-call normalization tests."""

from app.session.processor import _repair_streamed_tool_call


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
