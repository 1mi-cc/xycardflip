from __future__ import annotations

import json
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs

import requests

from ..config import settings
from ..repositories import insert_listings
from ..schemas import ListingIn
from .cookie_provider import CookieProvider
from .notifier import format_circuit_email, send_alert_email
from .xianyu_client import XianyuClient, XianyuHttpError

HEADERS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
]


class MarketMonitorService:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._is_running = False
        self._last_error = ""
        self._last_run_at = ""
        self._last_inserted = 0
        self._runs = 0
        self._circuit_open = False
        self._circuit_reason = ""
        self._circuit_open_at = ""
        self._consecutive_errors = 0
        self._consecutive_403 = 0
        self._error_count = 0
        self._xianyu = XianyuClient()
        self._cookie_provider = CookieProvider()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "is_running": self._is_running,
                "runs": self._runs,
                "last_run_at": self._last_run_at,
                "last_inserted": self._last_inserted,
                "last_error": self._last_error,
                "target_url": settings.monitor_target_url,
                "use_proxy_pool": settings.monitor_use_proxy_pool,
                "circuit_open": self._circuit_open,
                "circuit_reason": self._circuit_reason,
                "consecutive_errors": self._consecutive_errors,
                "consecutive_403": self._consecutive_403,
                "error_count": self._error_count,
                "keyword": settings.monitor_keyword,
                "max_price": settings.monitor_max_price,
                "cookie_error": self._cookie_provider.last_error if hasattr(self, "_cookie_provider") else "",
            }

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._is_running:
                return {"started": False, "reason": "already running"}
            if self._circuit_open and self._circuit_open_at:
                try:
                    opened_at = datetime.fromisoformat(self._circuit_open_at)
                    elapsed = (datetime.now(timezone.utc) - opened_at).total_seconds()
                except Exception:
                    elapsed = settings.monitor_circuit_cooldown_sec
                if elapsed < settings.monitor_circuit_cooldown_sec:
                    remaining = round(settings.monitor_circuit_cooldown_sec - elapsed, 1)
                    return {"started": False, "reason": f"circuit cooldown {remaining}s"}
            self._reset_circuit()
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="market-monitor")
            self._is_running = True
            self._thread.start()
            return {"started": True}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if not self._is_running:
                return {"stopped": False, "reason": "not running"}
            self._stop_event.set()
            thread = self._thread
        if thread:
            thread.join(timeout=5)
        with self._lock:
            self._is_running = False
        return {"stopped": True}

    def run_once(self) -> dict[str, Any]:
        if self._circuit_open:
            return {
                "fetched": 0,
                "inserted": 0,
                "circuit_open": True,
                "reason": self._circuit_reason,
            }
        items = self._fetch_market_data()
        inserted = self._save_items(items)
        with self._lock:
            self._runs += 1
            self._last_inserted = inserted
            self._last_run_at = datetime.now(timezone.utc).isoformat()
            self._last_error = ""
            self._consecutive_errors = 0
            self._consecutive_403 = 0
        return {"fetched": len(items), "inserted": inserted}

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
                with self._lock:
                    self._last_error = ""
            except Exception as exc:  # pragma: no cover
                with self._lock:
                    self._last_error = str(exc)
                # circuit breaker check will be done in _fetch_market_data
                if self._circuit_open:
                    break

            if self._circuit_open:
                break

            sleep_time = self._compute_delay_sec()

            if self._stop_event.wait(timeout=sleep_time):
                break

        with self._lock:
            self._is_running = False

    def _fetch_market_data(self) -> list[dict[str, Any]]:
        try:
            if settings.monitor_provider.lower() == "xianyu":
                items: list[dict[str, Any]] = []
                pages = max(1, min(10, settings.monitor_pages))
                proxies = self._get_proxies()
                cookie = self._cookie_provider.get_cookie()
                for p in range(1, pages + 1):
                    items.extend(self._xianyu.fetch(page=p, proxies=proxies, cookie_override=cookie))
                return items
            return self._fetch_generic()
        except XianyuHttpError as exc:
            self._register_error(exc, is_403=exc.status == 403)
            raise
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            self._register_error(exc, is_403=status == 403)
            raise
        except Exception as exc:
            self._register_error(exc, is_403=False)
            raise

    def _fetch_generic(self) -> list[dict[str, Any]]:
        headers = {
            "User-Agent": random.choice(HEADERS_LIST),
            "Accept": "application/json",
        }
        proxies = self._get_proxies()
        response = requests.get(
            settings.monitor_target_url,
            headers=headers,
            timeout=settings.monitor_timeout_sec,
            proxies=proxies,
        )
        if response.status_code == 403:
            self._register_error(RuntimeError("generic 403"), is_403=True)
            raise RuntimeError("target status code: 403")
        if response.status_code != 200:
            self._register_error(RuntimeError(f"status {response.status_code}"), is_403=False)
            raise RuntimeError(f"target status code: {response.status_code}")

        data = response.json()
        if isinstance(data, dict):
            items = data.get("items", [])
            return items if isinstance(items, list) else []
        if isinstance(data, list):
            return data
        return []

    def _get_proxies(self) -> dict[str, str] | None:
        if not settings.monitor_use_proxy_pool:
            return None

        base_url = settings.proxy_pool_api
        raw_params = parse_qs(settings.proxy_pool_params)
        params = {k: v[0] for k, v in raw_params.items()}
        resp = requests.get(base_url, params=params, timeout=5)
        if resp.status_code != 200:
            return None

        ip_ports = json.loads(resp.text)
        if not isinstance(ip_ports, list) or not ip_ports:
            return None
        best = ip_ports[0]
        if not isinstance(best, list) or len(best) < 2:
            return None

        ip = str(best[0]).strip()
        port = str(best[1]).strip()
        proxy = f"http://{ip}:{port}"
        return {"http": proxy, "https": proxy}

    def _save_items(self, items: list[dict[str, Any]]) -> int:
        rows: list[ListingIn] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            price_raw = item.get("price", 0)
            try:
                price = float(price_raw)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            if price > settings.monitor_max_price:
                continue

            title = str(item.get("name") or item.get("title") or "").strip()
            if not title:
                continue
            listing_id = str(item.get("id") or item.get("listing_id") or "").strip() or None
            seller_id = str(item.get("seller_id") or "").strip() or None
            rows.append(
                ListingIn(
                    source="xianyu_monitor" if settings.monitor_provider.lower() == "xianyu" else "market_monitor",
                    listing_id=listing_id,
                    seller_id=seller_id,
                    title=title,
                    description=str(item.get("description") or ""),
                    list_price=price,
                    listed_at=datetime.now(timezone.utc),
                    status="open",
                    raw=item,
                )
            )

        if not rows:
            return 0
        return insert_listings(rows)

    def _register_error(self, exc: Exception, is_403: bool = False) -> None:
        with self._lock:
            self._consecutive_errors += 1
            self._error_count += 1
            if is_403:
                self._consecutive_403 += 1
            else:
                self._consecutive_403 = 0

            threshold_hit = (
                self._consecutive_errors >= settings.monitor_circuit_max_errors
                or self._consecutive_403 >= settings.monitor_circuit_403_threshold
            )
            if threshold_hit and not self._circuit_open:
                reason = f"circuit open after errors={self._consecutive_errors}, 403={self._consecutive_403}"
                self._open_circuit(reason)
            self._last_error = str(exc)

    def _open_circuit(self, reason: str) -> None:
        self._circuit_open = True
        self._circuit_reason = reason
        self._circuit_open_at = datetime.now(timezone.utc).isoformat()
        self._stop_event.set()
        print(f"[market_monitor] CIRCUIT OPEN: {reason}")
        subject, body = format_circuit_email(
            reason=reason,
            keyword=settings.monitor_keyword,
            last_error=self._last_error,
            consecutive_errors=self._consecutive_errors,
            consecutive_403=self._consecutive_403,
        )
        send_alert_email(subject, body)

    def _reset_circuit(self) -> None:
        self._circuit_open = False
        self._circuit_reason = ""
        self._circuit_open_at = ""
        self._consecutive_errors = 0
        self._consecutive_403 = 0
        self._error_count = 0

    def _compute_delay_sec(self) -> float:
        now_local = datetime.now()
        hour = now_local.hour
        if 8 <= hour < 17:
            return random.triangular(
                settings.monitor_day_delay_min,
                settings.monitor_day_delay_max,
                settings.monitor_day_delay_min + 2,
            )
        if 17 <= hour < 24:
            return random.triangular(
                settings.monitor_peak_delay_min,
                settings.monitor_peak_delay_max,
                settings.monitor_peak_delay_min + 1,
            )
        return random.triangular(
            settings.monitor_night_delay_min,
            settings.monitor_night_delay_max,
            settings.monitor_night_delay_min + 3,
        )


monitor_service = MarketMonitorService()
