from __future__ import annotations

import ipaddress
import json
import os
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import urlparse

import requests

from ..config import settings


class ProxyRequiredError(RuntimeError):
    """Raised when strict proxy mode is enabled but no proxy is available."""


_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


def _clear_proxy_env() -> None:
    if not settings.network_ignore_env_proxy:
        return
    for key in _PROXY_ENV_KEYS:
        os.environ.pop(key, None)


def request_get(url: str, **kwargs: Any) -> requests.Response:
    return _request("GET", url, **kwargs)


def request_post(url: str, **kwargs: Any) -> requests.Response:
    return _request("POST", url, **kwargs)


def resolve_proxy(required: bool | None = None) -> dict[str, str] | None:
    must_have_proxy = settings.network_force_proxy_only if required is None else bool(required)
    proxy = _from_forced()
    if proxy:
        return proxy
    proxy = _from_pool()
    if proxy:
        return proxy
    proxy = _from_local()
    if proxy:
        return proxy
    if must_have_proxy:
        raise ProxyRequiredError(
            "NETWORK_FORCE_PROXY_ONLY=true but no proxy available. "
            "Set NETWORK_FORCE_PROXY_URL or enable proxy pool / LOCAL_PROXY_URL."
        )
    return None


def resolve_proxy_for_url(url: str, required: bool | None = None) -> dict[str, str] | None:
    if _is_local_url(url):
        return None
    return resolve_proxy(required=required)


def proxy_url_from_mapping(proxies: dict[str, str] | None) -> str | None:
    if not proxies:
        return None
    value = str(proxies.get("https") or proxies.get("http") or "").strip()
    return value or None


def network_policy_status() -> dict[str, Any]:
    return {
        "ignore_env_proxy": settings.network_ignore_env_proxy,
        "force_proxy_only": settings.network_force_proxy_only,
        "forced_proxy_configured": bool(str(settings.network_force_proxy_url or "").strip()),
        "proxy_pool_enabled": settings.monitor_use_proxy_pool,
        "proxy_pool_api": settings.proxy_pool_api,
        "local_proxy_configured": bool(str(settings.local_proxy_url or "").strip()),
    }


def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
    _clear_proxy_env()
    with requests.Session() as session:
        session.trust_env = not settings.network_ignore_env_proxy
        return session.request(method=method.upper(), url=url, **kwargs)


def _from_forced() -> dict[str, str] | None:
    proxy = _normalize_proxy(settings.network_force_proxy_url)
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _from_pool() -> dict[str, str] | None:
    use_pool = settings.monitor_use_proxy_pool or settings.network_force_proxy_only
    if not use_pool:
        return None
    base_url = settings.proxy_pool_api
    if not str(base_url or "").strip():
        return None
    raw_params = parse_qs(settings.proxy_pool_params)
    params = {k: v[0] for k, v in raw_params.items()}
    try:
        resp = request_get(base_url, params=params, timeout=5)
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    ip, port = _parse_pool_proxy(resp.text)
    if not ip or not port:
        return None
    proxy = _normalize_proxy(f"{ip}:{port}")
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _from_local() -> dict[str, str] | None:
    proxy = _normalize_proxy(settings.local_proxy_url)
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _normalize_proxy(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"http://{text}"
    return text


def _parse_pool_proxy(raw_text: str) -> tuple[str, str]:
    text = str(raw_text or "").strip()
    if not text:
        return "", ""
    # JSON shape: [[ip, port], ...]
    try:
        payload = json.loads(text)
    except Exception:
        payload = None
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, list) and len(first) >= 2:
            return str(first[0]).strip(), str(first[1]).strip()
        if isinstance(first, str):
            return _split_host_port(first)
    if isinstance(payload, dict):
        for key in ("data", "result", "items", "list"):
            value = payload.get(key)
            if isinstance(value, list) and value:
                first = value[0]
                if isinstance(first, list) and len(first) >= 2:
                    return str(first[0]).strip(), str(first[1]).strip()
                if isinstance(first, dict):
                    ip = str(first.get("ip") or first.get("host") or "").strip()
                    port = str(first.get("port") or "").strip()
                    if ip and port:
                        return ip, port
                if isinstance(first, str):
                    return _split_host_port(first)

    # Plain text shape: "ip:port" in first line.
    first_line = text.splitlines()[0].strip()
    return _split_host_port(first_line)


def _split_host_port(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text or ":" not in text:
        return "", ""
    host, port = text.rsplit(":", 1)
    return host.strip(), port.strip()


def _is_local_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").strip()
    except Exception:
        return False
    return _is_local_host(host)


def _is_local_host(host: str) -> bool:
    text = (host or "").strip().lower()
    if not text:
        return False
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    if text in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return False
    return ip.is_loopback


_clear_proxy_env()
