from __future__ import annotations

import ipaddress
import json
import os
import random
import threading
import time
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import urlparse

import requests

from ..config import settings


class ProxyRequiredError(RuntimeError):
    """Raised when strict proxy mode is enabled but no proxy is available."""


class BusinessBanError(RuntimeError):
    """Raised when upstream service returns business-level ban/limit response."""

    def __init__(self, *, code: str, message: str, context: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.context = context


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


class _ProxyRuntimeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bad_until: dict[str, float] = {}
        self._failure_count: dict[str, int] = {}
        self._last_selected_proxy = ""
        self._last_rotation_at = 0.0
        self._last_rotation_reason = ""

    def mark_selected(self, proxy_url: str) -> None:
        if not proxy_url:
            return
        with self._lock:
            self._last_selected_proxy = proxy_url

    def mark_bad(self, proxy_url: str, reason: str = "") -> dict[str, Any]:
        target = proxy_url.strip()
        if not target:
            return {"marked": False, "reason": "empty_proxy"}
        now = time.time()
        with self._lock:
            count = self._failure_count.get(target, 0) + 1
            self._failure_count[target] = count
            threshold = max(1, int(settings.proxy_max_failures))
            if count >= threshold:
                base_ttl = max(1.0, float(settings.proxy_bad_ttl_sec))
                jitter_span = max(0.0, float(settings.proxy_bad_ttl_jitter_sec))
                jitter = random.uniform(-jitter_span, jitter_span) if jitter_span > 0 else 0.0
                ttl_with_jitter = max(1.0, base_ttl + jitter)
                self._bad_until[target] = now + ttl_with_jitter
                self._last_rotation_at = now
                self._last_rotation_reason = reason or "proxy_marked_bad"
                # reset strike count once quarantined
                self._failure_count[target] = 0
                return {
                    "marked": True,
                    "proxy": target,
                    "quarantined_until": self._bad_until[target],
                    "reason": self._last_rotation_reason,
                    "quarantine_ttl_sec": round(ttl_with_jitter, 2),
                    "quarantine_jitter_sec": round(jitter, 2),
                }
            return {
                "marked": False,
                "proxy": target,
                "reason": "below_failure_threshold",
                "failures": count,
                "threshold": threshold,
            }

    def is_available(self, proxy_url: str) -> bool:
        target = proxy_url.strip()
        if not target:
            return False
        now = time.time()
        with self._lock:
            until = self._bad_until.get(target, 0.0)
            if not until:
                return True
            if until <= now:
                self._bad_until.pop(target, None)
                return True
            return False

    def current(self) -> str:
        with self._lock:
            return self._last_selected_proxy

    def status(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            active_bad = {
                proxy: round(max(0.0, until - now), 1)
                for proxy, until in self._bad_until.items()
                if until > now
            }
            return {
                "last_selected_proxy": self._last_selected_proxy,
                "last_rotation_at_unix": self._last_rotation_at,
                "last_rotation_reason": self._last_rotation_reason,
                "quarantined_proxies": active_bad,
                "max_failures": settings.proxy_max_failures,
                "bad_ttl_sec": settings.proxy_bad_ttl_sec,
                "bad_ttl_jitter_sec": settings.proxy_bad_ttl_jitter_sec,
            }

    def should_throttle_rotation(self) -> bool:
        with self._lock:
            if not self._last_rotation_at:
                return False
            return (time.time() - self._last_rotation_at) < max(
                0.0,
                float(settings.proxy_rotation_cooldown_sec),
            )


_PROXY_STATE = _ProxyRuntimeState()


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
        _PROXY_STATE.mark_selected(proxy_url_from_mapping(proxy) or "")
        return proxy
    proxy = _from_pool()
    if proxy:
        _PROXY_STATE.mark_selected(proxy_url_from_mapping(proxy) or "")
        return proxy
    proxy = _from_local()
    if proxy:
        _PROXY_STATE.mark_selected(proxy_url_from_mapping(proxy) or "")
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
        "runtime": _PROXY_STATE.status(),
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
    candidates = _parse_pool_proxies(resp.text)
    if not candidates:
        return None

    for ip, port in candidates:
        if not ip or not port:
            continue
        proxy = _normalize_proxy(f"{ip}:{port}")
        if not proxy:
            continue
        if _PROXY_STATE.is_available(proxy):
            return {"http": proxy, "https": proxy}

    # All candidates are quarantined. Return the first candidate as fallback in strict mode.
    ip, port = candidates[0]
    fallback = _normalize_proxy(f"{ip}:{port}")
    if not fallback:
        return None
    return {"http": fallback, "https": fallback}


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
    proxies = _parse_pool_proxies(raw_text)
    if not proxies:
        return "", ""
    return proxies[0]


def _parse_pool_proxies(raw_text: str) -> list[tuple[str, str]]:
    text = str(raw_text or "").strip()
    if not text:
        return []
    parsed = _try_parse_json_pool_payload(text)
    if parsed:
        return parsed

    parsed_lines: list[tuple[str, str]] = []
    for line in text.splitlines():
        host, port = _split_host_port(line.strip())
        if host and port:
            parsed_lines.append((host, port))
    return parsed_lines


def _try_parse_json_pool_payload(raw: str) -> list[tuple[str, str]]:
    try:
        payload = json.loads(raw)
    except Exception:
        return []

    def _extract_from_node(node: Any) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        if isinstance(node, list):
            for item in node:
                if isinstance(item, list) and len(item) >= 2:
                    ip = str(item[0]).strip()
                    port = str(item[1]).strip()
                    if ip and port:
                        out.append((ip, port))
                elif isinstance(item, dict):
                    ip = str(item.get("ip") or item.get("host") or "").strip()
                    port = str(item.get("port") or "").strip()
                    if ip and port:
                        out.append((ip, port))
                elif isinstance(item, str):
                    ip, port = _split_host_port(item)
                    if ip and port:
                        out.append((ip, port))
            return out
        if isinstance(node, dict):
            for key in ("data", "result", "items", "list"):
                if key in node:
                    out.extend(_extract_from_node(node.get(key)))
            if not out:
                ip = str(node.get("ip") or node.get("host") or "").strip()
                port = str(node.get("port") or "").strip()
                if ip and port:
                    out.append((ip, port))
            return out
        return out

    results = _extract_from_node(payload)
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for host, port in results:
        key = f"{host}:{port}"
        if key in seen:
            continue
        seen.add(key)
        unique.append((host, port))
    return unique


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


def mark_proxy_bad(proxy_url: str | None = None, reason: str = "") -> dict[str, Any]:
    selected = (proxy_url or "").strip() or _PROXY_STATE.current()
    return _PROXY_STATE.mark_bad(selected, reason=reason)


def rotate_proxy(*, reason: str = "", required: bool | None = None) -> dict[str, Any]:
    if _PROXY_STATE.should_throttle_rotation():
        return {
            "rotated": False,
            "reason": "rotation_cooldown",
            "runtime": _PROXY_STATE.status(),
        }
    current = _PROXY_STATE.current()
    if current:
        _PROXY_STATE.mark_bad(current, reason=reason or "rotate_proxy")
    new_mapping = resolve_proxy(required=required)
    return {
        "rotated": bool(new_mapping),
        "reason": reason,
        "new_proxy": proxy_url_from_mapping(new_mapping),
        "runtime": _PROXY_STATE.status(),
    }


_clear_proxy_env()
