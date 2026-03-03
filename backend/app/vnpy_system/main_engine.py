from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..services.cookie_provider import CookieProvider
from ..services.proxy_resolver import resolve_proxy
from ..services.xianyu_client import XianyuClient, XianyuHttpError
from .event_engine import Event, EventType, event_engine

logger = logging.getLogger(__name__)


def _should_refresh_cookie(exc: XianyuHttpError) -> bool:
    text = (exc.body_excerpt or str(exc)).lower()
    if exc.status in {401, 403}:
        return True
    return any(key in text for key in ("token", "session", "auth", "login"))


class MainEngine:
    """System core that coordinates engines and data sources."""

    def __init__(self) -> None:
        self.event_engine = event_engine
        self.engines: dict[str, object] = {}
        self._xianyu = XianyuClient()
        self._cookie_provider = CookieProvider()
        self.started = False
        self.last_error = ""

    def start(self) -> None:
        if self.started:
            return
        self.event_engine.start()
        self.started = True
        logger.info("main engine started")

    def stop(self) -> None:
        if not self.started:
            return
        self.started = False
        self.event_engine.stop()
        logger.info("main engine stopped")

    def register_engine(self, name: str, engine: object) -> None:
        self.engines[name] = engine
        logger.info("registered engine: %s", name)

    def get_engine(self, name: str) -> object | None:
        return self.engines.get(name)

    def search_items(self, keyword: str, *, pages: int = 1) -> list[dict[str, Any]]:
        if not keyword.strip():
            return []
        proxies = self._get_proxies()
        cookie = self._cookie_provider.get_cookie()
        items: list[dict[str, Any]] = []
        refreshed = False
        for page in range(1, max(1, pages) + 1):
            try:
                batch = self._xianyu.fetch(
                    page=page,
                    proxies=proxies,
                    cookie_override=cookie,
                    keyword=keyword,
                )
            except XianyuHttpError as exc:
                if not refreshed and _should_refresh_cookie(exc):
                    refreshed = True
                    cookie = self._cookie_provider.get_cookie(force_refresh=True) or cookie
                    batch = self._xianyu.fetch(
                        page=page,
                        proxies=proxies,
                        cookie_override=cookie,
                        keyword=keyword,
                    )
                else:
                    raise
            items.extend(batch)
        return items

    def emit_event(self, event_type: EventType, data: dict) -> None:
        event = Event(event_type=event_type, data=data, timestamp=datetime.now(timezone.utc).isoformat())
        self.event_engine.emit(event)

    def _get_proxies(self) -> dict[str, str] | None:
        return resolve_proxy()


main_engine = MainEngine()
