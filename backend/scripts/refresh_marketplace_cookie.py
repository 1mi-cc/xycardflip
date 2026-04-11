from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_OVERRIDE = os.getenv("COOKIE_ENV_PATH", "").strip() or os.getenv("DOTENV_PATH", "").strip()
ENV_PATH = Path(ENV_OVERRIDE).expanduser() if ENV_OVERRIDE else ROOT_DIR / ".env"

_ALL_TARGET_NAMES = {
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
    "pt_key",
    "pt_pin",
}


PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "xianyu": {
        "env_key": "XIAN_YU_COOKIE",
        "domains": ("goofish.com", "xianyu.com", "taobao.com"),
        "required_names": ("_m_h5_tk", "_m_h5_tk_enc"),
        "preferred_names": ("_m_h5_tk", "_m_h5_tk_enc", "cookie2", "_tb_token_"),
        "start_url": "https://www.goofish.com/",
        "cdp_urls": (
            "https://www.goofish.com/",
            "https://h5api.m.goofish.com/",
            "https://www.taobao.com/",
        ),
        "target_names": _ALL_TARGET_NAMES,
    },
    "jd": {
        "env_key": "JD_COOKIE",
        "domains": ("jd.com", "3.cn", "jd.hk"),
        "required_names": (),
        "preferred_names": ("pt_key", "pt_pin"),
        "start_url": "https://www.jd.com/",
        "cdp_urls": (
            "https://www.jd.com/",
            "https://item.jd.com/",
            "https://api.m.jd.com/",
        ),
        "target_names": (),
    },
    "pinduoduo": {
        "env_key": "PINDUODUO_COOKIE",
        "domains": ("pinduoduo.com", "yangkeduo.com"),
        "required_names": (),
        "preferred_names": (),
        "start_url": "https://mobile.yangkeduo.com/",
        "cdp_urls": (
            "https://mobile.yangkeduo.com/",
            "https://mobile.pinduoduo.com/",
            "https://api.pinduoduo.com/",
        ),
        "target_names": (),
    },
}


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
    import browser_cookie3

    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    browser_roots: list[tuple[str, Path, Callable]] = [
        ("edge", local_app_data / "Microsoft" / "Edge" / "User Data", browser_cookie3.edge),
        ("chrome", local_app_data / "Google" / "Chrome" / "User Data", browser_cookie3.chrome),
    ]

    for label, root, loader in browser_roots:
        local_state = root / "Local State"
        if not root.exists():
            continue
        profiles = [
            profile
            for profile in root.iterdir()
            if profile.is_dir() and (profile.name == "Default" or profile.name.startswith("Profile "))
        ]
        for profile in sorted(profiles, key=lambda item: item.name):
            cookie_file = profile / "Network" / "Cookies"
            if cookie_file.exists():
                yield (
                    f"{label}:{profile.name}",
                    lambda domain, lf=loader, cf=cookie_file, ks=local_state: lf(
                        domain_name=domain,
                        cookie_file=str(cf),
                        key_file=str(ks),
                    ),
                )

    yield ("edge:auto", lambda domain: browser_cookie3.edge(domain_name=domain))
    yield ("chrome:auto", lambda domain: browser_cookie3.chrome(domain_name=domain))


def _build_cookie_string(items: list[tuple[str, str]]) -> str:
    return "; ".join(f"{key}={value}" for key, value in items if key and value).strip()


def _collect_cookies(domain: str, *, target_names: set[str]) -> list[tuple[str, str]]:
    collected: dict[str, str] = {}
    allow_all = not target_names
    for _label, loader in _iter_cookie_sources():
        try:
            jar = loader(domain)
        except Exception:
            continue
        for cookie in jar:
            name = str(cookie.name or "").strip()
            value = str(cookie.value or "").strip()
            if not name or not value:
                continue
            if allow_all or name in target_names:
                collected[name] = value
        if collected:
            continue
    return sorted(collected.items(), key=lambda item: item[0])


def _score_cookie_text(
    cookie_text: str,
    *,
    required_names: tuple[str, ...],
    preferred_names: tuple[str, ...],
) -> tuple[int, int, int, int]:
    required_hits = sum(1 for name in required_names if f"{name}=" in cookie_text)
    preferred_hits = sum(1 for name in preferred_names if f"{name}=" in cookie_text)
    total_pairs = cookie_text.count("=")
    return (required_hits, preferred_hits, total_pairs, len(cookie_text))


def _extract_best_cookie_string(
    *,
    domains: tuple[str, ...],
    target_names: set[str],
    required_names: tuple[str, ...],
    preferred_names: tuple[str, ...],
) -> str:
    candidates: list[str] = []
    for domain in domains:
        items = _collect_cookies(domain, target_names=target_names)
        if not items:
            continue
        text = _build_cookie_string(items)
        if text:
            candidates.append(text)

    scored = sorted(
        candidates,
        key=lambda value: _score_cookie_text(
            value,
            required_names=required_names,
            preferred_names=preferred_names,
        ),
        reverse=True,
    )
    return scored[0] if scored else ""


def _extract_cookie_via_edge_cdp(
    *,
    domains: tuple[str, ...],
    required_names: tuple[str, ...],
    preferred_names: tuple[str, ...],
    start_url: str,
    cdp_urls: tuple[str, ...],
    target_names: set[str],
) -> str:
    import requests
    import websocket

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
            start_url,
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
        _send("Page.navigate", {"url": start_url})
        time.sleep(5)
        result = _send("Network.getCookies", {"urls": list(cdp_urls)})
        cookies = result.get("result", {}).get("cookies", [])
        if not cookies:
            return ""

        allow_all = not target_names
        cookie_map: dict[str, str] = {}
        for item in cookies:
            domain = str(item.get("domain") or "")
            name = str(item.get("name") or "").strip()
            value = str(item.get("value") or "").strip()
            if not name or not value:
                continue
            if not any(token in domain for token in domains):
                continue
            if allow_all or name in target_names:
                cookie_map[name] = value

        if not cookie_map:
            return ""
        cookie_text = _build_cookie_string(sorted(cookie_map.items(), key=lambda item: item[0]))
        if required_names and not all(f"{name}=" in cookie_text for name in required_names):
            return ""
        return cookie_text
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


def _resolve_provider_config(provider: str) -> dict[str, Any]:
    key = str(provider or "").strip().lower()
    if key not in PROVIDER_CONFIG:
        raise SystemExit(f"unsupported provider: {provider}")
    return PROVIDER_CONFIG[key]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh marketplace browser cookie into backend .env")
    parser.add_argument(
        "--provider",
        choices=sorted(PROVIDER_CONFIG.keys()),
        required=True,
        help="Marketplace provider to refresh.",
    )
    parser.add_argument(
        "--kill-browsers",
        action="store_true",
        help="Kill Chrome/Edge first to release cookie DB locks.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    provider_cfg = _resolve_provider_config(args.provider)

    if args.kill_browsers:
        _kill_browser_processes()

    target_names = set(provider_cfg.get("target_names") or ())
    required_names = tuple(provider_cfg.get("required_names") or ())
    preferred_names = tuple(provider_cfg.get("preferred_names") or ())
    domains = tuple(provider_cfg.get("domains") or ())

    cookie_value = _extract_best_cookie_string(
        domains=domains,
        target_names=target_names,
        required_names=required_names,
        preferred_names=preferred_names,
    )
    should_try_cdp = (not cookie_value) or (
        bool(required_names) and not all(f"{name}=" in cookie_value for name in required_names)
    )
    if should_try_cdp:
        cdp_cookie = _extract_cookie_via_edge_cdp(
            domains=domains,
            required_names=required_names,
            preferred_names=preferred_names,
            start_url=str(provider_cfg["start_url"]),
            cdp_urls=tuple(provider_cfg["cdp_urls"]),
            target_names=target_names,
        )
        if cdp_cookie:
            cookie_value = cdp_cookie

    if not cookie_value:
        print(f"failed: no cookie found for provider={args.provider}")
        return 1

    if required_names and not all(f"{name}=" in cookie_value for name in required_names):
        print(f"failed: extracted cookie missing required names for provider={args.provider}: {', '.join(required_names)}")
        return 2

    env_key = str(provider_cfg["env_key"])
    _upsert_env_value(ENV_PATH, env_key, cookie_value)
    print(f"ok: updated {ENV_PATH} with {env_key} (len={len(cookie_value)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
