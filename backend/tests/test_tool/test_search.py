"""Search tool tests."""

import pytest

from app.schemas.agent import AgentInfo
from app.tool.builtin.search import SearchTool
from app.tool.context import ToolContext


class _IndexManager:
    async def search(self, *args, **kwargs):  # pragma: no cover - should not be called here
        raise AssertionError("search index should not be called without a workspace")


def _make_ctx(*, workspace: str | None, index_manager=_IndexManager()) -> ToolContext:
    return ToolContext(
        session_id="test-session",
        message_id="test-msg",
        agent=AgentInfo(name="test", description="", mode="primary"),
        call_id="test-call",
        workspace=workspace,
        index_manager=index_manager,
    )


@pytest.mark.asyncio
async def test_search_without_workspace_returns_guidance_not_error() -> None:
    result = await SearchTool().execute(
        {"query": "workspace overview", "max_results": 1},
        _make_ctx(workspace=None),
    )

    assert result.success
    assert result.title == "未设置工作区"
    assert "无法使用工作区全文检索" in result.output
    assert "选择一个文件夹" in result.output
    assert result.metadata["reason"] == "workspace_required"


@pytest.mark.asyncio
async def test_search_without_workspace_takes_precedence_over_missing_index() -> None:
    result = await SearchTool().execute(
        {"query": "workspace overview", "max_results": 1},
        _make_ctx(workspace=None, index_manager=None),
    )

    assert result.success
    assert result.title == "未设置工作区"
