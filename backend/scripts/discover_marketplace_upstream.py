from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote


PROVIDER_CONFIG = {
    "jd": {
        "start_url": "https://www.jd.com/",
        "default_keyword": "Pokemon Card PSA 10",
        "url_keywords": ("jd.com", "3.cn", "api.m.jd.com", "search"),
        "name_keywords": ("search", "goods", "sku", "query"),
        "body_keywords": ("goodslist", "skuid", "skuname", "wareid", "price"),
        "port": 9222,
    },
    "pinduoduo": {
        "start_url": "https://mobile.yangkeduo.com/",
        "default_keyword": "Pokemon Card PSA 10",
        "url_keywords": ("pinduoduo.com", "yangkeduo.com", "search", "goods"),
        "name_keywords": ("search", "goods", "list"),
        "body_keywords": ("goods_list", "goods_name", "goods_id", "min_group_price", "price"),
        "port": 9222,
    },
}


def _edge_executable() -> str:
    candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise SystemExit("Edge executable not found.")


def _load_requests_modules():
    try:
        import requests  # type: ignore
        import websocket  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Missing dependency for discovery tool: {exc}") from exc
    return requests, websocket


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover candidate marketplace JSON upstream URLs via Edge CDP.",
    )
    parser.add_argument("--provider", choices=sorted(PROVIDER_CONFIG.keys()), required=True)
    parser.add_argument("--watch-seconds", type=int, default=25)
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--remote-debug-port", type=int, default=9222)
    parser.add_argument("--reuse-browser", action="store_true")
    parser.add_argument("--keyword", default="")
    return parser


def _inspect_response_body(body_text: str, provider_cfg: dict[str, Any]) -> tuple[int, list[str]]:
    lowered = str(body_text or "").lower()
    matches = sorted({keyword for keyword in provider_cfg.get("body_keywords", ()) if keyword in lowered})
    return (len(matches), matches)


def _score_candidate(
    url: str,
    method: str,
    content_type: str,
    provider_cfg: dict[str, Any],
    *,
    body_score: int,
) -> tuple[int, int, int, int]:
    lowered_url = str(url or "").lower()
    lowered_type = str(content_type or "").lower()
    url_hits = sum(1 for keyword in provider_cfg["url_keywords"] if keyword in lowered_url)
    type_hit = 1 if "json" in lowered_type else 0
    method_hit = 1 if str(method or "").upper() in {"GET", "POST"} else 0
    return (body_score, type_hit, url_hits, method_hit)


def _build_navigation_url(provider: str, keyword: str, provider_cfg: dict[str, Any]) -> str:
    text = str(keyword or provider_cfg.get("default_keyword") or "").strip()
    if not text:
        return str(provider_cfg["start_url"])
    encoded = quote(text, safe="")
    if provider == "jd":
        return f"https://search.jd.com/Search?keyword={encoded}"
    if provider == "pinduoduo":
        return f"https://mobile.yangkeduo.com/search_result.html?search_key={encoded}"
    return str(provider_cfg["start_url"])


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    provider_cfg = PROVIDER_CONFIG[args.provider]
    requests, websocket = _load_requests_modules()
    navigation_url = _build_navigation_url(args.provider, args.keyword, provider_cfg)

    edge_bin = _edge_executable()
    user_data = Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
    proc = None
    if not args.reuse_browser:
        proc = subprocess.Popen(
            [
                edge_bin,
                f"--remote-debugging-port={int(args.remote_debug_port)}",
                "--remote-allow-origins=*",
                "--user-data-dir=" + str(user_data),
                "--profile-directory=Default",
                "--no-first-run",
                "--no-default-browser-check",
                navigation_url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    ws = None
    try:
        version = None
        for _ in range(40):
            try:
                version = requests.get(
                    f"http://127.0.0.1:{int(args.remote_debug_port)}/json/version",
                    timeout=1,
                ).json()
                break
            except Exception:
                time.sleep(0.5)
        if not version:
            raise SystemExit("Failed to connect to Edge remote debugging endpoint.")

        pages = requests.get(
            f"http://127.0.0.1:{int(args.remote_debug_port)}/json/list",
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
            raise SystemExit("No page websocket debugger URL found.")

        ws = websocket.create_connection(
            ws_url,
            timeout=8,
            origin=f"http://127.0.0.1:{int(args.remote_debug_port)}",
        )
        message_id = 1

        def send(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            nonlocal message_id
            current_id = message_id
            message_id += 1
            ws.send(json.dumps({"id": current_id, "method": method, "params": params or {}}))
            while True:
                payload = json.loads(ws.recv())
                if payload.get("id") == current_id:
                    return payload

        send("Network.enable")
        send("Page.enable")
        send("Page.navigate", {"url": navigation_url})
        deadline = time.time() + max(5, int(args.watch_seconds))
        candidates: dict[str, dict[str, Any]] = {}

        while time.time() < deadline:
            try:
                payload = json.loads(ws.recv())
            except Exception:
                continue
            if payload.get("method") != "Network.responseReceived":
                continue
            params = payload.get("params") or {}
            response = params.get("response") or {}
            request_id = str(params.get("requestId") or "")
            url = str(response.get("url") or "").strip()
            mime_type = str(response.get("mimeType") or "").strip()
            if not url or not any(keyword in url.lower() for keyword in provider_cfg["url_keywords"]):
                continue
            if "json" not in mime_type.lower():
                continue

            method = "GET"
            try:
                extra = send("Network.getRequestPostData", {"requestId": request_id})
                post_data = str((extra.get("result") or {}).get("postData") or "")
                if post_data:
                    method = "POST"
            except Exception:
                post_data = ""

            response_body = ""
            try:
                extra_body = send("Network.getResponseBody", {"requestId": request_id})
                response_body = str((extra_body.get("result") or {}).get("body") or "")
            except Exception:
                response_body = ""

            body_score, body_indicators = _inspect_response_body(response_body, provider_cfg)

            score = _score_candidate(
                url,
                method,
                mime_type,
                provider_cfg,
                body_score=body_score,
            )
            current = candidates.get(url)
            item = {
                "url": url,
                "method": method,
                "mime_type": mime_type,
                "score": score,
                "body_score": body_score,
                "body_indicators": body_indicators,
                "post_data_present": bool(post_data),
                "post_data_sample": (post_data[:500] if post_data else ""),
                "status": int(response.get("status") or 0),
            }
            if current is None or tuple(item["score"]) > tuple(current["score"]):
                candidates[url] = item

        ranked = sorted(
            candidates.values(),
            key=lambda item: tuple(item["score"]),
            reverse=True,
        )[: max(1, int(args.max_results))]
        print(
            json.dumps(
                {
                    "provider": args.provider,
                    "navigation_url": navigation_url,
                    "keyword": str(args.keyword or provider_cfg.get("default_keyword") or ""),
                    "watch_seconds": int(args.watch_seconds),
                    "candidate_count": len(ranked),
                    "items": ranked,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        try:
            if ws is not None:
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


if __name__ == "__main__":
    raise SystemExit(main())
