"""Code execution tool — run Python code in-process.

Executes Python code in a background thread using the backend's own
interpreter. All packages bundled with the backend (pandas, numpy,
matplotlib, etc.) are available without requiring a separate Python
installation.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any

from app.sandbox.manager import SandboxUnavailable, get_sandbox_manager
from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30  # seconds
MAX_TIMEOUT = 120
MAX_OUTPUT = 51200  # 50 KB


def _snapshot_workspace(workspace: str | None) -> dict[str, tuple[int, int]]:
    """Return a cheap file snapshot for detecting created/modified files."""
    root = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    if not root.is_dir():
        return {}

    snapshot: dict[str, tuple[int, int]] = {}
    try:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            # mtime_ns + size is enough for UI/session tracking purposes
            snapshot[str(path.resolve())] = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        return {}

    return snapshot


class CodeExecuteTool(ToolDefinition):

    @property
    def id(self) -> str:
        return "code_execute"

    @property
    def description(self) -> str:
        return (
            "在本机执行 Python 代码。"
            "如果本地沙箱可用，代码会在沙箱中运行；否则自动使用后端 Python 环境，"
            "其中包含 pandas、numpy、matplotlib 等内置依赖。"
            "重要：每次调用都在全新的隔离命名空间中执行，变量、导入和数据不会跨调用保留。"
            "每次调用都必须包含所需的 import 和数据加载。多步骤分析应尽量放在一次调用中完成，"
            "不要拆成多个依赖状态的调用。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"超时时间，单位秒（默认 {DEFAULT_TIMEOUT}，最大 {MAX_TIMEOUT}）",
                    "default": DEFAULT_TIMEOUT,
                },
            },
            "required": ["code"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        code = args.get("code", "")
        if not code.strip():
            return ToolResult(error="No code provided")

        timeout = min(args.get("timeout", DEFAULT_TIMEOUT), MAX_TIMEOUT)
        before_snapshot = _snapshot_workspace(ctx.workspace)

        manager = get_sandbox_manager()
        sandbox_metadata: dict[str, Any] = {"used": False}
        if manager.is_enabled():
            try:
                sandbox_result = await manager.run_python(
                    session_id=ctx.session_id,
                    code=code,
                    cwd=str(Path(ctx.workspace).resolve() if ctx.workspace else Path.cwd().resolve()),
                    workspace=ctx.workspace,
                    timeout=timeout,
                )
                output = sandbox_result.output
                exit_code = sandbox_result.exit_code
                sandbox_metadata = {"used": True, **sandbox_result.metadata}
            except SandboxUnavailable as exc:
                if manager.is_required():
                    return ToolResult(
                        error=f"Sandbox unavailable: {exc}",
                        metadata={"sandbox": {"used": False, "required": True, "error": str(exc)}},
                    )
                try:
                    output, exit_code = await asyncio.wait_for(
                        asyncio.to_thread(_run_code, code),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    return ToolResult(
                        error=f"Execution timed out after {timeout}s",
                        metadata={"timeout": True, "sandbox": {"used": False, "error": str(exc)}},
                    )
                except Exception as inner_exc:
                    return ToolResult(error=f"Execution failed: {inner_exc}")
        else:
            try:
                output, exit_code = await asyncio.wait_for(
                    asyncio.to_thread(_run_code, code),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                return ToolResult(
                    error=f"Execution timed out after {timeout}s",
                    metadata={"timeout": True, "sandbox": sandbox_metadata},
                )
            except Exception as exc:
                return ToolResult(error=f"Execution failed: {exc}")

        title = f"python: {code[:60]}..." if len(code) > 60 else f"python: {code}"
        after_snapshot = _snapshot_workspace(ctx.workspace)
        written_files = sorted(
            path
            for path, sig in after_snapshot.items()
            if before_snapshot.get(path) != sig
        )

        return ToolResult(
            output=output,
            title=title,
            metadata={
                "exit_code": exit_code,
                "language": "python",
                "written_files": written_files,
                "sandbox": sandbox_metadata,
            },
            error=f"Code execution failed with exit code {exit_code}" if exit_code != 0 else None,
        )


def _run_code(code: str) -> tuple[str, int]:
    """Execute *code* in an isolated namespace and return (output, exit_code)."""
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    exit_code = 0

    # Fresh namespace so each call is isolated.
    namespace: dict[str, Any] = {"__builtins__": __builtins__}

    # Save/restore cwd so user code can't permanently change it.
    original_cwd = os.getcwd()

    try:
        compiled = compile(code, "<code_execute>", "exec")
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(compiled, namespace)
    except SystemExit as e:
        # Allow sys.exit() — treat the exit code as the return code.
        exit_code = e.code if isinstance(e.code, int) else 1
    except Exception:
        traceback.print_exc(file=stderr_buf)
        exit_code = 1
    finally:
        try:
            os.chdir(original_cwd)
        except OSError:
            pass

    stdout = stdout_buf.getvalue()[:MAX_OUTPUT]
    stderr = stderr_buf.getvalue()[:MAX_OUTPUT]

    parts: list[str] = []
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append(f"STDERR:\n{stderr}")

    output = "\n".join(parts) if parts else "(no output)"
    if exit_code != 0:
        output = f"Exit code: {exit_code}\n{output}"

    return output, exit_code
