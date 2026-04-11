from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import dotenv_values


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_OVERRIDE = os.getenv("COOKIE_ENV_PATH", "").strip() or os.getenv("DOTENV_PATH", "").strip()
ENV_PATH = Path(ENV_OVERRIDE).expanduser() if ENV_OVERRIDE else ROOT_DIR / ".env"


PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "jd": {
        "env_key": "JD_COOKIE",
        "default_user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
    },
    "pinduoduo": {
        "env_key": "PINDUODUO_COOKIE",
        "default_user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
    },
}


def _load_cookie(env_key: str) -> str:
    if not ENV_PATH.exists():
        return ""
    try:
        env_values = dotenv_values(ENV_PATH)
    except Exception:
        return ""
    return str(env_values.get(env_key) or "").strip()


def _json_or_empty(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON payload: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("JSON payload must decode to an object.")
    return value


def _coerce_json_response(response: requests.Response) -> tuple[str, Any]:
    response.raise_for_status()
    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"upstream response is not valid JSON: {exc}") from exc
    return "application/json; charset=utf-8", payload


def _build_parser(provider: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Run a local {provider} cookie snapshot bridge on 127.0.0.1",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765 if provider == "jd" else 8766)
    parser.add_argument("--source-url", required=True, help="Upstream JSON endpoint that requires browser cookie.")
    parser.add_argument("--upstream-method", choices=("GET", "POST"), default="GET")
    parser.add_argument("--params-json", default="", help="Optional query params JSON object.")
    parser.add_argument("--body-json", default="", help="Optional POST body JSON object.")
    parser.add_argument("--timeout-sec", type=float, default=15.0)
    return parser


def _build_handler(
    *,
    provider: str,
    env_key: str,
    source_url: str,
    upstream_method: str,
    params: dict[str, Any],
    body: dict[str, Any],
    timeout_sec: float,
    default_user_agent: str,
):
    class SnapshotBridgeHandler(BaseHTTPRequestHandler):
        server_version = "MarketplaceSnapshotBridge/1.0"

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
                cookie = _load_cookie(env_key)
                self._send_json(
                    200,
                    {
                        "provider": provider,
                        "env_key": env_key,
                        "cookie_present": bool(cookie),
                        "source_url": source_url,
                        "upstream_method": upstream_method,
                        "risk_level": "high-risk-unstable",
                        "mode": "cookie-bridge",
                    },
                )
                return

            if parsed.path != "/snapshot":
                self._send_json(404, {"detail": "not found"})
                return

            cookie = _load_cookie(env_key)
            if not cookie:
                self._send_json(
                    503,
                    {
                        "detail": f"{env_key} is missing in local .env",
                        "provider": provider,
                    },
                )
                return

            headers = {
                "Cookie": cookie,
                "Accept": "application/json,text/plain,*/*",
                "User-Agent": default_user_agent,
            }

            try:
                if upstream_method == "POST":
                    response = requests.post(
                        source_url,
                        params=params or None,
                        json=body or None,
                        headers=headers,
                        timeout=timeout_sec,
                    )
                else:
                    response = requests.get(
                        source_url,
                        params=params or None,
                        headers=headers,
                        timeout=timeout_sec,
                    )
                _content_type, payload = _coerce_json_response(response)
            except Exception as exc:
                self._send_json(
                    502,
                    {
                        "detail": str(exc),
                        "provider": provider,
                        "risk_level": "high-risk-unstable",
                    },
                )
                return

            self._send_json(
                200,
                {
                    "provider": provider,
                    "captured_at": __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                    "payload": payload,
                },
            )

    return SnapshotBridgeHandler


def main(provider: str, argv: list[str] | None = None) -> int:
    provider_key = str(provider or "").strip().lower()
    if provider_key not in PROVIDER_CONFIG:
        raise SystemExit(f"unsupported provider: {provider}")
    config = PROVIDER_CONFIG[provider_key]
    parser = _build_parser(provider_key)
    args = parser.parse_args(argv)

    params = _json_or_empty(args.params_json)
    body = _json_or_empty(args.body_json)

    handler = _build_handler(
        provider=provider_key,
        env_key=config["env_key"],
        source_url=args.source_url,
        upstream_method=str(args.upstream_method or "GET").upper(),
        params=params,
        body=body,
        timeout_sec=float(args.timeout_sec or 15.0),
        default_user_agent=config["default_user_agent"],
    )
    server = ThreadingHTTPServer((args.host, int(args.port)), handler)
    print(
        json.dumps(
            {
                "provider": provider_key,
                "listen": f"http://{args.host}:{args.port}",
                "snapshot_url": f"http://{args.host}:{args.port}/snapshot",
                "health_url": f"http://{args.host}:{args.port}/health",
                "risk_level": "high-risk-unstable",
                "mode": "cookie-bridge",
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
    if len(sys.argv) < 2:
        raise SystemExit("Use provider wrapper script instead of running snapshot_bridge_common.py directly.")
    raise SystemExit(main(sys.argv[1], sys.argv[2:]))
