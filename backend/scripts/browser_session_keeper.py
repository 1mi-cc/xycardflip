from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import quote


PROVIDER_CONFIG = {
    "jd": {
        "default_keyword": "Pokemon Card PSA 10",
        "default_debug_port": 9445,
        "start_url": "https://search.jd.com/Search?keyword={keyword}",
    },
    "pinduoduo": {
        "default_keyword": "Pokemon Card PSA 10",
        "default_debug_port": 9446,
        "start_url": "https://mobile.yangkeduo.com/search_result.html?search_key={keyword}",
    },
}


def _load_requests():
    try:
        import requests  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Missing dependency for browser session keeper: {exc}") from exc
    return requests


def _edge_executable() -> str:
    candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise SystemExit("Edge executable not found.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch or reuse a persistent Edge remote-debug session for marketplace browser bridges.",
    )
    parser.add_argument("--provider", choices=sorted(PROVIDER_CONFIG.keys()), required=True)
    parser.add_argument("--keyword", default="")
    parser.add_argument("--remote-debug-port", type=int, default=0)
    parser.add_argument("--profile-directory", default="Default")
    parser.add_argument("--reuse-if-running", action="store_true")
    return parser


def _build_start_url(provider: str, keyword: str) -> str:
    cfg = PROVIDER_CONFIG[provider]
    encoded = quote(str(keyword or cfg["default_keyword"]).strip() or str(cfg["default_keyword"]), safe="")
    return cfg["start_url"].format(keyword=encoded)


def _wait_for_debug_endpoint(port: int, timeout_sec: int = 20) -> dict:
    requests = _load_requests()
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            payload = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=1).json()
            if isinstance(payload, dict):
                return payload
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"Failed to connect to Edge remote debugging endpoint on {port}.")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    cfg = PROVIDER_CONFIG[args.provider]
    port = int(args.remote_debug_port or cfg["default_debug_port"])
    start_url = _build_start_url(args.provider, args.keyword)
    requests = _load_requests()

    if args.reuse_if_running:
        try:
            version = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=1).json()
            print(
                json.dumps(
                    {
                        "provider": args.provider,
                        "remote_debug_port": port,
                        "reused": True,
                        "browser_version": version.get("Browser", ""),
                        "websocket_url": version.get("webSocketDebuggerUrl", ""),
                        "start_url": start_url,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        except Exception:
            pass

    edge_bin = _edge_executable()
    user_data = Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
    proc = subprocess.Popen(
        [
            edge_bin,
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            "--user-data-dir=" + str(user_data),
            "--profile-directory=" + str(args.profile_directory),
            "--no-first-run",
            "--no-default-browser-check",
            start_url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    version = _wait_for_debug_endpoint(port)
    print(
        json.dumps(
            {
                "provider": args.provider,
                "remote_debug_port": port,
                "pid": proc.pid,
                "reused": False,
                "browser_version": version.get("Browser", ""),
                "websocket_url": version.get("webSocketDebuggerUrl", ""),
                "start_url": start_url,
                "mode": "session-keeper",
                "note": "Leave this browser window open and use browser snapshot bridge with --reuse-browser.",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
