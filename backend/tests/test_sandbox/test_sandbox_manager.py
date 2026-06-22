from __future__ import annotations

import builtins
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import threading
import time

from app.config import Settings
from app.sandbox import manager as sandbox_module
from app.sandbox.manager import SandboxManager, SandboxUnavailable


def test_builds_deerflow_style_aio_container_command(tmp_path: Path) -> None:
    manager = SandboxManager(
        settings=Settings(
            sandbox_image="ghcr.io/agent-infra/sandbox:latest",
            sandbox_container_prefix="fpi-desk-sandbox",
        )
    )

    cmd = manager.build_docker_run_command(
        container_name="fpi-desk-sandbox-abc123",
        port=28080,
        mount_root=tmp_path,
    )

    assert cmd == [
        "docker",
        "run",
        "--security-opt",
        "seccomp=unconfined",
        "--rm",
        "-d",
        "-p",
        "127.0.0.1:28080:8080",
        "--name",
        "fpi-desk-sandbox-abc123",
        "--mount",
        f"type=bind,src={tmp_path.resolve()},dst=/workspace",
        "ghcr.io/agent-infra/sandbox:latest",
    ]


def test_local_is_default_sandbox_provider() -> None:
    assert Settings().sandbox_provider == "local"


def test_macos_local_shell_uses_seatbelt_profile(tmp_path: Path, monkeypatch) -> None:
    calls: list[dict] = []

    def fake_which(name: str) -> str | None:
        return {
            "sandbox-exec": "/usr/bin/sandbox-exec",
            "bash": "/bin/bash",
        }.get(name)

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        return subprocess.CompletedProcess(cmd, 0, stdout="local ok\n", stderr="")

    monkeypatch.setattr(sandbox_module.sys, "platform", "darwin")
    monkeypatch.setattr(sandbox_module.shutil, "which", fake_which)
    monkeypatch.setattr(sandbox_module.subprocess, "run", fake_run)

    manager = SandboxManager(settings=Settings(sandbox_mode="required", sandbox_provider="local"))
    result = manager._run_local_shell_sync(  # noqa: SLF001 - verify provider command construction
        session_id="session-1",
        command="pwd",
        cwd=str(tmp_path),
        workspace=str(tmp_path),
        timeout=10,
    )

    assert result.output == "local ok\n"
    assert result.exit_code == 0
    assert result.metadata["provider"] == "local"
    assert result.metadata["platform"] == "macos-seatbelt"

    cmd = calls[0]["cmd"]
    assert cmd[:2] == ["/usr/bin/sandbox-exec", "-p"]
    profile = cmd[2]
    assert '(deny file-write* (subpath "/"))' in profile
    assert f'(allow file-write* (subpath "{tmp_path.resolve()}"))' in profile
    assert cmd[-3:] == ["/bin/bash", "-lc", "pwd"]
    assert calls[0]["kwargs"]["cwd"] == str(tmp_path)


def test_linux_local_shell_requires_bubblewrap(monkeypatch) -> None:
    monkeypatch.setattr(sandbox_module.sys, "platform", "linux")
    monkeypatch.setattr(sandbox_module.shutil, "which", lambda name: None)

    manager = SandboxManager(settings=Settings(sandbox_mode="required", sandbox_provider="local"))

    try:
        manager._run_local_shell_sync(  # noqa: SLF001 - target provider guard directly
            session_id="session-1",
            command="pwd",
            cwd=None,
            workspace=None,
            timeout=10,
        )
    except SandboxUnavailable as exc:
        assert "bubblewrap" in str(exc)
    else:
        raise AssertionError("Linux local sandbox should require bubblewrap")


def test_tencent_provider_requires_e2b_api_key() -> None:
    manager = SandboxManager(
        settings=Settings(
            sandbox_mode="required",
            sandbox_provider="tencent",
            tencent_sandbox_api_key="",
        )
    )

    try:
        manager._run_tencent_python_sync(  # noqa: SLF001 - target the provider guard directly
            session_id="session-1",
            code="print('hello')",
            cwd=None,
            workspace=None,
            timeout=30,
        )
    except SandboxUnavailable as exc:
        assert "Tencent AGS/E2B API key" in str(exc)
    else:
        raise AssertionError("Tencent sandbox should require an AGS/E2B API key")


def test_tencent_import_error_reports_missing_dependency(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "e2b_code_interpreter":
            raise ImportError("No module named 'missing_e2b_dep'", name="missing_e2b_dep")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    manager = SandboxManager(
        settings=Settings(
            sandbox_mode="required",
            sandbox_provider="tencent",
            tencent_sandbox_api_key="test-e2b-key",
        )
    )

    try:
        manager._create_tencent_sandbox()  # noqa: SLF001 - target import guard directly
    except SandboxUnavailable as exc:
        message = str(exc)
        assert "e2b-code-interpreter" in message
        assert "missing_e2b_dep" in message
    else:
        raise AssertionError("Tencent sandbox should report E2B import failure")


def test_tencent_python_uses_configured_domain_template_and_kills() -> None:
    class FakeExecution:
        text = None
        error = None

        class Logs:
            stdout = ["hello from tencent\n"]
            stderr = []

        logs = Logs()

    class FakeSandbox:
        create_calls: list[dict] = []
        killed = False

        @classmethod
        def create(cls, **kwargs):
            cls.create_calls.append(kwargs)
            return cls()

        def run_code(self, code, **kwargs):
            assert code == "print('hello from tencent')"
            assert kwargs["language"] == "python"
            assert kwargs["timeout"] == 30
            return FakeExecution()

        def kill(self):
            type(self).killed = True

    manager = SandboxManager(
        settings=Settings(
            sandbox_mode="required",
            sandbox_provider="tencent",
            tencent_sandbox_domain="ap-guangzhou.tencentags.com",
            tencent_sandbox_template="code-2qj6gcgh6oa",
            tencent_sandbox_api_key="test-e2b-key",
            tencent_sandbox_validate_api_key=False,
            tencent_sandbox_lifetime=3600,
        ),
        tencent_sandbox_cls=FakeSandbox,
    )

    result = manager._run_tencent_python_sync(  # noqa: SLF001 - use sync path for deterministic unit test
        session_id="session-1",
        code="print('hello from tencent')",
        cwd=None,
        workspace=None,
        timeout=30,
    )

    assert result.output == "hello from tencent\n"
    assert result.exit_code == 0
    assert result.metadata["provider"] == "tencent"
    assert result.metadata["domain"] == "ap-guangzhou.tencentags.com"
    assert result.metadata["template"] == "code-2qj6gcgh6oa"
    assert FakeSandbox.create_calls == [
        {
            "template": "code-2qj6gcgh6oa",
            "timeout": 3600,
            "api_key": "test-e2b-key",
            "domain": "ap-guangzhou.tencentags.com",
            "validate_api_key": False,
        }
    ]
    assert FakeSandbox.killed is True


def test_tencent_shell_limits_local_concurrent_sandboxes() -> None:
    first_command_started = threading.Event()
    release_command = threading.Event()
    state_lock = threading.Lock()

    class FakeResult:
        stdout = "ok\n"
        stderr = ""
        exit_code = 0

    class FakeCommands:
        def run(self, *args, **kwargs):
            first_command_started.set()
            if not release_command.wait(timeout=2):
                raise RuntimeError("test command was not released")
            return FakeResult()

    class FakeSandbox:
        active = 0
        max_active = 0

        def __init__(self) -> None:
            self.commands = FakeCommands()

        @classmethod
        def create(cls, **kwargs):
            with state_lock:
                cls.active += 1
                cls.max_active = max(cls.max_active, cls.active)
            return cls()

        def kill(self):
            with state_lock:
                type(self).active -= 1

    manager = SandboxManager(
        settings=Settings(
            sandbox_mode="required",
            sandbox_provider="tencent",
            tencent_sandbox_api_key="test-e2b-key",
            tencent_sandbox_max_concurrent=1,
            tencent_sandbox_acquire_timeout=2,
        ),
        tencent_sandbox_cls=FakeSandbox,
    )

    def run_command() -> int:
        result = manager._run_tencent_shell_sync(  # noqa: SLF001 - exercise provider concurrency directly
            session_id="session-1",
            command="pwd",
            cwd=None,
            workspace=None,
            timeout=30,
        )
        return result.exit_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run_command)
        assert first_command_started.wait(timeout=2)
        second = pool.submit(run_command)
        time.sleep(0.25)
        release_command.set()
        assert first.result(timeout=2) == 0
        assert second.result(timeout=2) == 0

    assert FakeSandbox.max_active == 1


def test_tencent_sandbox_create_retries_transient_failure() -> None:
    class FakeResult:
        stdout = "ok\n"
        stderr = ""
        exit_code = 0

    class FakeCommands:
        def run(self, *args, **kwargs):
            return FakeResult()

    class FlakySandbox:
        create_calls = 0
        killed = False

        def __init__(self) -> None:
            self.commands = FakeCommands()

        @classmethod
        def create(cls, **kwargs):
            cls.create_calls += 1
            if cls.create_calls == 1:
                raise RuntimeError("temporary quota error")
            return cls()

        def kill(self):
            type(self).killed = True

    manager = SandboxManager(
        settings=Settings(
            sandbox_mode="required",
            sandbox_provider="tencent",
            tencent_sandbox_api_key="test-e2b-key",
            tencent_sandbox_create_retries=2,
            tencent_sandbox_retry_backoff=0,
        ),
        tencent_sandbox_cls=FlakySandbox,
    )

    result = manager._run_tencent_shell_sync(  # noqa: SLF001 - exercise create retry directly
        session_id="session-1",
        command="pwd",
        cwd=None,
        workspace=None,
        timeout=30,
    )

    assert result.exit_code == 0
    assert FlakySandbox.create_calls == 2
    assert FlakySandbox.killed is True


def test_tencent_api_key_can_be_created_from_secret_and_cached(tmp_path: Path) -> None:
    cache_path = tmp_path / "tencent_sandbox_api_key"
    calls: list[tuple[str, str, str]] = []

    class FakeResponse:
        APIKey = "created-e2b-api-key"

    class FakeClient:
        def CreateAPIKey(self, request):
            assert request.Name == "openyak-test"
            return FakeResponse()

    def fake_client_factory(secret_id: str, secret_key: str, region: str):
        calls.append((secret_id, secret_key, region))
        return FakeClient()

    manager = SandboxManager(
        settings=Settings(
            sandbox_provider="tencent",
            tencent_sandbox_api_key="",
            tencent_sandbox_auto_create_api_key=True,
            tencent_sandbox_api_key_cache_path=str(cache_path),
            tencent_sandbox_key_name="openyak-test",
            tencent_sandbox_region="ap-beijing",
            tencent_secret_id="sid",
            tencent_secret_key="skey",
        ),
        tencent_client_factory=fake_client_factory,
    )

    assert manager._tencent_api_key() == "created-e2b-api-key"  # noqa: SLF001
    assert cache_path.read_text(encoding="utf-8") == "created-e2b-api-key"
    assert calls == [("sid", "skey", "ap-beijing")]


def test_tencent_api_key_can_read_bundled_resource_cache(tmp_path: Path, monkeypatch) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    resource_key = tmp_path / "resources" / "backend" / "_internal" / "tencent_sandbox_api_key"
    resource_key.parent.mkdir(parents=True)
    resource_key.write_text("bundled-e2b-api-key", encoding="utf-8")
    monkeypatch.chdir(runtime_dir)
    monkeypatch.setenv("OPENYAK_RESOURCE_DIR", str(tmp_path / "resources"))

    manager = SandboxManager(
        settings=Settings(
            sandbox_provider="tencent",
            tencent_sandbox_api_key="",
            tencent_sandbox_auto_create_api_key=False,
        )
    )

    assert manager._tencent_api_key() == "bundled-e2b-api-key"  # noqa: SLF001
