from __future__ import annotations

import os
import runpy
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

from app.config import settings
from app.main import app


def _open_browser_later(port: int) -> None:
    if os.getenv("NO_AUTO_OPEN_BROWSER", "").strip().lower() in {"1", "true", "yes"}:
        return

    def _open() -> None:
        try:
            webbrowser.open(f"http://127.0.0.1:{port}")
        except Exception:
            pass

    threading.Timer(1.5, _open).start()


def _run_script_mode_if_requested() -> bool:
    """
    Run a standalone helper script inside the packaged executable process.
    This avoids launching a second API server process in frozen mode.
    """
    if len(sys.argv) < 3 or sys.argv[1] != "--run-script":
        return False

    script_path = Path(sys.argv[2]).expanduser()
    if not script_path.is_absolute():
        script_path = (Path.cwd() / script_path).resolve()
    if not script_path.exists():
        raise SystemExit(f"script not found: {script_path}")

    script_args = sys.argv[3:]
    original_argv = list(sys.argv)
    try:
        sys.argv = [str(script_path), *script_args]
        runpy.run_path(str(script_path), run_name="__main__")
    finally:
        sys.argv = original_argv
    return True


def run() -> None:
    if _run_script_mode_if_requested():
        return

    host = settings.api_host if settings.api_host else "127.0.0.1"
    port = int(settings.api_port)
    _open_browser_later(port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run()
