"""
One-shot Xianyu spider to fetch multiple pages and ingest listings.
Use the same parsing logic as the monitor but without a long-running loop.

Usage:
  python xianyu_spider.py

Env vars (reuse monitor defaults):
  XIAN_YU_KEYWORD, MONITOR_MAX_PRICE, MONITOR_PAGES
  XIAN_YU_COOKIE, XIAN_YU_SEARCH_URL
  MONITOR_USE_PROXY_POOL, PROXY_POOL_API, PROXY_POOL_PARAMS
"""

from __future__ import annotations

import os
from typing import Any
from datetime import datetime, timezone

from app.config import settings
from app.repositories import insert_listings
from app.schemas import ListingIn
from urllib.parse import parse_qs
import json
import requests

from app.services.xianyu_client import XianyuClient


def main() -> None:
    client = XianyuClient()
    proxies = _get_proxies() if settings.monitor_use_proxy_pool else None
    pages = max(1, min(10, settings.monitor_pages))
    all_items: list[dict[str, Any]] = []
    for p in range(1, pages + 1):
        print(f"[spider] fetch page {p}")
        items = client.fetch(page=p, proxies=proxies)
        all_items.extend(items)

    print(f"[spider] fetched {len(all_items)} raw items")
    rows: list[ListingIn] = []
    for item in all_items:
        try:
            price = float(item.get("price", 0))
        except Exception:
            continue
        if price <= 0 or price > settings.monitor_max_price:
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
        rows.append(
            ListingIn(
                source="xianyu_spider",
                listing_id=str(item.get("id") or "").strip() or None,
                seller_id=str(item.get("seller_id") or "").strip() or None,
                title=title,
                description=str(item.get("description") or ""),
                list_price=price,
                listed_at=datetime.now(timezone.utc),
                status="open",
                raw=item,
            )
        )

    if not rows:
        print("[spider] nothing to insert")
        return

    inserted = insert_listings(rows)
    print(f"[spider] inserted {inserted} listings into DB")


if __name__ == "__main__":
    main()


def _get_proxies() -> dict[str, str] | None:
    base_url = settings.proxy_pool_api
    raw_params = parse_qs(settings.proxy_pool_params)
    params = {k: v[0] for k, v in raw_params.items()}
    try:
        resp = requests.get(base_url, params=params, timeout=5)
        if resp.status_code != 200:
            return None
        ip_ports = json.loads(resp.text)
        if not isinstance(ip_ports, list) or not ip_ports:
            return None
        best = ip_ports[0]
        if not isinstance(best, list) or len(best) < 2:
            return None
        proxy = f"http://{str(best[0]).strip()}:{str(best[1]).strip()}"
        return {"http": proxy, "https": proxy}
    except Exception:
        return None
