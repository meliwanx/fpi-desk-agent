"""Standalone entry point for OpenYak backend in desktop mode.

Usage:
    python run.py --port 8100 --data-dir /path/to/app/data
"""

import argparse
import faulthandler
import os
import sys
import traceback
from pathlib import Path


def _configure_bundled_node(resource_dir: str | None) -> None:
    """Make bundled Node.js discoverable for subprocesses in desktop builds."""
    if not resource_dir:
        return

    node_root = Path(resource_dir) / "nodejs"
    node_bin = node_root if os.name == "nt" else node_root / "bin"
    if not node_bin.exists():
        return

    current_path = os.environ.get("PATH", "")
    path_parts = [part for part in current_path.split(os.pathsep) if part]
    node_bin_text = str(node_bin)
    if node_bin_text not in path_parts:
        os.environ["PATH"] = os.pathsep.join([node_bin_text, *path_parts])


def _install_crash_reporter() -> None:
    """Install global crash handlers so unhandled exceptions are always logged to stderr.

    stderr is piped to backend.log by the desktop shell (Tauri/Electron),
    so this ensures crash tracebacks are captured for diagnosis.
    """
    # faulthandler: prints C-level tracebacks on segfaults, aborts, etc.
    faulthandler.enable(file=sys.stderr, all_threads=True)

    # sys.excepthook: catches unhandled Python exceptions in the main thread
    _original_excepthook = sys.excepthook

    def _crash_excepthook(exc_type, exc_value, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        # Write with a clear marker so the desktop shell can detect it
        sys.stderr.write(f"\n[FATAL CRASH] Unhandled exception:\n{msg}\n")
        sys.stderr.flush()
        _original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _crash_excepthook

    # threading.excepthook: catches unhandled exceptions in spawned threads
    import threading

    _original_thread_excepthook = threading.excepthook

    def _thread_crash_hook(args):
        msg = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        sys.stderr.write(
            f"\n[FATAL CRASH] Unhandled exception in thread {args.thread}:\n{msg}\n"
        )
        sys.stderr.flush()
        _original_thread_excepthook(args)

    threading.excepthook = _thread_crash_hook


def main() -> None:
    _install_crash_reporter()

    parser = argparse.ArgumentParser(description="OpenYak backend server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory (for desktop mode)")
    parser.add_argument("--resource-dir", type=str, default=None, help="Resource directory (bundled assets from Tauri)")
    args = parser.parse_args()

    # If a data directory is specified, change to it so that SQLite DB,
    # uploads, and other data files are created there.
    if args.data_dir:
        os.makedirs(args.data_dir, exist_ok=True)
        os.chdir(args.data_dir)

    # Store resource dir as env var so the app can find bundled assets (e.g. Node.js)
    if args.resource_dir:
        os.environ["OPENYAK_RESOURCE_DIR"] = args.resource_dir
        _configure_bundled_node(args.resource_dir)

    import uvicorn
    from app.main import create_app

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
