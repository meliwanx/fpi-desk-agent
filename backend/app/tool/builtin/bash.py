"""Bash tool — shell execution with timeout.

Uses subprocess.run in a thread to avoid Windows event-loop issues
(SelectorEventLoop does not support asyncio.create_subprocess_exec).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from typing import Any

from app.sandbox.manager import SandboxUnavailable, get_sandbox_manager
from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext
from app.tool.subprocess_compat import (
    decode_subprocess_output,
    find_shell,
    get_subprocess_kwargs,
)
from app.tool.workspace import WorkspaceViolation, get_default_output_dir, validate_cwd

def _bash_cfg():
    from app.config import get_settings
    s = get_settings()
    return s.bash_timeout, s.bash_max_timeout


class BashTool(ToolDefinition):

    @property
    def id(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return (
            "执行本机 shell 命令，并返回 stdout 和 stderr。"
            "命令在这台电脑上运行，默认工作目录为当前工作区；也可以通过明确绝对路径只读查看本机其他位置。"
            "如果配置了本地沙箱，会限制写入范围。默认超时时间 120 秒，最大 600 秒。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间，单位秒",
                    "default": _bash_cfg()[0],
                },
                "cwd": {
                    "type": "string",
                    "description": "命令的工作目录",
                },
            },
            "required": ["command"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        command = args["command"]
        default_timeout, max_timeout = _bash_cfg()
        timeout = min(args.get("timeout", default_timeout), max_timeout)
        cwd = args.get("cwd")

        # Workspace restriction: validate/default cwd (defaults to openyak_written/)
        try:
            if not cwd and ctx.workspace:
                cwd = get_default_output_dir(ctx.workspace)
            cwd = validate_cwd(cwd, ctx.workspace)
        except WorkspaceViolation as e:
            return ToolResult(error=str(e))

        # Ensure cwd exists — openyak_written/ may not have been created yet
        if cwd:
            import pathlib
            try:
                pathlib.Path(cwd).mkdir(parents=True, exist_ok=True)
            except OSError:
                # If we can't create it, fall back to workspace or None
                cwd = ctx.workspace or None

        manager = get_sandbox_manager()
        if manager.is_enabled():
            try:
                sandbox_result = await manager.run_shell(
                    session_id=ctx.session_id,
                    command=command,
                    cwd=cwd or ctx.workspace or os.getcwd(),
                    workspace=ctx.workspace,
                    timeout=timeout,
                )
                metadata = {
                    "exit_code": sandbox_result.exit_code,
                    "sandbox": {"used": True, **sandbox_result.metadata},
                }
                return ToolResult(
                    output=sandbox_result.output,
                    title=command[:80],
                    metadata=metadata,
                    error=(
                        f"Command failed with exit code {sandbox_result.exit_code}"
                        if sandbox_result.exit_code != 0
                        else None
                    ),
                )
            except SandboxUnavailable as exc:
                if manager.is_required():
                    return ToolResult(
                        error=f"Sandbox unavailable: {exc}",
                        metadata={"sandbox": {"used": False, "required": True, "error": str(exc)}},
                    )

        extra_kwargs = get_subprocess_kwargs()
        shell_prefix = find_shell()

        def _run() -> subprocess.CompletedProcess[bytes]:
            return subprocess.run(
                [*shell_prefix, command],
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                timeout=timeout,
                env={**os.environ},
                **extra_kwargs,
            )

        try:
            result = await asyncio.to_thread(_run)
        except subprocess.TimeoutExpired:
            return ToolResult(
                error=f"Command timed out after {timeout}s",
                metadata={"timeout": True},
            )
        except FileNotFoundError:
            return ToolResult(error="Shell not found")
        except PermissionError:
            return ToolResult(error="Permission denied")

        stdout = decode_subprocess_output(result.stdout)
        stderr = decode_subprocess_output(result.stderr)

        output_parts = []
        if stdout:
            output_parts.append(stdout)
        if stderr:
            output_parts.append(f"STDERR:\n{stderr}")

        output = "\n".join(output_parts) if output_parts else "(no output)"
        exit_code = result.returncode

        if exit_code != 0:
            output = f"Exit code: {exit_code}\n{output}"

        return ToolResult(
            output=output,
            title=command[:80],
            metadata={"exit_code": exit_code, "sandbox": {"used": False}},
            error=f"Command failed with exit code {exit_code}" if exit_code != 0 else None,
        )
