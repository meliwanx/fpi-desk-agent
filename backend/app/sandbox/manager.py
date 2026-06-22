"""Sandbox execution manager.

The default provider is local and follows Codex's public sandbox direction:
macOS uses Seatbelt via ``sandbox-exec`` and Linux/WSL2 uses bubblewrap.
Docker and Tencent AGS remain as explicit non-default providers for legacy or
special-purpose isolated execution.
"""

from __future__ import annotations

import asyncio
import base64
from contextlib import suppress
import hashlib
import logging
import os
import posixpath
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

CONTAINER_WORKSPACE = "/workspace"
CONTAINER_PORT = 8080
TENCENT_WORKSPACE = "/home/user"
_EXIT_MARKER_PREFIX = "__OPENYAK_EXIT_CODE_"


class SandboxUnavailable(RuntimeError):
    """Raised when sandbox execution was requested but cannot run."""


@dataclass(frozen=True)
class SandboxCommandResult:
    output: str
    exit_code: int
    metadata: dict[str, Any]


@dataclass
class _SandboxInstance:
    key: str
    container_name: str
    sandbox_url: str
    mount_root: Path
    client: Any
    last_used: float


class SandboxManager:
    """Run shell and Python code through the configured sandbox provider."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        tencent_sandbox_cls: Any | None = None,
        tencent_client_factory: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._tencent_sandbox_cls = tencent_sandbox_cls
        self._tencent_client_factory = tencent_client_factory
        self._lock = threading.RLock()
        self._instances: dict[str, _SandboxInstance] = {}
        self._tencent_max_concurrent = max(
            int(getattr(self._settings, "tencent_sandbox_max_concurrent", 2) or 1),
            1,
        )
        self._tencent_slots = threading.BoundedSemaphore(self._tencent_max_concurrent)

    def is_enabled(self) -> bool:
        return self._mode() != "off"

    def is_required(self) -> bool:
        return self._mode() == "required"

    def _mode(self) -> str:
        mode = (self._settings.sandbox_mode or "auto").strip().lower()
        return mode if mode in {"auto", "required", "off"} else "auto"

    def _provider(self) -> str:
        provider = (self._settings.sandbox_provider or "local").strip().lower()
        return provider if provider in {"local", "tencent", "docker"} else "local"

    def _acquire_tencent_slot(self, *, session_id: str, operation: str) -> float:
        timeout = max(float(self._settings.tencent_sandbox_acquire_timeout or 0), 0.0)
        started = time.monotonic()
        logger.info(
            "Waiting for Tencent sandbox slot operation=%s session_id=%s max_concurrent=%s timeout=%.1fs",
            operation,
            session_id,
            self._tencent_max_concurrent,
            timeout,
        )
        acquired = self._tencent_slots.acquire(timeout=timeout)
        waited = time.monotonic() - started
        if not acquired:
            raise SandboxUnavailable(
                "Timed out waiting for Tencent sandbox slot after "
                f"{timeout:.1f}s; local max concurrent is {self._tencent_max_concurrent}"
            )
        logger.info(
            "Acquired Tencent sandbox slot operation=%s session_id=%s waited=%.3fs",
            operation,
            session_id,
            waited,
        )
        return waited

    def _release_tencent_slot(self, *, session_id: str, operation: str, duration: float) -> None:
        self._tencent_slots.release()
        logger.info(
            "Released Tencent sandbox slot operation=%s session_id=%s duration=%.3fs",
            operation,
            session_id,
            duration,
        )

    def build_docker_run_command(
        self,
        *,
        container_name: str,
        port: int,
        mount_root: Path,
    ) -> list[str]:
        """Build the DeerFlow-style local AIO sandbox container command."""
        return [
            "docker",
            "run",
            "--security-opt",
            "seccomp=unconfined",
            "--rm",
            "-d",
            "-p",
            f"127.0.0.1:{port}:{CONTAINER_PORT}",
            "--name",
            container_name,
            "--mount",
            f"type=bind,src={mount_root.resolve()},dst={CONTAINER_WORKSPACE}",
            self._settings.sandbox_image,
        ]

    async def run_shell(
        self,
        *,
        session_id: str,
        command: str,
        cwd: str | None,
        workspace: str | None,
        timeout: int,
    ) -> SandboxCommandResult:
        return await asyncio.to_thread(
            self._run_shell_sync,
            session_id=session_id,
            command=command,
            cwd=cwd,
            workspace=workspace,
            timeout=timeout,
        )

    async def run_python(
        self,
        *,
        session_id: str,
        code: str,
        cwd: str | None,
        workspace: str | None,
        timeout: int,
    ) -> SandboxCommandResult:
        if self._provider() == "tencent":
            return await asyncio.to_thread(
                self._run_tencent_python_sync,
                session_id=session_id,
                code=code,
                cwd=cwd,
                workspace=workspace,
                timeout=timeout,
            )

        encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
        runner = (
            "python3 - <<'PY'\n"
            "import base64\n"
            f"code = base64.b64decode({encoded!r}).decode('utf-8')\n"
            "namespace = {'__builtins__': __builtins__}\n"
            "exec(compile(code, '<code_execute>', 'exec'), namespace)\n"
            "PY"
        )
        return await self.run_shell(
            session_id=session_id,
            command=runner,
            cwd=cwd,
            workspace=workspace,
            timeout=timeout,
        )

    def _run_shell_sync(
        self,
        *,
        session_id: str,
        command: str,
        cwd: str | None,
        workspace: str | None,
        timeout: int,
    ) -> SandboxCommandResult:
        if self._provider() == "local":
            return self._run_local_shell_sync(
                session_id=session_id,
                command=command,
                cwd=cwd,
                workspace=workspace,
                timeout=timeout,
            )
        if self._provider() == "tencent":
            return self._run_tencent_shell_sync(
                session_id=session_id,
                command=command,
                cwd=cwd,
                workspace=workspace,
                timeout=timeout,
            )
        return self._run_docker_shell_sync(
            session_id=session_id,
            command=command,
            cwd=cwd,
            workspace=workspace,
            timeout=timeout,
        )

    def _run_local_shell_sync(
        self,
        *,
        session_id: str,
        command: str,
        cwd: str | None,
        workspace: str | None,
        timeout: int,
    ) -> SandboxCommandResult:
        if not self.is_enabled():
            raise SandboxUnavailable("Sandbox mode is off")

        if sys.platform == "darwin":
            return self._run_macos_seatbelt_shell_sync(
                command=command,
                cwd=cwd,
                workspace=workspace,
                timeout=timeout,
            )
        if sys.platform.startswith("linux"):
            return self._run_linux_bubblewrap_shell_sync(
                command=command,
                cwd=cwd,
                workspace=workspace,
                timeout=timeout,
            )
        if sys.platform == "win32":
            raise SandboxUnavailable(
                "Local Windows sandbox execution is not available in this build; "
                "use WSL2 for Linux sandboxing or set sandbox_mode=auto/off to run on the host."
            )
        raise SandboxUnavailable(f"Local sandbox is not supported on platform: {sys.platform}")

    def _run_macos_seatbelt_shell_sync(
        self,
        *,
        command: str,
        cwd: str | None,
        workspace: str | None,
        timeout: int,
    ) -> SandboxCommandResult:
        sandbox_exec = shutil.which("sandbox-exec")
        if not sandbox_exec:
            raise SandboxUnavailable("macOS Seatbelt sandbox is unavailable: sandbox-exec not found")

        shell = shutil.which("bash") or "/bin/bash"
        run_cwd = str(Path(cwd or workspace or os.getcwd()).expanduser().resolve())
        writable_roots = self._local_writable_roots(cwd=cwd, workspace=workspace)
        profile = self._macos_seatbelt_profile(writable_roots)
        cmd = [sandbox_exec, "-p", profile, shell, "-lc", command]
        return self._run_local_subprocess(
            cmd,
            cwd=run_cwd,
            timeout=timeout,
            metadata={
                "provider": "local",
                "platform": "macos-seatbelt",
                "cwd": run_cwd,
                "writable_roots": [str(p) for p in writable_roots],
            },
        )

    def _run_linux_bubblewrap_shell_sync(
        self,
        *,
        command: str,
        cwd: str | None,
        workspace: str | None,
        timeout: int,
    ) -> SandboxCommandResult:
        bwrap = shutil.which("bwrap") or shutil.which("bubblewrap")
        if not bwrap:
            raise SandboxUnavailable("Linux local sandbox is unavailable: bubblewrap is not installed")

        shell = shutil.which("bash") or "/bin/bash"
        run_cwd = str(Path(cwd or workspace or os.getcwd()).expanduser().resolve())
        writable_roots = self._local_writable_roots(cwd=cwd, workspace=workspace)
        cmd = [
            bwrap,
            "--die-with-parent",
            "--ro-bind",
            "/",
            "/",
            "--dev-bind",
            "/dev",
            "/dev",
            "--proc",
            "/proc",
        ]
        for root in self._linux_tmp_roots():
            cmd.extend(["--bind", str(root), str(root)])
        for root in writable_roots:
            cmd.extend(["--bind", str(root), str(root)])
        cmd.extend([
            "--chdir",
            run_cwd,
            "--setenv",
            "HOME",
            os.environ.get("HOME", str(Path.home())),
            "--setenv",
            "PATH",
            os.environ.get("PATH", ""),
            shell,
            "-lc",
            command,
        ])
        return self._run_local_subprocess(
            cmd,
            cwd=run_cwd,
            timeout=timeout,
            metadata={
                "provider": "local",
                "platform": "linux-bubblewrap",
                "cwd": run_cwd,
                "writable_roots": [str(p) for p in writable_roots],
            },
        )

    @staticmethod
    def _run_local_subprocess(
        cmd: list[str],
        *,
        cwd: str,
        timeout: int,
        metadata: dict[str, Any],
    ) -> SandboxCommandResult:
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                timeout=timeout,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired as exc:
            raise SandboxUnavailable(f"Local sandbox command timed out after {timeout}s") from exc
        except OSError as exc:
            raise SandboxUnavailable(f"Local sandbox command failed: {exc}") from exc

        output = SandboxManager._format_command_output(
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            exit_code=int(result.returncode),
        )
        return SandboxCommandResult(
            output=output,
            exit_code=int(result.returncode),
            metadata=metadata,
        )

    @staticmethod
    def _local_writable_roots(*, cwd: str | None, workspace: str | None) -> list[Path]:
        roots: list[Path] = []
        for raw in (workspace, cwd):
            if not raw:
                continue
            try:
                root = Path(raw).expanduser().resolve()
            except OSError:
                continue
            if root not in roots:
                roots.append(root)
        if not roots:
            roots.append(Path(os.getcwd()).resolve())
        return roots

    @staticmethod
    def _macos_seatbelt_profile(writable_roots: list[Path]) -> str:
        lines = [
            "(version 1)",
            "(allow default)",
            '(deny file-write* (subpath "/"))',
            '(allow file-write* (literal "/dev/null"))',
            '(allow file-write* (subpath "/dev/fd"))',
        ]
        for root in SandboxManager._common_temp_roots():
            lines.append(f'(allow file-write* (subpath "{SandboxManager._seatbelt_escape(str(root))}"))')
        for root in writable_roots:
            lines.append(f'(allow file-write* (subpath "{SandboxManager._seatbelt_escape(str(root))}"))')
        return "\n".join(lines)

    @staticmethod
    def _seatbelt_escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _common_temp_roots() -> list[Path]:
        roots: list[Path] = []
        for raw in (os.environ.get("TMPDIR"), "/tmp", "/private/tmp", "/var/tmp", "/var/folders"):
            if not raw:
                continue
            try:
                root = Path(raw).expanduser().resolve()
            except OSError:
                continue
            if root not in roots:
                roots.append(root)
        return roots

    @staticmethod
    def _linux_tmp_roots() -> list[Path]:
        return [root for root in SandboxManager._common_temp_roots() if root.exists()]

    def _run_docker_shell_sync(
        self,
        *,
        session_id: str,
        command: str,
        cwd: str | None,
        workspace: str | None,
        timeout: int,
    ) -> SandboxCommandResult:
        if not self.is_enabled():
            raise SandboxUnavailable("Sandbox mode is off")

        instance = self._ensure_sandbox(session_id=session_id, cwd=cwd, workspace=workspace)
        container_cwd = self._container_cwd(instance.mount_root, cwd)
        marker_id = uuid.uuid4().hex
        marker = f"{_EXIT_MARKER_PREFIX}{marker_id}__"
        wrapper = self._wrap_shell_command(command, container_cwd=container_cwd, marker=marker)

        try:
            result = instance.client.shell.exec_command(
                command=wrapper,
                strict=False,
                timeout=float(timeout + 10),
                hard_timeout=float(timeout + 10),
                no_change_timeout=max(timeout + 5, 30),
            )
        except Exception as exc:
            raise SandboxUnavailable(f"Sandbox command failed: {exc}") from exc

        data = getattr(result, "data", None)
        output = getattr(data, "output", None) or ""
        exit_code = getattr(data, "exit_code", None)
        parsed_output, parsed_exit = self._parse_exit_marker(output, marker)
        if parsed_exit is not None:
            exit_code = parsed_exit
            output = parsed_output
        if exit_code is None:
            exit_code = 0
        if not output.strip():
            output = "(no output)"
        instance.last_used = time.time()
        return SandboxCommandResult(
            output=output,
            exit_code=int(exit_code),
            metadata={
                "container_name": instance.container_name,
                "sandbox_url": instance.sandbox_url,
                "mount_root": str(instance.mount_root),
                "container_cwd": container_cwd,
            },
        )

    def _run_tencent_shell_sync(
        self,
        *,
        session_id: str,
        command: str,
        cwd: str | None,
        workspace: str | None,
        timeout: int,
    ) -> SandboxCommandResult:
        if not self.is_enabled():
            raise SandboxUnavailable("Sandbox mode is off")

        remote_cwd = self._tencent_cwd(cwd=cwd, workspace=workspace)
        sandbox: Any | None = None
        slot_acquired = False
        started = time.monotonic()
        try:
            self._acquire_tencent_slot(session_id=session_id, operation="shell")
            slot_acquired = True
            sandbox = self._create_tencent_sandbox(operation="shell", session_id=session_id)
            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []
            try:
                result = sandbox.commands.run(
                    command,
                    cwd=remote_cwd,
                    on_stdout=stdout_chunks.append,
                    on_stderr=stderr_chunks.append,
                    timeout=float(timeout),
                    request_timeout=float(timeout + 10),
                )
            except Exception as exc:
                result = self._command_exit_exception_result(exc)
                if result is None:
                    raise

            stdout = "".join(stdout_chunks) or getattr(result, "stdout", "") or ""
            stderr = "".join(stderr_chunks) or getattr(result, "stderr", "") or ""
            exit_code = int(getattr(result, "exit_code", 0) or 0)
            output = self._format_command_output(stdout=stdout, stderr=stderr, exit_code=exit_code)
            return SandboxCommandResult(
                output=output,
                exit_code=exit_code,
                metadata=self._tencent_metadata(remote_cwd=remote_cwd),
            )
        except SandboxUnavailable:
            raise
        except Exception as exc:
            raise SandboxUnavailable(f"Tencent sandbox command failed: {exc}") from exc
        finally:
            if sandbox is not None:
                self._kill_tencent_sandbox(sandbox)
            if slot_acquired:
                self._release_tencent_slot(
                    session_id=session_id,
                    operation="shell",
                    duration=time.monotonic() - started,
                )

    def _run_tencent_python_sync(
        self,
        *,
        session_id: str,
        code: str,
        cwd: str | None,
        workspace: str | None,
        timeout: int,
    ) -> SandboxCommandResult:
        if not self.is_enabled():
            raise SandboxUnavailable("Sandbox mode is off")

        remote_cwd = self._tencent_cwd(cwd=cwd, workspace=workspace)
        sandbox: Any | None = None
        slot_acquired = False
        started = time.monotonic()
        try:
            self._acquire_tencent_slot(session_id=session_id, operation="python")
            slot_acquired = True
            sandbox = self._create_tencent_sandbox(operation="python", session_id=session_id)
            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []
            error_chunks: list[str] = []

            def _append_error(error: Any) -> None:
                traceback = getattr(error, "traceback", None)
                if traceback:
                    error_chunks.append(str(traceback))
                    return
                name = getattr(error, "name", "")
                value = getattr(error, "value", "")
                text = f"{name}: {value}".strip(": ")
                if text:
                    error_chunks.append(text)

            execution = sandbox.run_code(
                code,
                language="python",
                on_stdout=lambda message: stdout_chunks.append(str(message)),
                on_stderr=lambda message: stderr_chunks.append(str(message)),
                on_error=_append_error,
                timeout=float(timeout),
                request_timeout=float(timeout + 10),
            )
            stdout = "".join(stdout_chunks) or "".join(getattr(execution.logs, "stdout", []) or [])
            stderr = "".join(stderr_chunks) or "".join(getattr(execution.logs, "stderr", []) or [])
            if not stdout and getattr(execution, "text", None):
                stdout = str(execution.text)
            execution_error = getattr(execution, "error", None)
            if execution_error and not error_chunks:
                _append_error(execution_error)
            if error_chunks:
                stderr = "\n".join(part for part in [stderr.rstrip("\n"), *error_chunks] if part)
            exit_code = 1 if execution_error or error_chunks else 0
            output = self._format_command_output(stdout=stdout, stderr=stderr, exit_code=exit_code)
            return SandboxCommandResult(
                output=output,
                exit_code=exit_code,
                metadata=self._tencent_metadata(remote_cwd=remote_cwd),
            )
        except SandboxUnavailable:
            raise
        except Exception as exc:
            raise SandboxUnavailable(f"Tencent sandbox Python execution failed: {exc}") from exc
        finally:
            if sandbox is not None:
                self._kill_tencent_sandbox(sandbox)
            if slot_acquired:
                self._release_tencent_slot(
                    session_id=session_id,
                    operation="python",
                    duration=time.monotonic() - started,
                )

    def _create_tencent_sandbox(self, *, operation: str = "unknown", session_id: str = "") -> Any:
        api_key = self._tencent_api_key()
        if not api_key:
            raise SandboxUnavailable(
                "Tencent AGS/E2B API key is not configured; set OPENYAK_TENCENT_SANDBOX_API_KEY"
            )

        sandbox_cls = self._tencent_sandbox_cls
        if sandbox_cls is None:
            try:
                from e2b_code_interpreter import Sandbox as sandbox_cls
            except ImportError as exc:
                logger.exception("Failed to import e2b-code-interpreter for Tencent sandbox")
                detail = str(exc) or repr(exc)
                missing = getattr(exc, "name", "")
                if missing and missing not in detail:
                    detail = f"{detail} (missing module: {missing})"
                raise SandboxUnavailable(
                    "Python package e2b-code-interpreter or one of its dependencies "
                    f"could not be imported: {detail}"
                ) from exc

        domain = self._tencent_domain()
        template = (self._settings.tencent_sandbox_template or "code-interpreter-v1").strip()
        lifetime = max(int(self._settings.tencent_sandbox_lifetime or 3600), 60)
        attempts = max(int(self._settings.tencent_sandbox_create_retries or 1), 1)
        backoff = max(float(self._settings.tencent_sandbox_retry_backoff or 0), 0.0)
        for attempt in range(1, attempts + 1):
            try:
                logger.info(
                    "Creating Tencent AGS sandbox operation=%s session_id=%s attempt=%s/%s template=%s domain=%s",
                    operation,
                    session_id,
                    attempt,
                    attempts,
                    template,
                    domain,
                )
                sandbox = sandbox_cls.create(
                    template=template,
                    timeout=lifetime,
                    api_key=api_key,
                    domain=domain,
                    validate_api_key=bool(self._settings.tencent_sandbox_validate_api_key),
                )
                logger.info(
                    "Created Tencent AGS sandbox operation=%s session_id=%s sandbox_id=%s",
                    operation,
                    session_id,
                    self._tencent_sandbox_identifier(sandbox),
                )
                return sandbox
            except Exception as exc:
                if attempt >= attempts:
                    logger.warning(
                        "Failed to create Tencent AGS sandbox operation=%s session_id=%s attempts=%s",
                        operation,
                        session_id,
                        attempts,
                        exc_info=True,
                    )
                    raise SandboxUnavailable(
                        f"Failed to create Tencent AGS sandbox after {attempts} attempt(s): {exc}"
                    ) from exc
                logger.warning(
                    "Retrying Tencent AGS sandbox create operation=%s session_id=%s attempt=%s/%s",
                    operation,
                    session_id,
                    attempt,
                    attempts,
                    exc_info=True,
                )
                if backoff:
                    time.sleep(backoff * attempt)
        raise SandboxUnavailable("Failed to create Tencent AGS sandbox")

    def _tencent_api_key(self) -> str:
        configured = (self._settings.tencent_sandbox_api_key or os.environ.get("E2B_API_KEY") or "").strip()
        if configured:
            return configured

        cached = self._read_cached_tencent_api_key()
        if cached:
            return cached

        if not self._settings.tencent_sandbox_auto_create_api_key:
            return ""

        secret_id = (self._settings.tencent_secret_id or os.environ.get("TENCENTCLOUD_SECRET_ID") or "").strip()
        secret_key = (self._settings.tencent_secret_key or os.environ.get("TENCENTCLOUD_SECRET_KEY") or "").strip()
        if not secret_id or not secret_key:
            return ""

        created = self._create_tencent_api_key(secret_id=secret_id, secret_key=secret_key)
        self._write_cached_tencent_api_key(created)
        return created

    def _read_cached_tencent_api_key(self) -> str:
        for path in self._tencent_api_key_candidate_paths():
            try:
                cached = path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if cached:
                return cached
        return ""

    def _write_cached_tencent_api_key(self, api_key: str) -> None:
        path = self._tencent_api_key_cache_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(api_key, encoding="utf-8")
            with suppress(OSError):
                path.chmod(0o600)
        except OSError as exc:
            raise SandboxUnavailable(f"Failed to cache Tencent AGS/E2B API key: {exc}") from exc

    def _tencent_api_key_cache_path(self) -> Path:
        raw = (self._settings.tencent_sandbox_api_key_cache_path or "tencent_sandbox_api_key").strip()
        path = Path(raw).expanduser()
        return path if path.is_absolute() else (Path.cwd() / path).resolve()

    def _tencent_api_key_candidate_paths(self) -> list[Path]:
        paths = [self._tencent_api_key_cache_path()]
        resource_dir = os.environ.get("OPENYAK_RESOURCE_DIR")
        if resource_dir:
            resource_root = Path(resource_dir).expanduser()
            cache_name = Path(self._settings.tencent_sandbox_api_key_cache_path or "tencent_sandbox_api_key").name
            paths.extend(
                [
                    resource_root / "backend" / cache_name,
                    resource_root / "backend" / "_internal" / cache_name,
                ]
            )
        return paths

    def _create_tencent_api_key(self, *, secret_id: str, secret_key: str) -> str:
        try:
            client = self._create_tencent_client(secret_id=secret_id, secret_key=secret_key)
            from tencentcloud.ags.v20250920 import models

            request = models.CreateAPIKeyRequest()
            request.Name = (self._settings.tencent_sandbox_key_name or "fpi-desk-agent").strip()
            response = client.CreateAPIKey(request)
            api_key = (getattr(response, "APIKey", "") or "").strip()
        except ImportError as exc:
            raise SandboxUnavailable("Python package tencentcloud-sdk-python is not installed") from exc
        except Exception as exc:
            raise SandboxUnavailable(f"Failed to create Tencent AGS/E2B API key: {exc}") from exc

        if not api_key:
            raise SandboxUnavailable("Tencent AGS CreateAPIKey returned an empty API key")
        return api_key

    def _create_tencent_client(self, *, secret_id: str, secret_key: str) -> Any:
        if self._tencent_client_factory is not None:
            return self._tencent_client_factory(secret_id, secret_key, self._settings.tencent_sandbox_region)

        from tencentcloud.ags.v20250920 import ags_client
        from tencentcloud.common import credential

        cred = credential.Credential(secret_id, secret_key)
        return ags_client.AgsClient(cred, self._settings.tencent_sandbox_region)

    def _tencent_domain(self) -> str:
        return (
            self._settings.tencent_sandbox_domain
            or os.environ.get("E2B_DOMAIN")
            or "ap-guangzhou.tencentags.com"
        ).strip()

    def _tencent_metadata(self, *, remote_cwd: str) -> dict[str, Any]:
        return {
            "provider": "tencent",
            "domain": self._tencent_domain(),
            "template": (self._settings.tencent_sandbox_template or "code-interpreter-v1").strip(),
            "remote_cwd": remote_cwd,
        }

    @staticmethod
    def _tencent_cwd(*, cwd: str | None, workspace: str | None) -> str:
        return TENCENT_WORKSPACE

    @staticmethod
    def _tencent_sandbox_identifier(sandbox: Any) -> str:
        for attr in ("sandbox_id", "sandboxId", "id"):
            value = getattr(sandbox, attr, None)
            if value:
                return str(value)
        return "unknown"

    @staticmethod
    def _kill_tencent_sandbox(sandbox: Any) -> None:
        sandbox_id = SandboxManager._tencent_sandbox_identifier(sandbox)
        try:
            logger.info("Killing Tencent AGS sandbox sandbox_id=%s", sandbox_id)
            sandbox.kill()
            logger.info("Killed Tencent AGS sandbox sandbox_id=%s", sandbox_id)
        except Exception:
            logger.warning("Failed to kill Tencent AGS sandbox sandbox_id=%s", sandbox_id, exc_info=True)

    @staticmethod
    def _command_exit_exception_result(exc: Exception) -> Any | None:
        if all(hasattr(exc, attr) for attr in ("stdout", "stderr", "exit_code")):
            return exc
        return None

    @staticmethod
    def _format_command_output(*, stdout: str, stderr: str, exit_code: int) -> str:
        output_parts = []
        if stdout:
            output_parts.append(stdout)
        if stderr:
            output_parts.append(f"STDERR:\n{stderr}")
        return "\n".join(output_parts) if output_parts else "(no output)"

    @staticmethod
    def _wrap_shell_command(command: str, *, container_cwd: str, marker: str) -> str:
        script = (
            "set +e\n"
            f"mkdir -p {shlex.quote(container_cwd)}\n"
            f"cd {shlex.quote(container_cwd)}\n"
            f"{command}\n"
            "status=$?\n"
            f"printf '\\n{marker}:%s\\n' \"$status\"\n"
            "exit \"$status\"\n"
        )
        return f"bash -lc {shlex.quote(script)}"

    @staticmethod
    def _parse_exit_marker(output: str, marker: str) -> tuple[str, int | None]:
        match = re.search(rf"\n?{re.escape(marker)}:(\d+)\s*$", output)
        if not match:
            return output, None
        cleaned = output[: match.start()].rstrip("\n")
        return cleaned, int(match.group(1))

    def _ensure_sandbox(self, *, session_id: str, cwd: str | None, workspace: str | None) -> _SandboxInstance:
        self._ensure_prerequisites()
        mount_root = self._mount_root(session_id=session_id, cwd=cwd, workspace=workspace)
        key = self._instance_key(session_id, mount_root)

        with self._lock:
            cached = self._instances.get(key)
            if cached and self._is_container_running(cached.container_name):
                cached.last_used = time.time()
                return cached
            if cached:
                self._instances.pop(key, None)

            sandbox_id = self._sandbox_id(session_id, mount_root)
            container_name = f"{self._settings.sandbox_container_prefix}-{sandbox_id}"
            discovered = self._discover(container_name)
            if discovered is not None:
                sandbox_url = discovered
            else:
                sandbox_url = self._start_container(container_name=container_name, mount_root=mount_root)
            client = self._create_client(sandbox_url)
            instance = _SandboxInstance(
                key=key,
                container_name=container_name,
                sandbox_url=sandbox_url,
                mount_root=mount_root,
                client=client,
                last_used=time.time(),
            )
            self._instances[key] = instance
            return instance

    def _ensure_prerequisites(self) -> None:
        if shutil.which("docker") is None:
            raise SandboxUnavailable("Docker is not installed or not on PATH")
        try:
            import agent_sandbox  # noqa: F401
        except ImportError as exc:
            raise SandboxUnavailable("Python package agent-sandbox is not installed") from exc

    def _mount_root(self, *, session_id: str, cwd: str | None, workspace: str | None) -> Path:
        if workspace:
            root = Path(workspace).expanduser().resolve()
        elif cwd:
            root = Path(cwd).expanduser().resolve()
        else:
            base = Path(self._settings.sandbox_data_dir).expanduser()
            if not base.is_absolute():
                base = Path.cwd() / base
            root = (base / self._safe_segment(session_id)).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _container_cwd(mount_root: Path, cwd: str | None) -> str:
        if not cwd:
            return CONTAINER_WORKSPACE
        try:
            relative = Path(cwd).expanduser().resolve().relative_to(mount_root)
        except ValueError:
            return CONTAINER_WORKSPACE
        rel = relative.as_posix()
        if rel in {"", "."}:
            return CONTAINER_WORKSPACE
        return posixpath.join(CONTAINER_WORKSPACE, rel)

    @staticmethod
    def _safe_segment(value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
        return digest

    @staticmethod
    def _instance_key(session_id: str, mount_root: Path) -> str:
        raw = f"{session_id}:{mount_root.resolve()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _sandbox_id(session_id: str, mount_root: Path) -> str:
        raw = f"{session_id}:{mount_root.resolve()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _start_container(self, *, container_name: str, mount_root: Path) -> str:
        port = self._find_free_port()
        cmd = self.build_docker_run_command(
            container_name=container_name,
            port=port,
            mount_root=mount_root,
        )
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise SandboxUnavailable(f"Failed to start sandbox container: {stderr}") from exc
        except subprocess.TimeoutExpired as exc:
            raise SandboxUnavailable("Timed out starting sandbox container") from exc

        sandbox_url = f"http://127.0.0.1:{port}"
        if not self._wait_ready(sandbox_url):
            self._stop_container(container_name)
            raise SandboxUnavailable("Sandbox container started but did not become ready")
        return sandbox_url

    def _discover(self, container_name: str) -> str | None:
        if not self._is_container_running(container_name):
            return None
        port = self._get_container_port(container_name)
        if port is None:
            return None
        sandbox_url = f"http://127.0.0.1:{port}"
        return sandbox_url if self._wait_ready(sandbox_url, timeout=5) else None

    def _find_free_port(self) -> int:
        start = max(1, int(self._settings.sandbox_port_start))
        for port in range(start, start + 200):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        raise SandboxUnavailable("No free localhost port available for sandbox")

    @staticmethod
    def _is_container_running(container_name: str) -> bool:
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False
        return result.returncode == 0 and result.stdout.strip().lower() == "true"

    @staticmethod
    def _get_container_port(container_name: str) -> int | None:
        try:
            result = subprocess.run(
                ["docker", "port", container_name, str(CONTAINER_PORT)],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None
        if result.returncode != 0:
            return None
        text = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        if not text:
            return None
        try:
            return int(text.rsplit(":", 1)[-1])
        except ValueError:
            return None

    @staticmethod
    def _wait_ready(sandbox_url: str, timeout: int = 30) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                response = httpx.get(f"{sandbox_url}/v1/sandbox", timeout=5)
                if response.status_code == 200:
                    return True
            except httpx.HTTPError:
                pass
            time.sleep(1)
        return False

    def _create_client(self, sandbox_url: str):
        from agent_sandbox import Sandbox

        return Sandbox(base_url=sandbox_url, timeout=float(self._settings.sandbox_client_timeout))

    @staticmethod
    def _stop_container(container_name: str) -> None:
        try:
            subprocess.run(
                ["docker", "stop", container_name],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return

    def shutdown(self) -> None:
        with self._lock:
            instances = list(self._instances.values())
            self._instances.clear()
        for instance in instances:
            self._stop_container(instance.container_name)


_manager: SandboxManager | None = None
_manager_lock = threading.Lock()


def get_sandbox_manager() -> SandboxManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = SandboxManager()
        return _manager


def reset_sandbox_manager() -> None:
    global _manager
    with _manager_lock:
        manager = _manager
        _manager = None
    if manager is not None:
        manager.shutdown()
