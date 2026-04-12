from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlparse

import requests


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.services.listing_normalizer import normalize_listing  # noqa: E402
from app.services.marketplace_normalizer import normalize_marketplace_canonical_key  # noqa: E402
from app.services.xianyu_client import XianyuClient  # noqa: E402


XIANYU_PLATFORM = "xianyu"
PROVENANCE = "operator_xianyu_browser_session"
DEFAULT_SERVER_HOST = "61.147.247.54"
DEFAULT_PUBLIC_APP_PORT = 18036
DEFAULT_USERNAME = "operator"
DEFAULT_PASSWORD = "Ccj666888.qwer1013"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_timestamp(value: Any) -> str:
    text = _text(value)
    if not text:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    normalized = text.replace("Z", "+00:00")
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _listing_url(item_id: str) -> str:
    if not item_id:
        return ""
    return f"https://www.goofish.com/item?id={item_id}"


def _load_http_modules():
    try:
        import requests as http_requests  # type: ignore
        import websocket  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Missing dependency for browser cookie extraction: {exc}") from exc
    return http_requests, websocket


def _page_match_score(page: dict[str, Any]) -> int:
    url = _text(page.get("url")).lower()
    if not url:
        return -1
    score = 0
    if page.get("type") == "page":
        score += 1
    parsed = urlparse(url)
    if any(host in parsed.netloc for host in ("goofish.com", "xianyu.com", "taobao.com")):
        score += 4
    if "search" in parsed.path:
        score += 2
    if _text(page.get("title")):
        score += 1
    return score


def _select_debug_page(pages: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [page for page in pages if page.get("webSocketDebuggerUrl")]
    if not candidates:
        return None
    ranked = sorted(candidates, key=lambda page: (_page_match_score(page), page.get("id", "")), reverse=True)
    if _page_match_score(ranked[0]) < 0:
        return None
    return ranked[0]


def _debug_cookies(remote_debug_port: int) -> list[dict[str, Any]]:
    http_requests, websocket = _load_http_modules()
    version = http_requests.get(f"http://127.0.0.1:{int(remote_debug_port)}/json/version", timeout=3).json()
    if not isinstance(version, dict):
        raise RuntimeError("Remote debug version payload is invalid.")
    pages = http_requests.get(f"http://127.0.0.1:{int(remote_debug_port)}/json/list", timeout=3).json()
    selected_page = _select_debug_page(pages if isinstance(pages, list) else [])
    if not selected_page:
        raise RuntimeError("No Xianyu-compatible page found in remote debug session.")
    ws_url = _text(selected_page.get("webSocketDebuggerUrl"))
    if not ws_url:
        raise RuntimeError("Selected page has no websocket debugger URL.")

    ws = websocket.create_connection(
        ws_url,
        timeout=8,
        origin=f"http://127.0.0.1:{int(remote_debug_port)}",
    )
    try:
        message_id = 1

        def _send(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            nonlocal message_id
            current_id = message_id
            message_id += 1
            ws.send(json.dumps({"id": current_id, "method": method, "params": params or {}}))
            while True:
                payload = json.loads(ws.recv())
                if payload.get("id") == current_id:
                    return payload

        _send("Network.enable")
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
        return list(((result.get("result") or {}).get("cookies") or []))
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _cookie_string_from_debug_cookies(cookies: list[dict[str, Any]]) -> str:
    required = {"_m_h5_tk", "_m_h5_tk_enc"}
    pairs: dict[str, str] = {}
    for item in cookies:
        domain = _text(item.get("domain")).lower()
        if not any(host in domain for host in ("goofish.com", "xianyu.com", "taobao.com")):
            continue
        name = _text(item.get("name"))
        value = _text(item.get("value"))
        if not name or not value:
            continue
        pairs[name] = value
    if not all(name in pairs for name in required):
        raise RuntimeError("Remote debug Xianyu session is missing required _m_h5_tk cookies.")
    return "; ".join(f"{key}={value}" for key, value in sorted(pairs.items()))


def fetch_xianyu_browser_items(
    *,
    keywords: list[str],
    pages: int,
    remote_debug_port: int,
) -> tuple[str, list[dict[str, Any]]]:
    cookie = _cookie_string_from_debug_cookies(_debug_cookies(remote_debug_port))
    client = XianyuClient()
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for keyword in [item for item in (_text(value) for value in keywords) if item]:
        for page in range(1, max(1, int(pages)) + 1):
            batch = client.fetch(page=page, cookie_override=cookie, keyword=keyword)
            for item in batch:
                if not isinstance(item, dict):
                    continue
                normalized = dict(item)
                normalized["keyword"] = keyword
                item_id = _text(normalized.get("id"))
                dedupe_key = item_id or f"{_text(normalized.get('title'))}:{_text(normalized.get('seller_id'))}"
                if dedupe_key in seen_ids:
                    continue
                seen_ids.add(dedupe_key)
                items.append(normalized)
    return cookie, items


def normalize_xianyu_browser_items(
    items: list[dict[str, Any]],
    *,
    keyword: str = "",
    virtual_only: bool = True,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        title = _text(item.get("title"))
        description = _text(item.get("description"))
        if not title:
            continue
        try:
            list_price = round(float(item.get("price") or 0.0), 2)
        except (TypeError, ValueError):
            continue
        if list_price <= 0:
            continue

        listing = normalize_listing(title=title, description=description)
        item_type = _text(item.get("item_type")) or listing.item_type or "generic"
        if virtual_only and item_type != "virtual_goods":
            continue

        item_id = _text(item.get("id"))
        item_keyword = _text(item.get("keyword")) or _text(keyword)
        canonical_key = normalize_marketplace_canonical_key(
            raw_key=_text(item.get("canonical_key")),
            title=title,
        )
        normalized.append(
            {
                "platform": XIANYU_PLATFORM,
                "offer_id": item_id or None,
                "seller_id": _text(item.get("seller_id")) or None,
                "title": title,
                "canonical_key": canonical_key or title,
                "item_type": item_type,
                "list_price": list_price,
                "shipping_cost": 0.0 if item_type == "virtual_goods" else 0.0,
                "fee_rate": 0.0,
                "currency": "CNY",
                "listed_at": _parse_timestamp(item.get("listed_at")),
                "status": "open",
                "listing_url": _text(item.get("listing_url")) or _listing_url(item_id),
                "raw": {
                    **dict(item.get("raw") or {}),
                    "provenance": PROVENANCE,
                    "keyword": item_keyword,
                    "normalization_item_type": listing.item_type,
                    "normalization_key": listing.normalized_key,
                },
            }
        )
    return normalized


def summarize_xianyu_browser_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(rows),
        "virtual_goods_count": sum(1 for row in rows if _text(row.get("item_type")) == "virtual_goods"),
        "keywords": sorted(
            {
                _text((row.get("raw") or {}).get("keyword"))
                for row in rows
                if _text((row.get("raw") or {}).get("keyword"))
            }
        ),
    }


def _push_rows(
    rows: list[dict[str, Any]],
    *,
    server_host: str,
    public_app_port: int,
    username: str,
    password: str,
    timeout_sec: float,
) -> dict[str, Any]:
    base_url = f"http://{server_host}:{int(public_app_port)}/card-api"
    login = requests.post(
        f"{base_url}/auth/login",
        json={"username": username, "password": password},
        timeout=timeout_sec,
    )
    login.raise_for_status()
    token = ((login.json() or {}).get("data") or {}).get("token")
    if not token:
        raise RuntimeError("Remote auth token missing.")
    response = requests.post(
        f"{base_url}/marketplace/offers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json=rows,
        timeout=timeout_sec,
    )
    response.raise_for_status()
    return response.json()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import real Xianyu offers from a local browser session.")
    parser.add_argument("--keyword", action="append", default=[], help="Repeatable Xianyu keyword.")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--remote-debug-port", type=int, default=9447)
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--allow-non-virtual", action="store_true")
    parser.add_argument("--server-host", default=DEFAULT_SERVER_HOST)
    parser.add_argument("--public-app-port", type=int, default=DEFAULT_PUBLIC_APP_PORT)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--timeout-sec", type=float, default=20.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    keywords = [_text(item) for item in args.keyword if _text(item)]
    if not keywords:
        raise SystemExit("At least one --keyword is required.")
    _cookie, items = fetch_xianyu_browser_items(
        keywords=keywords,
        pages=max(1, int(args.pages)),
        remote_debug_port=int(args.remote_debug_port),
    )
    rows = normalize_xianyu_browser_items(
        items,
        virtual_only=not bool(args.allow_non_virtual),
    )
    summary = summarize_xianyu_browser_rows(rows)
    if not args.push:
        print(json.dumps({"dry_run": True, "summary": summary, "rows": rows}, ensure_ascii=False, indent=2))
        return 0
    result = _push_rows(
        rows,
        server_host=str(args.server_host),
        public_app_port=int(args.public_app_port),
        username=str(args.username),
        password=str(args.password),
        timeout_sec=float(args.timeout_sec),
    )
    print(json.dumps({"dry_run": False, "summary": summary, "result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
