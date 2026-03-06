from __future__ import annotations

import argparse
import os
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Iterable

import browser_cookie3
import json
import requests
import websocket


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_OVERRIDE = os.getenv("COOKIE_ENV_PATH", "").strip() or os.getenv("DOTENV_PATH", "").strip()
ENV_PATH = Path(ENV_OVERRIDE).expanduser() if ENV_OVERRIDE else ROOT_DIR / ".env"

TARGET_NAMES = {
    "_m_h5_tk",
    "_m_h5_tk_enc",
    "cookie2",
    "unb",
    "t",
    "cna",
    "isg",
    "sgcookie",
    "_tb_token_",
    "tracknick",
    "havana_lgc2_77",
    "havana_lgc_exp",
    "_hvn_lgc_",
    "tfstk",
}

TARGET_DOMAINS = ("goofish.com", "xianyu.com", "taobao.com")


def _kill_browser_processes() -> None:
    for name in ("chrome.exe", "msedge.exe"):
        subprocess.run(
            ["taskkill", "/IM", name, "/F"],
            check=False,
            capture_output=True,
            text=True,
        )


def _edge_executable() -> str:
    candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def _iter_cookie_sources() -> Iterable[tuple[str, Callable]]:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    browser_roots: list[tuple[str, Path, Callable]] = [
        ("edge", local_app_data / "Microsoft" / "Edge" / "User Data", browser_cookie3.edge),
        ("chrome", local_app_data / "Google" / "Chrome" / "User Data", browser_cookie3.chrome),
    ]

    for label, root, loader in browser_roots:
        local_state = root / "Local State"
        if not root.exists():
            continue
        profiles = [p for p in root.iterdir() if p.is_dir() and (p.name == "Default" or p.name.startswith("Profile "))]
        for profile in sorted(profiles, key=lambda p: p.name):
            cookie_file = profile / "Network" / "Cookies"
            if cookie_file.exists():
                yield (f"{label}:{profile.name}", lambda domain, lf=loader, cf=cookie_file, ks=local_state: lf(domain_name=domain, cookie_file=str(cf), key_file=str(ks)))

    # Fallback to library defaults.
    yield ("edge:auto", lambda domain: browser_cookie3.edge(domain_name=domain))
    yield ("chrome:auto", lambda domain: browser_cookie3.chrome(domain_name=domain))


def _collect_cookies(domain: str) -> list[tuple[str, str]]:
    collected: dict[str, str] = {}
    for label, loader in _iter_cookie_sources():
        try:
            jar = loader(domain)
        except Exception:
            continue
        for cookie in jar:
            name = str(cookie.name or "").strip()
            value = str(cookie.value or "").strip()
            if not name or not value:
                continue
            if name in TARGET_NAMES:
                collected[name] = value
            elif domain.endswith("goofish.com") and name.startswith("_m_h5_"):
                collected[name] = value
        if "_m_h5_tk" in collected and "_m_h5_tk_enc" in collected:
            break
    return sorted(collected.items())


def _build_cookie_string(items: list[tuple[str, str]]) -> str:
    return "; ".join(f"{k}={v}" for k, v in items if k and v).strip()


def _extract_best_cookie_string() -> str:
    candidates: list[str] = []
    for domain in TARGET_DOMAINS:
        items = _collect_cookies(domain)
        if not items:
            continue
        text = _build_cookie_string(items)
        if text:
            candidates.append(text)

    scored = sorted(
        candidates,
        key=lambda s: (
            int("_m_h5_tk=" in s),
            int("_m_h5_tk_enc=" in s),
            len(s),
        ),
        reverse=True,
    )
    return scored[0] if scored else ""


def _extract_cookie_via_edge_cdp() -> str:
    edge_bin = _edge_executable()
    if not edge_bin:
        return ""

    user_data = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data"
    if not user_data.exists():
        return ""

    proc = subprocess.Popen(
        [
            edge_bin,
            "--remote-debugging-port=9222",
            "--remote-allow-origins=*",
            "--user-data-dir=" + str(user_data),
            "--profile-directory=Default",
            "--no-first-run",
            "--no-default-browser-check",
            "https://www.goofish.com/",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    ws = None
    try:
        version = None
        for _ in range(40):
            try:
                version = requests.get("http://127.0.0.1:9222/json/version", timeout=1).json()
                break
            except Exception:
                time.sleep(0.5)
        if not version:
            return ""

        pages = requests.get("http://127.0.0.1:9222/json/list", timeout=3).json()
        ws_url = next(
            (
                page.get("webSocketDebuggerUrl")
                for page in pages
                if page.get("type") == "page" and page.get("webSocketDebuggerUrl")
            ),
            "",
        )
        if not ws_url:
            return ""

        ws = websocket.create_connection(
            ws_url,
            timeout=8,
            origin="http://127.0.0.1:9222",
        )

        message_id = 1

        def _send(method: str, params: dict | None = None) -> dict:
            nonlocal message_id
            current_id = message_id
            message_id += 1
            ws.send(json.dumps({"id": current_id, "method": method, "params": params or {}}))
            while True:
                payload = json.loads(ws.recv())
                if payload.get("id") == current_id:
                    return payload

        _send("Network.enable")
        _send("Page.enable")
        _send("Page.navigate", {"url": "https://www.goofish.com/"})
        time.sleep(5)
        result = _send(
            "Network.getCookies",
            {
                "urls": [
                    "https://www.goofish.com/",
                    "https://h5api.m.goofish.com/",
                    "https://www.taobao.com/",
                ]
            },
        )
        cookies = result.get("result", {}).get("cookies", [])
        if not cookies:
            return ""

        cookie_map: dict[str, str] = {}
        for item in cookies:
            domain = str(item.get("domain") or "")
            name = str(item.get("name") or "").strip()
            value = str(item.get("value") or "").strip()
            if not name or not value:
                continue
            if not any(token in domain for token in TARGET_DOMAINS):
                continue
            cookie_map[name] = value

        if not cookie_map:
            return ""
        # Keep deterministic output for easy diff.
        items = sorted(cookie_map.items(), key=lambda pair: pair[0])
        return _build_cookie_string(items)
    finally:
        try:
            if ws is not None:
                ws.close()
        except Exception:
            pass
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )


def _upsert_env_value(path: Path, key: str, value: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    escaped = value.replace("\\", "\\\\")
    line = f"{key}={escaped}"
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(line, text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh Xianyu/Goofish cookie into backend .env")
    parser.add_argument(
        "--kill-browsers",
        action="store_true",
        help="Kill Chrome/Edge first to release cookie DB lock.",
    )
    args = parser.parse_args()

    if args.kill_browsers:
        _kill_browser_processes()

    cookie_value = _extract_best_cookie_string()
    if "_m_h5_tk=" not in cookie_value or "_m_h5_tk_enc=" not in cookie_value:
        cdp_cookie = _extract_cookie_via_edge_cdp()
        if cdp_cookie:
            cookie_value = cdp_cookie
    if not cookie_value:
        print("failed: no cookie found from Edge/Chrome profiles")
        return 1

    required = ("_m_h5_tk=", "_m_h5_tk_enc=")
    if not all(k in cookie_value for k in required):
        print("failed: extracted cookie missing _m_h5_tk or _m_h5_tk_enc")
        return 2

    _upsert_env_value(ENV_PATH, "XIAN_YU_COOKIE", cookie_value)
    print(f"ok: updated {ENV_PATH} with XIAN_YU_COOKIE (len={len(cookie_value)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
