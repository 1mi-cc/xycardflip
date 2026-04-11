from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import quote


PROVIDER_CONFIG = {
    "jd": {
        "default_keyword": "Q coin auto recharge",
        "default_debug_port": 9445,
        "start_url": "https://search.jd.com/Search?keyword={keyword}",
    },
    "pinduoduo": {
        "default_keyword": "Q币 自动充值",
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
    parser.add_argument("--check-only", action="store_true")
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


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _provider_hosts(provider: str) -> tuple[str, ...]:
    return {
        "jd": ("jd.com",),
        "pinduoduo": ("yangkeduo.com", "pinduoduo.com"),
    }.get(provider, ())


def _infer_page_state(provider: str, *, current_url: str, page_title: str) -> str:
    url = _normalize_text(current_url).lower()
    title = _normalize_text(page_title).lower()
    parsed = urlparse(url)
    path = _normalize_text(parsed.path).lower()
    netloc = _normalize_text(parsed.netloc).lower()
    if provider == "pinduoduo":
        if "search_result" in path:
            return "search_results"
        if path.endswith("/login.html") or path.endswith("/login") or ("login" in path and "search_result" not in path):
            return "login"
        if title == "登录" or "登录 -" in title:
            return "login"
        return "unknown"
    if provider == "jd":
        if "cfe.m.jd.com" in netloc or "risk_handler" in path:
            return "risk_challenge"
        if "search.jd.com" in netloc and "search" in path:
            return "search_results"
        if "passport" in path or path.endswith("/login") or "login" in path:
            return "login"
        if title == "登录" or "登录 -" in title:
            return "login"
        return "unknown"
    return "unknown"


def _page_match_score(provider: str, page: dict) -> int:
    url = _normalize_text(page.get("url"))
    if not url:
        return -1
    score = 0
    if page.get("type") == "page":
        score += 1
    netloc = _normalize_text(urlparse(url).netloc).lower()
    if any(host in netloc for host in _provider_hosts(provider)):
        score += 4
    if "search" in url.lower():
        score += 2
    if _normalize_text(page.get("title")):
        score += 1
    return score


def _select_target_page(provider: str, pages: list[dict]) -> dict | None:
    candidates = [page for page in pages if page.get("webSocketDebuggerUrl")]
    if not candidates:
        return None
    ranked = sorted(candidates, key=lambda page: (_page_match_score(provider, page), page.get("id", "")), reverse=True)
    if _page_match_score(provider, ranked[0]) < 0:
        return None
    return ranked[0]


def _probe_existing_session(provider: str, port: int) -> dict:
    requests = _load_requests()
    version = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=1).json()
    pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=3).json()
    selected_page = _select_target_page(provider, pages if isinstance(pages, list) else []) or {}
    current_url = _normalize_text(selected_page.get("url"))
    page_title = _normalize_text(selected_page.get("title"))
    page_state = _infer_page_state(provider, current_url=current_url, page_title=page_title)
    return {
        "provider": provider,
        "remote_debug_port": port,
        "browser_version": version.get("Browser", ""),
        "websocket_url": version.get("webSocketDebuggerUrl", ""),
        "current_url": current_url,
        "page_title": page_title,
        "page_state": page_state,
        "login_required": page_state == "login",
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    cfg = PROVIDER_CONFIG[args.provider]
    port = int(args.remote_debug_port or cfg["default_debug_port"])
    start_url = _build_start_url(args.provider, args.keyword)

    if args.check_only:
        try:
            payload = _probe_existing_session(args.provider, port)
        except Exception as exc:
            raise SystemExit(f"Browser session probe failed: {exc}") from exc
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    if args.reuse_if_running:
        try:
            payload = _probe_existing_session(args.provider, port)
            payload["reused"] = True
            payload["start_url"] = start_url
            print(json.dumps(payload, ensure_ascii=False))
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
    _wait_for_debug_endpoint(port)
    try:
        probe = _probe_existing_session(args.provider, port)
    except Exception as exc:
        raise SystemExit(f"Browser session probe failed after launch: {exc}") from exc
    print(
        json.dumps(
            {
                "pid": proc.pid,
                "reused": False,
                "start_url": start_url,
                "mode": "session-keeper",
                "note": "Leave this browser window open and use browser snapshot bridge with --reuse-browser.",
                **probe,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
