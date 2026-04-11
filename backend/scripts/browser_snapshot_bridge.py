from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import quote
from urllib.parse import urlparse


PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "jd": {
        "default_port": 8775,
        "default_keyword": "Pokemon Card PSA 10",
        "start_url": "https://search.jd.com/Search?keyword={keyword}",
        "root_key": "jd_union_open_goods_query_response",
        "result_path": ("queryResult", "goodsList"),
        "id_key": "skuId",
        "title_key": "skuName",
        "link_key": "materialUrl",
    },
    "pinduoduo": {
        "default_port": 8776,
        "default_keyword": "Pokemon Card PSA 10",
        "start_url": "https://mobile.yangkeduo.com/search_result.html?search_key={keyword}",
        "root_key": "goods_search_response",
        "result_path": ("goods_list",),
        "id_key": "goods_id",
        "title_key": "goods_name",
        "link_key": "goods_link",
    },
}


def _load_http_modules():
    try:
        import requests  # type: ignore
        import websocket  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Missing dependency for browser snapshot bridge: {exc}") from exc
    return requests, websocket


def _edge_executable() -> str:
    candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise SystemExit("Edge executable not found.")


def _build_parser(provider: str) -> argparse.ArgumentParser:
    cfg = PROVIDER_CONFIG[provider]
    parser = argparse.ArgumentParser(
        description=f"Run a local {provider} browser snapshot bridge on 127.0.0.1",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(cfg["default_port"]))
    parser.add_argument("--keyword", default=str(cfg["default_keyword"]))
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--remote-debug-port", type=int, default=9222)
    parser.add_argument("--page-wait-ms", type=int, default=6000)
    parser.add_argument("--reuse-browser", action="store_true")
    return parser


def _build_search_url(provider: str, keyword: str, page: int) -> str:
    cfg = PROVIDER_CONFIG[provider]
    encoded = quote(str(keyword or cfg["default_keyword"]).strip() or str(cfg["default_keyword"]), safe="")
    if provider == "jd":
        return cfg["start_url"].format(keyword=encoded) + (f"&page={max(1, int(page))}" if int(page or 1) > 1 else "")
    if provider == "pinduoduo":
        return cfg["start_url"].format(keyword=encoded) + (f"&page={max(1, int(page))}" if int(page or 1) > 1 else "")
    return cfg["start_url"].format(keyword=encoded)


def _keyword_variants(keyword: str) -> list[str]:
    tokens = [
        token.lower()
        for token in re.split(r"\s+", str(keyword or "").strip())
        if token.strip() and not token.strip().isdigit()
    ]
    aliases = {
        "pokemon": ["\u5b9d\u53ef\u68a6", "\u795e\u5947\u5b9d\u8d1d"],
        "card": ["\u5361", "\u5361\u724c", "\u6536\u85cf\u5361"],
        "psa": ["psa"],
        "charizard": ["\u55b7\u706b\u9f99"],
        "pikachu": ["\u76ae\u5361\u4e18"],
        "mewtwo": ["\u8d85\u68a6"],
        "lugia": ["\u6d1b\u5947\u4e9a"],
        "rayquaza": ["\u88c2\u7a7a\u5ea7"],
        "dragonite": ["\u5feb\u9f99"],
        "blastoise": ["\u6c34\u7bad\u9f9f"],
    }
    variants: list[str] = []
    for token in tokens:
        variants.append(token)
        variants.extend(aliases.get(token, []))
    deduped: list[str] = []
    seen: set[str] = set()
    for item in variants:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _extract_price_from_text(value: str | None) -> float:
    text = _normalize_text(value)
    if not text:
        return 0.0
    match = re.search(r"[¥￥]\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return 0.0
    try:
        return float(match.group(1))
    except ValueError:
        return 0.0


def _keyword_score(text: str, keyword: str) -> int:
    lowered = _normalize_text(text).lower()
    if not lowered:
        return 0
    return sum(1 for variant in _keyword_variants(keyword) if variant.lower() in lowered)


def _title_matches_keyword(title: str, keyword: str) -> bool:
    return _keyword_score(title, keyword) >= 2


def _build_extract_expression(provider: str, limit: int) -> str:
    id_key = PROVIDER_CONFIG[provider]["id_key"]
    title_key = PROVIDER_CONFIG[provider]["title_key"]
    link_key = PROVIDER_CONFIG[provider]["link_key"]
    if provider == "jd":
        return f"""
(() => {{
  const maxItems = {max(1, int(limit)) * 10};
  const normalizeText = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
  const items = [];
  const anchors = Array.from(document.querySelectorAll('a[href*="item.jd.com/"]'));
  for (const anchor of anchors) {{
    const href = anchor.href || '';
    const skuMatch = href.match(/item\\.jd\\.com\\/(\\d+)\\.html/);
    if (!skuMatch) continue;
    const container = anchor.closest('li, div');
    items.push({{
      {id_key!r}: skuMatch[1],
      {title_key!r}: normalizeText(anchor.getAttribute('title') || anchor.textContent || container?.innerText || ''),
      {link_key!r}: href,
      priceText: normalizeText(container?.innerText || ''),
      listed_at: new Date().toISOString(),
    }});
    if (items.length >= maxItems) break;
  }}
  return {{
    items,
    bodyText: String(document.body?.innerText || '').slice(0, 60000),
  }};
}})()
""".strip()
    return f"""
(() => {{
  const maxItems = {max(1, int(limit)) * 10};
  const normalizeText = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
  const items = [];
  const anchors = Array.from(document.querySelectorAll('a[href*="goods"], a[href*="search_result"]'));
  for (const anchor of anchors) {{
    const href = anchor.href || '';
    const goodsMatch = href.match(/goods_id=(\\d+)/) || href.match(/goods_id%22%3A(\\d+)/);
    items.push({{
      {id_key!r}: goodsMatch ? goodsMatch[1] : '',
      {title_key!r}: normalizeText(anchor.getAttribute('title') || anchor.textContent || anchor.closest('div,li,a')?.innerText || ''),
      {link_key!r}: href,
      priceText: normalizeText(anchor.closest('div,li,a')?.innerText || ''),
      listed_at: new Date().toISOString(),
    }});
    if (items.length >= maxItems) break;
  }}
  return {{
    items,
    bodyText: String(document.body?.innerText || '').slice(0, 60000),
  }};
}})()
""".strip()


def _coerce_bridge_items(provider: str, raw_items: list[dict[str, Any]], body_text: str, keyword: str, limit: int) -> list[dict[str, Any]]:
    cfg = PROVIDER_CONFIG[provider]
    id_key = str(cfg["id_key"])
    title_key = str(cfg["title_key"])
    link_key = str(cfg["link_key"])
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in raw_items:
        title = _normalize_text(item.get(title_key))
        if not _title_matches_keyword(title, keyword):
            continue
        price = _extract_price_from_text(item.get("priceText") or item.get("price"))
        if price <= 0:
            continue
        listing_id = _normalize_text(item.get(id_key)) or f"{title}:{price}"
        if listing_id in seen:
            continue
        seen.add(listing_id)
        normalized.append(
            {
                id_key: listing_id,
                title_key: title,
                "price": price,
                link_key: _normalize_text(item.get(link_key)),
                "listed_at": item.get("listed_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        if len(normalized) >= max(1, int(limit)):
            return normalized

    lines = [_normalize_text(line) for line in re.split(r"\n+", str(body_text or "")) if _normalize_text(line)]
    for index, line in enumerate(lines):
        if not _title_matches_keyword(line, keyword):
            continue
        nearby = " ".join(lines[index : index + 4])
        price = _extract_price_from_text(nearby)
        if price <= 0:
            continue
        listing_id = f"{line}:{price}"
        if listing_id in seen:
            continue
        seen.add(listing_id)
        normalized.append(
            {
                id_key: listing_id,
                title_key: line,
                "price": price,
                link_key: "",
                "listed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        if len(normalized) >= max(1, int(limit)):
            break
    return normalized


def _connect_browser(provider: str, remote_debug_port: int, reuse_browser: bool, search_url: str):
    requests, websocket = _load_http_modules()
    edge_bin = _edge_executable()
    user_data = Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
    proc = None
    if not reuse_browser:
        proc = subprocess.Popen(
            [
                edge_bin,
                f"--remote-debugging-port={int(remote_debug_port)}",
                "--remote-allow-origins=*",
                "--user-data-dir=" + str(user_data),
                "--profile-directory=Default",
                "--no-first-run",
                "--no-default-browser-check",
                search_url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    version = None
    for _ in range(40):
        try:
            version = requests.get(
                f"http://127.0.0.1:{int(remote_debug_port)}/json/version",
                timeout=1,
            ).json()
            break
        except Exception:
            time.sleep(0.5)
    if not version:
        if proc is not None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], check=False, capture_output=True, text=True)
        raise RuntimeError("Failed to connect to Edge remote debugging endpoint.")

    pages = requests.get(
        f"http://127.0.0.1:{int(remote_debug_port)}/json/list",
        timeout=3,
    ).json()
    ws_url = next(
        (
            page.get("webSocketDebuggerUrl")
            for page in pages
            if page.get("type") == "page" and page.get("webSocketDebuggerUrl")
        ),
        "",
    )
    if not ws_url:
        if proc is not None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], check=False, capture_output=True, text=True)
        raise RuntimeError("No page websocket debugger URL found.")

    ws = websocket.create_connection(
        ws_url,
        timeout=8,
        origin=f"http://127.0.0.1:{int(remote_debug_port)}",
    )
    return requests, websocket, ws, proc


def _send(ws, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if not hasattr(_send, "_message_id"):
        _send._message_id = 1  # type: ignore[attr-defined]
    current_id = _send._message_id  # type: ignore[attr-defined]
    _send._message_id += 1  # type: ignore[attr-defined]
    ws.send(json.dumps({"id": current_id, "method": method, "params": params or {}}))
    while True:
        payload = json.loads(ws.recv())
        if payload.get("id") == current_id:
            return payload


def _capture_snapshot(
    provider: str,
    *,
    keyword: str,
    page: int,
    limit: int,
    remote_debug_port: int,
    page_wait_ms: int,
    reuse_browser: bool,
) -> dict[str, Any]:
    search_url = _build_search_url(provider, keyword, page)
    _requests, _websocket, ws, proc = _connect_browser(provider, remote_debug_port, reuse_browser, search_url)
    try:
        _send(ws, "Network.enable")
        _send(ws, "Page.enable")
        _send(ws, "Page.navigate", {"url": search_url})
        time.sleep(max(1.0, float(page_wait_ms) / 1000.0))
        expression = _build_extract_expression(provider, limit)
        result = _send(
            ws,
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        value = ((result.get("result") or {}).get("result") or {}).get("value") or {}
        raw_items = list(value.get("items") or []) if isinstance(value, dict) else []
        body_text = str(value.get("bodyText") or "") if isinstance(value, dict) else ""
        filtered_items = _coerce_bridge_items(provider, raw_items, body_text, keyword, limit)
        confidence_score = round(min(0.98, 0.25 + (0.18 * len(filtered_items))), 4) if filtered_items else 0.0
        low_confidence = len(filtered_items) == 0

        cfg = PROVIDER_CONFIG[provider]
        if provider == "jd":
            payload = {cfg["root_key"]: {cfg["result_path"][0]: {cfg["result_path"][1]: filtered_items}}}
        else:
            payload = {cfg["root_key"]: {cfg["result_path"][0]: filtered_items}}

        return {
            "provider": provider,
            "keyword": keyword,
            "page": int(page),
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "item_count": len(filtered_items),
            "raw_item_count": len(raw_items),
            "confidence_score": confidence_score,
            "low_confidence": low_confidence,
            "warnings": (
                ["No strongly keyword-matching items were found in the visible browser results."]
                if low_confidence
                else []
            ),
            "payload": payload,
            "risk_level": "high-risk-unstable",
            "mode": "cookie-browser-bridge",
        }
    finally:
        try:
            ws.close()
        except Exception:
            pass
        if proc is not None:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
            )


def _build_handler(
    *,
    provider: str,
    default_keyword: str,
    default_page: int,
    default_limit: int,
    remote_debug_port: int,
    page_wait_ms: int,
    reuse_browser: bool,
):
    class BrowserSnapshotHandler(BaseHTTPRequestHandler):
        server_version = "BrowserSnapshotBridge/1.0"

        def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(
                    200,
                    {
                        "provider": provider,
                        "mode": "cookie-browser-bridge",
                        "risk_level": "high-risk-unstable",
                        "host_only": True,
                    },
                )
                return
            if parsed.path != "/snapshot":
                self._send_json(404, {"detail": "not found"})
                return

            query = parse_qs(parsed.query or "")
            keyword = str((query.get("keyword") or [default_keyword])[0] or default_keyword).strip()
            page = max(1, min(20, int((query.get("page") or [default_page])[0] or default_page)))
            limit = max(1, min(100, int((query.get("limit") or [default_limit])[0] or default_limit)))
            try:
                payload = _capture_snapshot(
                    provider,
                    keyword=keyword,
                    page=page,
                    limit=limit,
                    remote_debug_port=remote_debug_port,
                    page_wait_ms=page_wait_ms,
                    reuse_browser=reuse_browser,
                )
            except Exception as exc:
                self._send_json(
                    502,
                    {
                        "detail": str(exc),
                        "provider": provider,
                        "mode": "cookie-browser-bridge",
                        "risk_level": "high-risk-unstable",
                    },
                )
                return
            self._send_json(200, payload)

    return BrowserSnapshotHandler


def main(provider: str, argv: list[str] | None = None) -> int:
    provider_key = str(provider or "").strip().lower()
    if provider_key not in PROVIDER_CONFIG:
        raise SystemExit(f"unsupported provider: {provider}")
    cfg = PROVIDER_CONFIG[provider_key]
    parser = _build_parser(provider_key)
    args = parser.parse_args(argv)
    handler = _build_handler(
        provider=provider_key,
        default_keyword=str(args.keyword or cfg["default_keyword"]),
        default_page=max(1, int(args.page)),
        default_limit=max(1, int(args.limit)),
        remote_debug_port=int(args.remote_debug_port),
        page_wait_ms=max(1000, int(args.page_wait_ms)),
        reuse_browser=bool(args.reuse_browser),
    )
    server = ThreadingHTTPServer((args.host, int(args.port)), handler)
    print(
        json.dumps(
            {
                "provider": provider_key,
                "listen": f"http://{args.host}:{args.port}",
                "snapshot_url": f"http://{args.host}:{args.port}/snapshot",
                "health_url": f"http://{args.host}:{args.port}/health",
                "keyword": str(args.keyword or cfg["default_keyword"]),
                "mode": "cookie-browser-bridge",
                "risk_level": "high-risk-unstable",
            },
            ensure_ascii=False,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=sorted(PROVIDER_CONFIG.keys()))
    known, rest = parser.parse_known_args()
    raise SystemExit(main(known.provider, rest))
