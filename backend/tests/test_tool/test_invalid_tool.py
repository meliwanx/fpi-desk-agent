"""Invalid tool fallback tests."""

import pytest

from app.schemas.agent import AgentInfo
from app.tool.builtin.invalid import InvalidTool
from app.tool.context import ToolContext


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_id="test-session",
        message_id="test-msg",
        agent=AgentInfo(name="test", description="", mode="primary"),
        call_id="test-call",
    )


@pytest.mark.asyncio
async def test_invalid_tool_returns_guidance_without_user_visible_error() -> None:
    result = await InvalidTool().execute({"name": ""}, _make_ctx())

    assert result.success
    assert result.title == "工具不可用"
    assert "未命名工具" in result.output
    assert result.metadata["reason"] == "unknown_tool"
