from __future__ import annotations

import argparse
import json
import subprocess
import time
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import quote
from urllib.parse import urlparse
import re


PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "jd": {
        "default_port": 8775,
        "default_keyword": "Pokemon Card PSA 10",
        "start_url": "https://search.jd.com/Search?keyword={keyword}",
        "domain_keywords": ("jd.com", "3.cn"),
        "root_key": "jd_union_open_goods_query_response",
        "result_path": ("queryResult", "goodsList"),
    },
    "pinduoduo": {
        "default_port": 8776,
        "default_keyword": "Pokemon Card PSA 10",
        "start_url": "https://mobile.yangkeduo.com/search_result.html?search_key={keyword}",
        "domain_keywords": ("yangkeduo.com", "pinduoduo.com"),
        "root_key": "goods_search_response",
        "result_path": ("goods_list",),
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
    variants: list[str] = []
    for token in tokens:
        variants.append(token)
        if token == "pokemon":
            variants.append("宝可梦")
        elif token == "card":
            variants.extend(["卡", "卡牌", "收藏卡"])
        elif token == "psa":
            variants.append("psa")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in variants:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def _title_matches_keyword(title: str, keyword: str) -> bool:
    text = str(title or "").strip().lower()
    if not text:
        return False
    variants = _keyword_variants(keyword)
    if not variants:
        return True
    hits = sum(1 for variant in variants if variant.lower() in text)
    return hits >= 2 or ("宝可梦" in text and "psa" in text)


def _build_extract_expression(provider: str, keyword: str, limit: int) -> str:
    keyword_tokens = [
        token.lower()
        for token in str(keyword or "").strip().split()
        if token.strip() and not token.strip().isdigit()
    ][:8]
    keyword_tokens_json = json.dumps(keyword_tokens, ensure_ascii=True)
    if provider == "jd":
        return f"""
(() => {{
  const maxItems = {max(1, int(limit))};
  const keywordTokens = {keyword_tokens_json};
  const keywordVariants = keywordTokens.flatMap((token) => {{
    const variants = [token];
    if (token === 'pokemon') variants.push('宝可梦');
    if (token === 'card') variants.push('卡', '卡牌', '收藏卡');
    if (token === 'psa') variants.push('psa');
    return variants;
  }});
  const parsePrice = (text) => {{
    const cleaned = String(text || '').replace(/,/g, '');
    const match = cleaned.match(/[\\u00A5\\uFFE5]\\s*([0-9]+(?:\\.[0-9]+)?)/) || cleaned.match(/(^|\\s)([0-9]+(?:\\.[0-9]+)?)(\\s|$)/);
    if (!match) return null;
    return Number(match[1] || match[2] || 0);
  }};
  const normalizeText = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
  const splitLines = (value) => String(value || '').split(/\\n+/).map(part => normalizeText(part)).filter(Boolean);
  const keywordHit = (value) => {{
    const lowered = String(value || '').toLowerCase();
    return !keywordVariants.length || keywordVariants.some(token => lowered.includes(String(token).toLowerCase()));
  }};
  const titleLike = (value) => {{
    const text = normalizeText(value);
    if (!text || text.length < 6 || text.length > 120) return false;
    if (/[\\u00A5\\uFFE5]\\s*\\d/.test(text)) return false;
    if (/^(商品|搜索|全部商品|配送至|筛选|综合|销量|价格|到手价|包邮|好评|看过|京东首页|网站导航)/.test(text)) return false;
    return keywordHit(text);
  }};
  const seen = new Set();
  const results = [];
  const anchors = Array.from(document.querySelectorAll('a[href*="item.jd.com/"]'));
  for (const anchor of anchors) {{
    const href = anchor.href || '';
    const skuMatch = href.match(/item\\.jd\\.com\\/(\\d+)\\.html/);
    if (!skuMatch) continue;
    const skuId = skuMatch[1];
    if (seen.has(skuId)) continue;
    const container = anchor.closest('li, div');
    const title = normalizeText(anchor.getAttribute('title') || anchor.textContent || container?.querySelector('em')?.textContent || '');
    if (!title || title.length < 4) continue;
    if (!keywordHit(title)) continue;
    const containerText = normalizeText(container?.innerText || '');
    const price = parsePrice(containerText);
    if (!price || !Number.isFinite(price) || price <= 0) continue;
    seen.add(skuId);
    results.push({{
      skuId,
      skuName: title,
      owner: '',
      price,
      materialUrl: href,
      listed_at: new Date().toISOString(),
    }});
    if (results.length >= maxItems) break;
  }}
  if (results.length < maxItems) {{
    const lines = splitLines(document.body?.innerText || '');
    for (let i = 0; i < lines.length; i += 1) {{
      const line = lines[i];
      if (!keywordHit(line)) continue;
      const nearby = [line, lines[i + 1] || '', lines[i + 2] || ''].join(' ');
      const price = parsePrice(nearby);
      if (!price || !Number.isFinite(price) || price <= 0) continue;
      const title = line;
      const skuId = `${{title}}:${{price}}`;
      if (seen.has(skuId)) continue;
      seen.add(skuId);
      results.push({{
        skuId,
        skuName: title,
        owner: '',
        price,
        materialUrl: '',
        listed_at: new Date().toISOString(),
      }});
      if (results.length >= maxItems) break;
    }}
  }}
  if (results.length < maxItems) {{
    const blocks = Array.from(document.querySelectorAll('a, li, div')).map(node => {{
      const text = normalizeText(node.innerText || '');
      const href = node.closest('a')?.href || node.querySelector('a')?.href || '';
      return {{ text, href }};
    }}).filter(block => block.text && block.text.length >= 12 && block.text.length <= 220 && /[\\u00A5\\uFFE5]\\s*\\d/.test(block.text) && keywordHit(block.text));
    for (const block of blocks) {{
      const price = parsePrice(block.text);
      if (!price || !Number.isFinite(price) || price <= 0) continue;
      const lines = splitLines(block.text);
      const title = lines.find(titleLike) || lines[0] || '';
      if (!titleLike(title)) continue;
      const skuMatch = String(block.href || '').match(/item\\.jd\\.com\\/(\\d+)\\.html/);
      const skuId = skuMatch ? skuMatch[1] : `${{title}}:${{price}}`;
      if (seen.has(skuId)) continue;
      seen.add(skuId);
      results.push({{
        skuId,
        skuName: title,
        owner: '',
        price,
        materialUrl: block.href || '',
        listed_at: new Date().toISOString(),
      }});
      if (results.length >= maxItems) break;
    }}
  }}
  return results;
}})()
""".strip()
    return f"""
(() => {{
  const maxItems = {max(1, int(limit))};
  const keywordTokens = {keyword_tokens_json};
  const keywordVariants = keywordTokens.flatMap((token) => {{
    const variants = [token];
    if (token === 'pokemon') variants.push('宝可梦');
    if (token === 'card') variants.push('卡', '卡牌', '收藏卡');
    if (token === 'psa') variants.push('psa');
    return variants;
  }});
  const parsePrice = (text) => {{
    const cleaned = String(text || '').replace(/,/g, '');
    const match = cleaned.match(/[\\u00A5\\uFFE5]\\s*([0-9]+(?:\\.[0-9]+)?)/) || cleaned.match(/(^|\\s)([0-9]+(?:\\.[0-9]+)?)(\\s|$)/);
    if (!match) return null;
    return Number(match[1] || match[2] || 0);
  }};
  const normalizeText = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
  const splitLines = (value) => String(value || '').split(/\\n+/).map(part => normalizeText(part)).filter(Boolean);
  const keywordHit = (value) => {{
    const lowered = String(value || '').toLowerCase();
    return !keywordVariants.length || keywordVariants.some(token => lowered.includes(String(token).toLowerCase()));
  }};
  const titleLike = (value) => {{
    const text = normalizeText(value);
    if (!text || text.length < 6 || text.length > 120) return false;
    if (/[\\u00A5\\uFFE5]\\s*\\d/.test(text)) return false;
    if (/^(登录|手机登录|扫码登录|发送验证码|同意协议|返回|搜索|综合|销量|价格|筛选)/.test(text)) return false;
    return keywordHit(text);
  }};
  const seen = new Set();
  const results = [];
  const anchors = Array.from(document.querySelectorAll('a[href*="goods"], a[href*="search_result"]'));
  for (const anchor of anchors) {{
    const href = anchor.href || '';
    const goodsMatch = href.match(/goods_id=(\\d+)/) || href.match(/goods_id%22%3A(\\d+)/);
    const container = anchor.closest('div, li, a');
    const fallbackText = normalizeText(container?.innerText || anchor.textContent || '');
    const title = normalizeText(anchor.getAttribute('title') || fallbackText);
    if (!title || title.length < 4) continue;
    const price = parsePrice(fallbackText);
    if (!price || !Number.isFinite(price) || price <= 0) continue;
    const goodsId = goodsMatch ? goodsMatch[1] : (title + ':' + price);
    if (seen.has(goodsId)) continue;
    seen.add(goodsId);
    results.push({{
      goods_id: goodsId,
      goods_name: title,
      mall_id: '',
      price,
      goods_link: href,
      listed_at: new Date().toISOString(),
    }});
    if (results.length >= maxItems) break;
  }}
  if (results.length < maxItems) {{
    const lines = splitLines(document.body?.innerText || '');
    for (let i = 0; i < lines.length; i += 1) {{
      const line = lines[i];
      if (!keywordHit(line)) continue;
      const nearby = [line, lines[i + 1] || '', lines[i + 2] || ''].join(' ');
      const price = parsePrice(nearby);
      if (!price || !Number.isFinite(price) || price <= 0) continue;
      const goodsId = `${{line}}:${{price}}`;
      if (seen.has(goodsId)) continue;
      seen.add(goodsId);
      results.push({{
        goods_id: goodsId,
        goods_name: line,
        mall_id: '',
        price,
        goods_link: '',
        listed_at: new Date().toISOString(),
      }});
      if (results.length >= maxItems) break;
    }}
  }}
  if (results.length < maxItems) {{
    const blocks = Array.from(document.querySelectorAll('a, li, div')).map(node => {{
      const text = normalizeText(node.innerText || '');
      const href = node.closest('a')?.href || node.querySelector('a')?.href || '';
      return {{ text, href }};
    }}).filter(block => block.text && block.text.length >= 12 && block.text.length <= 220 && /[\\u00A5\\uFFE5]\\s*\\d/.test(block.text) && keywordHit(block.text));
    for (const block of blocks) {{
      const price = parsePrice(block.text);
      if (!price || !Number.isFinite(price) || price <= 0) continue;
      const lines = splitLines(block.text);
      const title = lines.find(titleLike) || lines[0] || '';
      if (!titleLike(title)) continue;
      const goodsMatch = String(block.href || '').match(/goods_id=(\\d+)/);
      const goodsId = goodsMatch ? goodsMatch[1] : `${{title}}:${{price}}`;
      if (seen.has(goodsId)) continue;
      seen.add(goodsId);
      results.push({{
        goods_id: goodsId,
        goods_name: title,
        mall_id: '',
        price,
        goods_link: block.href || '',
        listed_at: new Date().toISOString(),
      }});
      if (results.length >= maxItems) break;
    }}
  }}
  return results;
}})()
""".strip()


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


def _capture_snapshot(provider: str, *, keyword: str, page: int, limit: int, remote_debug_port: int, page_wait_ms: int, reuse_browser: bool) -> dict[str, Any]:
    search_url = _build_search_url(provider, keyword, page)
    _requests, _websocket, ws, proc = _connect_browser(provider, remote_debug_port, reuse_browser, search_url)
    try:
        _send(ws, "Network.enable")
        _send(ws, "Page.enable")
        _send(ws, "Page.navigate", {"url": search_url})
        time.sleep(max(1.0, float(page_wait_ms) / 1000.0))
        expression = _build_extract_expression(provider, keyword, limit)
        result = _send(
            ws,
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        value = ((result.get("result") or {}).get("result") or {}).get("value")
        items = value if isinstance(value, list) else []
        filtered_items = [
            item
            for item in items
            if _title_matches_keyword(
                str(item.get("skuName") or item.get("goods_name") or item.get("title") or ""),
                keyword,
            )
        ]
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
            "raw_item_count": len(items),
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
