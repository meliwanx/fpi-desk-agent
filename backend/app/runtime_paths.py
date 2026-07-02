"""Runtime path names used by fpi-agent."""

from __future__ import annotations

from pathlib import Path

APP_CONFIG_DIR_NAME = ".fpiagent"
WORKSPACE_OUTPUT_DIR_NAME = "fpiagent_written"


def app_config_file(base: Path, *parts: str) -> Path:
    """Return a writable file path under ``.fpiagent``."""
    return base / APP_CONFIG_DIR_NAME / Path(*parts)


def workspace_output_dir(workspace: str | Path) -> Path:
    """Return the writable generated-files directory for a workspace."""
    return Path(workspace).resolve() / WORKSPACE_OUTPUT_DIR_NAME
