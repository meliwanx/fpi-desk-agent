from __future__ import annotations

from app.schemas.agent import AgentInfo
from app.sandbox.manager import SandboxCommandResult, SandboxUnavailable
from app.tool.builtin import bash as bash_module
from app.tool.builtin.bash import BashTool
from app.tool.context import ToolContext


class FakeSandboxManager:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def is_enabled(self) -> bool:
        return True

    def is_required(self) -> bool:
        return True

    async def run_shell(self, **kwargs) -> SandboxCommandResult:
        self.calls.append(kwargs)
        return SandboxCommandResult(
            output="sandbox hello",
            exit_code=0,
            metadata={"container_name": "fpi-desk-sandbox-test", "sandbox_url": "http://127.0.0.1:28080"},
        )


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_id="session-1",
        message_id="message-1",
        agent=AgentInfo(name="test", description="", mode="primary"),
        call_id="call-1",
    )


async def test_bash_uses_sandbox_manager_when_enabled(monkeypatch) -> None:
    fake = FakeSandboxManager()
    monkeypatch.setattr(bash_module, "get_sandbox_manager", lambda: fake, raising=False)

    result = await BashTool().execute({"command": "echo host"}, _make_ctx())

    assert result.output == "sandbox hello"
    assert result.metadata["exit_code"] == 0
    assert result.metadata["sandbox"]["used"] is True
    assert result.metadata["sandbox"]["container_name"] == "fpi-desk-sandbox-test"
    assert fake.calls[0]["command"] == "echo host"
    assert fake.calls[0]["session_id"] == "session-1"


async def test_bash_required_sandbox_does_not_fall_back_to_host(monkeypatch) -> None:
    class RequiredUnavailableManager:
        def is_enabled(self) -> bool:
            return True

        def is_required(self) -> bool:
            return True

        async def run_shell(self, **kwargs) -> SandboxCommandResult:
            raise SandboxUnavailable("Docker is not installed")

    monkeypatch.setattr(
        bash_module,
        "get_sandbox_manager",
        lambda: RequiredUnavailableManager(),
        raising=False,
    )

    result = await BashTool().execute({"command": "echo host"}, _make_ctx())

    assert result.output == ""
    assert result.error == "Sandbox unavailable: Docker is not installed"
    assert result.metadata["sandbox"]["required"] is True
