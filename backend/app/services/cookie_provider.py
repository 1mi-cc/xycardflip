from __future__ import annotations

import time
from typing import Optional

import requests

from ..config import settings


class CookieProvider:
    """
    Retrieves Xianyu cookies either from env or a local cookie service.
    Caches the latest cookie string in memory with a TTL to avoid hammering
    the automation service.
    """

    def __init__(self) -> None:
        self._cached_cookie: str | None = settings.xianyu_cookie.strip() or None
        self._last_fetched: float = 0.0
        self._ttl: int = max(60, settings.xianyu_cookie_ttl_sec)
        self._last_error: str = ""

    @property
    def last_error(self) -> str:
        return self._last_error

    def get_cookie(self, force_refresh: bool = False) -> str | None:
        if self._cached_cookie and not force_refresh:
            if (time.time() - self._last_fetched) < self._ttl:
                return self._cached_cookie

        # If env provided, reuse even if TTL expired (no refresh endpoint needed)
        if settings.xianyu_cookie.strip() and not force_refresh:
            self._cached_cookie = settings.xianyu_cookie.strip()
            self._last_fetched = time.time()
            return self._cached_cookie

        if settings.xianyu_cookie_refresh_on_start and settings.xianyu_cookie_refresh_url:
            try:
                requests.post(settings.xianyu_cookie_refresh_url, timeout=8)
            except Exception:
                # ignore refresh failure, fallback to latest endpoint
                pass

        if not settings.xianyu_cookie_provider_url:
            self._last_error = "cookie provider url not set"
            return self._cached_cookie

        try:
            resp = requests.get(settings.xianyu_cookie_provider_url, timeout=8)
            if resp.status_code != 200:
                self._last_error = f"cookie provider status {resp.status_code}"
                return self._cached_cookie
            data = resp.json()
            cookie_str = str(data.get("cookie_string") or "").strip()
            if cookie_str:
                self._cached_cookie = cookie_str
                self._last_fetched = time.time()
                self._last_error = ""
                return self._cached_cookie
            self._last_error = "cookie_string missing in provider response"
            return self._cached_cookie
        except Exception as exc:
            self._last_error = str(exc)
            return self._cached_cookie
