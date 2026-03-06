from __future__ import annotations

import asyncio
from collections import deque
import random
import threading
from datetime import datetime, timezone
from typing import Any
import requests

from ..config import settings
from ..repositories import insert_listings
from ..schemas import ListingIn
from .cookie_provider import CookieProvider
from .notifier import format_circuit_email, send_alert_email
from .opportunity_scan import scan_open_listings
from .proxy_resolver import mark_proxy_bad
from .proxy_resolver import proxy_url_from_mapping
from .proxy_resolver import rotate_proxy
from .proxy_resolver import request_get
from .proxy_resolver import resolve_proxy
from .proxy_resolver import resolve_proxy_for_url
from .xianyu_client import XianyuClient, XianyuHttpError


def _should_refresh_cookie(exc: XianyuHttpError) -> bool:
    text = (exc.body_excerpt or str(exc)).lower()
    if exc.status in {401, 403}:
        return True
    return any(key in text for key in ("token", "session", "auth", "login"))


class MarketMonitorService:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._is_running = False
        self._last_error = ""
        self._last_run_at = ""
        self._last_inserted = 0
        self._last_scan: dict[str, Any] = {}
        self._runs = 0
        self._circuit_open = False
        self._circuit_reason = ""
        self._circuit_open_at = ""
        self._consecutive_errors = 0
        self._consecutive_403 = 0
        self._error_count = 0
        self._health_window: deque[int] = deque(
            maxlen=max(5, int(settings.monitor_health_window_size))
        )
        self._health_last_rate = 1.0
        self._health_guard_triggered = False
        self._health_guard_reason = ""
        self._last_proxy = ""
        self._xianyu = XianyuClient()
        self._cookie_provider = CookieProvider()

    def status(self) -> dict[str, Any]:
        monitor_keywords = self._resolved_monitor_keywords()
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
                "keyword": monitor_keywords[0] if monitor_keywords else settings.monitor_keyword,
                "keywords": monitor_keywords,
                "max_price": settings.monitor_max_price,
                "auto_scan_after_ingest": settings.monitor_auto_scan_after_ingest,
                "auto_scan_limit": settings.monitor_auto_scan_limit,
                "health": {
                    "window_size": int(settings.monitor_health_window_size),
                    "min_samples": int(settings.monitor_health_min_samples),
                    "min_success_rate": float(settings.monitor_health_min_success_rate),
                    "samples": len(self._health_window),
                    "success_rate": round(self._health_last_rate, 4),
                    "guard_triggered": self._health_guard_triggered,
                    "guard_reason": self._health_guard_reason,
                },
                "last_proxy": self._last_proxy,
                "last_scan": self._last_scan,
                "cookie_error": self._cookie_provider.last_error if hasattr(self, "_cookie_provider") else "",
                "cookie_meta": self._cookie_provider.cookie_meta() if hasattr(self, "_cookie_provider") else {},
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
        scan_result: dict[str, Any] | None = None
        scan_error = ""
        if settings.monitor_auto_scan_after_ingest:
            try:
                scan_limit = max(1, min(500, int(settings.monitor_auto_scan_limit)))
                scan_result = asyncio.run(scan_open_listings(limit=scan_limit))
            except Exception as exc:
                scan_error = str(exc)

        with self._lock:
            self._runs += 1
            self._last_inserted = inserted
            self._last_scan = scan_result or {}
            self._last_run_at = datetime.now(timezone.utc).isoformat()
            self._last_error = scan_error
            self._consecutive_errors = 0
            self._consecutive_403 = 0
        self._record_health(success=True, reason=f"fetched={len(items)}, inserted={inserted}")
        return {
            "fetched": len(items),
            "inserted": inserted,
            "scan": scan_result or {},
            "scan_error": scan_error,
        }

    def refresh_cookie_local(self, kill_browsers: bool = True) -> dict[str, Any]:
        result = self._cookie_provider.refresh_cookie_local(kill_browsers=kill_browsers)
        if result.get("success"):
            with self._lock:
                self._reset_circuit()
                self._last_error = ""
        else:
            with self._lock:
                self._last_error = str(result.get("error") or "cookie refresh failed")
        return result

    def reset_circuit(self, reason: str = "manual reset") -> dict[str, Any]:
        with self._lock:
            self._reset_circuit()
            self._last_error = ""
        return {"ok": True, "reason": reason, "circuit_open": False}

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
        active_proxy = ""
        try:
            if settings.monitor_provider.lower() == "xianyu":
                items: list[dict[str, Any]] = []
                pages = max(1, min(10, settings.monitor_pages))
                keywords = self._resolved_monitor_keywords()
                proxies = self._get_proxies(self._xianyu.search_url)
                active_proxy = proxy_url_from_mapping(proxies) or ""
                with self._lock:
                    self._last_proxy = active_proxy
                cookie = self._cookie_provider.get_cookie()
                refreshed = False
                seen_keys: set[tuple[str, str, float]] = set()
                for keyword in keywords:
                    for p in range(1, pages + 1):
                        try:
                            batch = self._xianyu.fetch(
                                page=p,
                                proxies=proxies,
                                cookie_override=cookie,
                                keyword=keyword,
                            )
                        except XianyuHttpError as exc:
                            if not refreshed and _should_refresh_cookie(exc):
                                refreshed = True
                                cookie = self._cookie_provider.get_cookie(force_refresh=True) or cookie
                                batch = self._xianyu.fetch(
                                    page=p,
                                    proxies=proxies,
                                    cookie_override=cookie,
                                    keyword=keyword,
                                )
                            else:
                                raise
                        for item in batch:
                            if not isinstance(item, dict):
                                continue
                            try:
                                price_value = float(item.get("price") or 0)
                            except (TypeError, ValueError):
                                price_value = 0.0
                            key = (
                                str(item.get("id") or "").strip(),
                                str(item.get("title") or "").strip(),
                                price_value,
                            )
                            if key in seen_keys:
                                continue
                            seen_keys.add(key)
                            normalized = dict(item)
                            normalized.setdefault("keyword", keyword)
                            items.append(normalized)
                return items
            return self._fetch_generic()
        except XianyuHttpError as exc:
            self._register_error(exc, is_403=exc.status == 403, active_proxy=active_proxy)
            self._record_health(success=False, reason=f"xianyu_http_{exc.status}")
            raise
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            self._register_error(exc, is_403=status == 403, active_proxy=active_proxy)
            self._record_health(success=False, reason=f"http_error_{status}")
            raise
        except Exception as exc:
            self._register_error(exc, is_403=False, active_proxy=active_proxy)
            self._record_health(success=False, reason=str(exc))
            raise

    def _fetch_generic(self) -> list[dict[str, Any]]:
        headers = {
            "User-Agent": self._pick_user_agent(),
            "Accept": "application/json",
        }
        proxies = self._get_proxies(settings.monitor_target_url)
        with self._lock:
            self._last_proxy = proxy_url_from_mapping(proxies) or ""
        response = request_get(
            settings.monitor_target_url,
            headers=headers,
            timeout=settings.monitor_timeout_sec,
            proxies=proxies,
        )
        if response.status_code == 403:
            raise RuntimeError("target status code: 403")
        if response.status_code != 200:
            raise RuntimeError(f"target status code: {response.status_code}")

        data = response.json()
        if isinstance(data, dict):
            items = data.get("items", [])
            return items if isinstance(items, list) else []
        if isinstance(data, list):
            return data
        return []

    def _get_proxies(self, target_url: str | None = None) -> dict[str, str] | None:
        if target_url:
            return resolve_proxy_for_url(target_url)
        return resolve_proxy()

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

    def _register_error(self, exc: Exception, is_403: bool = False, active_proxy: str = "") -> None:
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
        self._maybe_rotate_proxy(exc=exc, is_403=is_403, active_proxy=active_proxy)

    def _open_circuit(self, reason: str) -> None:
        self._circuit_open = True
        self._circuit_reason = reason
        self._circuit_open_at = datetime.now(timezone.utc).isoformat()
        self._stop_event.set()
        print(f"[market_monitor] CIRCUIT OPEN: {reason}")
        subject, body = format_circuit_email(
            reason=reason,
            keyword=",".join(self._resolved_monitor_keywords()),
            last_error=self._last_error,
            consecutive_errors=self._consecutive_errors,
            consecutive_403=self._consecutive_403,
        )
        send_alert_email(subject, body)

    def _resolved_monitor_keywords(self) -> list[str]:
        keywords = [kw.strip() for kw in settings.monitor_keywords if kw and kw.strip()]
        if keywords:
            return keywords
        fallback = settings.monitor_keyword.strip()
        return [fallback] if fallback else []

    def _reset_circuit(self) -> None:
        self._circuit_open = False
        self._circuit_reason = ""
        self._circuit_open_at = ""
        self._consecutive_errors = 0
        self._consecutive_403 = 0
        self._error_count = 0
        self._health_guard_triggered = False
        self._health_guard_reason = ""
        self._health_last_rate = 1.0
        self._health_window.clear()

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

    def _pick_user_agent(self) -> str:
        uas = [ua.strip() for ua in settings.monitor_user_agents if ua and ua.strip()]
        if not uas:
            return "Mozilla/5.0"
        return random.choice(uas)

    def _record_health(self, *, success: bool, reason: str = "") -> None:
        should_trip = False
        trip_reason = ""
        with self._lock:
            self._health_window.append(1 if success else 0)
            total = len(self._health_window)
            if total <= 0:
                self._health_last_rate = 1.0
                return
            success_count = sum(self._health_window)
            self._health_last_rate = success_count / float(total)
            min_samples = max(1, int(settings.monitor_health_min_samples))
            min_rate = max(0.0, min(1.0, float(settings.monitor_health_min_success_rate)))
            if (
                total >= min_samples
                and self._health_last_rate < min_rate
                and not self._circuit_open
                and not self._health_guard_triggered
            ):
                self._health_guard_triggered = True
                trip_reason = (
                    "health_guard_triggered "
                    f"(success_rate={self._health_last_rate:.2%}, samples={total}, reason={reason})"
                )
                self._health_guard_reason = trip_reason
                should_trip = True
        if should_trip:
            self._open_circuit(trip_reason)

    def _maybe_rotate_proxy(self, *, exc: Exception, is_403: bool, active_proxy: str) -> None:
        message = str(exc).lower()
        proxy_error = is_403 or any(
            token in message for token in ("429", "rate", "too many", "proxy", "forbidden")
        )
        if not proxy_error:
            return

        if active_proxy:
            mark_proxy_bad(active_proxy, reason=f"monitor_error:{str(exc)[:120]}")
        rotate_proxy(reason=f"monitor_error:{str(exc)[:120]}", required=False)


monitor_service = MarketMonitorService()
