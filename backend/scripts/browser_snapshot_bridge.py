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
    suffix = f"&page={max(1, int(page))}" if int(page or 1) > 1 else ""
    return cfg["start_url"].format(keyword=encoded) + suffix


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


def _keyword_variants(keyword: str) -> list[str]:
    tokens = [
        token.lower()
        for token in re.split(r"\s+", str(keyword or "").strip())
        if token.strip() and not token.strip().isdigit()
    ]
    aliases = {
        "pokemon": ["宝可梦", "神奇宝贝"],
        "card": ["卡", "卡牌", "收藏卡"],
        "psa": ["psa"],
        "charizard": ["喷火龙"],
        "pikachu": ["皮卡丘"],
        "mewtwo": ["超梦"],
        "lugia": ["洛奇亚"],
        "rayquaza": ["裂空座"],
        "dragonite": ["快龙"],
        "blastoise": ["水箭龟"],
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


def _keyword_score(text: str, keyword: str) -> int:
    lowered = _normalize_text(text).lower()
    if not lowered:
        return 0
    return sum(1 for variant in _keyword_variants(keyword) if variant.lower() in lowered)


def _score_candidate(title: str, price: float, link: str, keyword: str) -> float:
    keyword_hits = _keyword_score(title, keyword)
    if keyword_hits <= 0:
        return 0.0
    score = keyword_hits * 0.28
    if price > 0:
        score += 0.18
    if link:
        score += 0.14
    if price >= 10:
        score += 0.10
    lowered = title.lower()
    if "psa" in lowered:
        score += 0.08
    if any(alias in lowered for alias in ("宝可梦", "神奇宝贝", "卡", "卡牌")):
        score += 0.08
    return round(min(0.99, score), 4)


def _detect_login_page(provider: str, body_text: str) -> bool:
    text = _normalize_text(body_text)
    if not text:
        return False
    markers = {
        "pinduoduo": ("手机登录", "扫码登录", "发送验证码", "同意协议并登录"),
        "jd": ("登录", "验证码"),
    }.get(provider, ())
    return bool(markers) and all(marker in text for marker in markers[:2])


def _build_extract_expression(provider: str, limit: int) -> str:
    cfg = PROVIDER_CONFIG[provider]
    id_key = cfg["id_key"]
    title_key = cfg["title_key"]
    link_key = cfg["link_key"]
    if provider == "jd":
        href_filter = 'a[href*="item.jd.com/"]'
        id_regex = r"item\.jd\.com/(\d+)\.html"
        return f"""
(() => {{
  const maxItems = {max(1, int(limit)) * 12};
  const normalizeText = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
  const items = [];
  const anchors = Array.from(document.querySelectorAll('{href_filter}'));
  for (const anchor of anchors) {{
    const href = anchor.href || '';
    const idMatch = href.match(/{id_regex}/);
    const container = anchor.closest('li, div, article');
    items.push({{
      {json.dumps(id_key)}: idMatch ? idMatch[1] : '',
      {json.dumps(title_key)}: normalizeText(anchor.getAttribute('title') || anchor.textContent || container?.innerText || ''),
      {json.dumps(link_key)}: href,
      priceText: normalizeText(container?.innerText || ''),
      listed_at: new Date().toISOString(),
    }});
    if (items.length >= maxItems) break;
  }}
  return {{
    items,
    bodyText: String(document.body?.innerText || '').slice(0, 120000),
  }};
}})()
""".strip()
    return f"""
(() => {{
  const maxItems = {max(1, int(limit)) * 20};
  const normalizeText = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
  const parseGoodsId = (href) => {{
    const match = String(href || '').match(/goods_id=(\\d+)/);
    return match ? match[1] : '';
  }};
  const candidates = [];
  const blocks = Array.from(document.querySelectorAll('div, li, a'));
  for (const node of blocks) {{
    const text = normalizeText(node.innerText || '');
    if (!text || text.length < 12 || text.length > 260) continue;
    const href = node.closest('a')?.href || node.querySelector('a')?.href || '';
    const goodsId = parseGoodsId(href) || node.getAttribute('data-goods-id') || '';
    const className = normalizeText(node.className || '');
    candidates.push({{
      {json.dumps(id_key)}: goodsId,
      {json.dumps(title_key)}: text,
      {json.dumps(link_key)}: href,
      priceText: text,
      className,
      listed_at: new Date().toISOString(),
    }});
    if (candidates.length >= maxItems) break;
  }}
  return {{
    items: candidates,
    bodyText: String(document.body?.innerText || '').slice(0, 120000),
  }};
}})()
""".strip()


def _coerce_bridge_items(
    provider: str,
    raw_items: list[dict[str, Any]],
    body_text: str,
    keyword: str,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = PROVIDER_CONFIG[provider]
    id_key = str(cfg["id_key"])
    title_key = str(cfg["title_key"])
    link_key = str(cfg["link_key"])
    accepted: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in raw_items:
        title = _normalize_text(item.get(title_key))
        price = _extract_price_from_text(item.get("priceText") or item.get("price"))
        link = _normalize_text(item.get(link_key))
        listing_id = _normalize_text(item.get(id_key)) or (f"{title}:{price}" if title and price > 0 else "")
        score = _score_candidate(title, price, link, keyword)
        diagnostics.append(
            {
                "title": title[:120],
                "price": price,
                "link_present": bool(link),
                "keyword_score": _keyword_score(title, keyword),
                "score": score,
                "accepted": False,
                "source": "anchor",
            }
        )
        if score < 0.65 or not listing_id:
            continue
        if listing_id in seen:
            continue
        seen.add(listing_id)
        diagnostics[-1]["accepted"] = True
        accepted.append(
            {
                id_key: listing_id,
                title_key: title,
                "price": price,
                link_key: link,
                "listed_at": item.get("listed_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        if len(accepted) >= max(1, int(limit)):
            return accepted, diagnostics

    if accepted:
        return accepted, diagnostics

    lines = [_normalize_text(line) for line in re.split(r"\n+", str(body_text or "")) if _normalize_text(line)]
    for index, line in enumerate(lines):
        nearby = " ".join(lines[index : index + 4])
        price = _extract_price_from_text(nearby)
        score = _score_candidate(line, price, "", keyword)
        diagnostics.append(
            {
                "title": line[:120],
                "price": price,
                "link_present": False,
                "keyword_score": _keyword_score(line, keyword),
                "score": score,
                "accepted": False,
                "source": "body_line",
            }
        )
        if score < 0.75:
            continue
        listing_id = f"{line}:{price}"
        if listing_id in seen:
            continue
        seen.add(listing_id)
        diagnostics[-1]["accepted"] = True
        accepted.append(
            {
                id_key: listing_id,
                title_key: line,
                "price": price,
                link_key: "",
                "listed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        if len(accepted) >= max(1, int(limit)):
            break
    return accepted, diagnostics


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
        login_required = _detect_login_page(provider, body_text)
        filtered_items, diagnostics = _coerce_bridge_items(provider, raw_items, body_text, keyword, limit)
        confidence_score = round(
            min(0.98, max((item["score"] for item in diagnostics if item.get("accepted")), default=0.0)),
            4,
        ) if filtered_items else 0.0
        low_confidence = login_required or len(filtered_items) == 0

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
            "login_required": login_required,
            "warnings": (
                ["Browser page looks like a login screen. Keep the provider logged in and retry."]
                if login_required
                else ["No strongly keyword-matching items were found in the visible browser results."]
            ) if low_confidence else [],
            "diagnostics": diagnostics[:20],
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
