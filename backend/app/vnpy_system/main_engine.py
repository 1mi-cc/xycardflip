from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs

import requests

from ..config import settings
from ..services.cookie_provider import CookieProvider
from ..services.xianyu_client import XianyuClient
from .event_engine import Event, EventType, event_engine

logger = logging.getLogger(__name__)


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
        for page in range(1, max(1, pages) + 1):
            items.extend(
                self._xianyu.fetch(
                    page=page,
                    proxies=proxies,
                    cookie_override=cookie,
                    keyword=keyword,
                )
            )
        return items

    def emit_event(self, event_type: EventType, data: dict) -> None:
        event = Event(event_type=event_type, data=data, timestamp=datetime.now(timezone.utc).isoformat())
        self.event_engine.emit(event)

    def _get_proxies(self) -> dict[str, str] | None:
        if not settings.monitor_use_proxy_pool:
            return None
        base_url = settings.proxy_pool_api
        raw_params = parse_qs(settings.proxy_pool_params)
        params = {k: v[0] for k, v in raw_params.items()}
        try:
            resp = requests.get(base_url, params=params, timeout=5)
        except Exception:
            return None
        if resp.status_code != 200:
            return None
        try:
            ip_ports = json.loads(resp.text)
        except Exception:
            return None
        if not isinstance(ip_ports, list) or not ip_ports:
            return None
        best = ip_ports[0]
        if not isinstance(best, list) or len(best) < 2:
            return None
        ip = str(best[0]).strip()
        port = str(best[1]).strip()
        if not ip or not port:
            return None
        proxy = f"http://{ip}:{port}"
        return {"http": proxy, "https": proxy}


main_engine = MainEngine()
