from __future__ import annotations

import os
import threading
import webbrowser

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


def run() -> None:
    host = settings.api_host if settings.api_host else "127.0.0.1"
    port = int(settings.api_port)
    _open_browser_later(port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run()
