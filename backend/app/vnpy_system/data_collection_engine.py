from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from .. import repositories as repo
from ..schemas import ListingIn
from .event_engine import EventType
from .main_engine import MainEngine

logger = logging.getLogger(__name__)


class DataCollectionEngine:
    """Periodic scanner for Xianyu listings."""

    def __init__(self, main_engine: MainEngine, scan_interval: int = 300, pages: int | None = None) -> None:
        self.main_engine = main_engine
        self.scan_interval = max(10, int(scan_interval))
        self.pages = pages or settings.monitor_pages
        self.keywords: list[str] = []
        self.active = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_run_at = ""
        self._last_error = ""
        self._last_fetched = 0
        self._last_inserted = 0

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active": self.active,
                "keywords": list(self.keywords),
                "scan_interval": self.scan_interval,
                "pages": self.pages,
                "last_run_at": self._last_run_at,
                "last_error": self._last_error,
                "last_fetched": self._last_fetched,
                "last_inserted": self._last_inserted,
            }

    def add_keyword(self, keyword: str) -> None:
        cleaned = keyword.strip()
        if not cleaned:
            return
        if cleaned not in self.keywords:
            self.keywords.append(cleaned)
            logger.info("added keyword: %s", cleaned)

    def set_keywords(self, keywords: list[str]) -> None:
        cleaned = [kw.strip() for kw in keywords if kw and kw.strip()]
        self.keywords = list(dict.fromkeys(cleaned))
        logger.info("keywords updated: %s", ",".join(self.keywords))

    def start(self) -> None:
        if self.active:
            return
        self.active = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scan_loop, daemon=True, name="vnpy-data-scan")
        self._thread.start()
        logger.info("data collection engine started")

    def stop(self) -> None:
        if not self.active:
            return
        self.active = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("data collection engine stopped")

    def scan_once(self) -> dict[str, int]:
        fetched = 0
        inserted = 0
        errors: list[str] = []
        for keyword in list(self.keywords):
            try:
                f, i = self._scan_keyword(keyword)
                fetched += f
                inserted += i
            except Exception as exc:
                msg = f"{keyword}: {exc}"
                errors.append(msg)
                logger.error("scan keyword error: %s", msg)
        with self._lock:
            self._last_run_at = datetime.now(timezone.utc).isoformat()
            self._last_fetched = fetched
            self._last_inserted = inserted
            self._last_error = "; ".join(errors)
        result = {"fetched": fetched, "inserted": inserted}
        if errors:
            result["errors"] = errors
        return result

    def _scan_loop(self) -> None:
        while self.active and not self._stop_event.is_set():
            try:
                self.scan_once()
            except Exception as exc:
                with self._lock:
                    self._last_error = str(exc)
                logger.error("scan loop error: %s", exc, exc_info=True)

            if self._stop_event.wait(timeout=self.scan_interval):
                break

    def _scan_keyword(self, keyword: str) -> tuple[int, int]:
        fetched = 0
        inserted = 0
        try:
            items = self.main_engine.search_items(keyword, pages=self.pages)
            fetched = len(items)
            for item in items:
                listing = self._build_listing(item)
                if listing is None:
                    continue
                row_id, is_new = repo.upsert_listing(listing)
                if row_id is None:
                    continue
                if is_new:
                    inserted += 1
                    self.main_engine.emit_event(
                        EventType.ITEM_FOUND,
                        {"listing_row_id": row_id, "keyword": keyword},
                    )
        except Exception as exc:
            logger.error("scan keyword error (%s): %s", keyword, exc, exc_info=True)
            raise
        return fetched, inserted

    def _build_listing(self, item: dict[str, Any]) -> ListingIn | None:
        try:
            price = float(item.get("price", 0))
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        if price > settings.monitor_max_price:
            return None
        title = str(item.get("title") or "").strip()
        if not title:
            return None
        listing_id = str(item.get("id") or item.get("listing_id") or "").strip() or None
        seller_id = str(item.get("seller_id") or "").strip() or None
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else item
        return ListingIn(
            source="xianyu_vnpy",
            listing_id=listing_id,
            seller_id=seller_id,
            title=title,
            description=str(item.get("description") or ""),
            list_price=price,
            listed_at=datetime.now(timezone.utc),
            status="open",
            raw=raw,
        )
