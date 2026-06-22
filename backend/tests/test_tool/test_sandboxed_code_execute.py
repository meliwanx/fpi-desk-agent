from __future__ import annotations

from app.schemas.agent import AgentInfo
from app.sandbox.manager import SandboxCommandResult, SandboxUnavailable
from app.tool.builtin import code_execute as code_execute_module
from app.tool.builtin.code_execute import CodeExecuteTool
from app.tool.context import ToolContext


class FakeSandboxManager:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def is_enabled(self) -> bool:
        return True

    def is_required(self) -> bool:
        return True

    async def run_python(self, **kwargs) -> SandboxCommandResult:
        self.calls.append(kwargs)
        return SandboxCommandResult(
            output="sandbox python",
            exit_code=0,
            metadata={"container_name": "fpi-desk-sandbox-python"},
        )


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_id="session-1",
        message_id="message-1",
        agent=AgentInfo(name="test", description="", mode="primary"),
        call_id="call-1",
    )


async def test_code_execute_uses_sandbox_manager_when_enabled(monkeypatch) -> None:
    fake = FakeSandboxManager()
    monkeypatch.setattr(code_execute_module, "get_sandbox_manager", lambda: fake, raising=False)

    result = await CodeExecuteTool().execute({"code": "print('host')"}, _make_ctx())

    assert result.output == "sandbox python"
    assert result.metadata["exit_code"] == 0
    assert result.metadata["sandbox"]["used"] is True
    assert result.metadata["sandbox"]["container_name"] == "fpi-desk-sandbox-python"
    assert fake.calls[0]["code"] == "print('host')"
    assert fake.calls[0]["session_id"] == "session-1"


async def test_code_execute_required_sandbox_does_not_fall_back_to_host(monkeypatch) -> None:
    class RequiredUnavailableManager:
        def is_enabled(self) -> bool:
            return True

        def is_required(self) -> bool:
            return True

        async def run_python(self, **kwargs) -> SandboxCommandResult:
            raise SandboxUnavailable("Docker is not installed")

    monkeypatch.setattr(
        code_execute_module,
        "get_sandbox_manager",
        lambda: RequiredUnavailableManager(),
        raising=False,
    )

    result = await CodeExecuteTool().execute({"code": "print('host')"}, _make_ctx())

    assert result.output == ""
    assert result.error == "Sandbox unavailable: Docker is not installed"
    assert result.metadata["sandbox"]["required"] is True
