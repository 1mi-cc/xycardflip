"""
One-shot Xianyu spider to fetch multiple pages and ingest listings.
Use the same parsing logic as the monitor but without a long-running loop.

Usage:
  python xianyu_spider.py

Env vars (reuse monitor defaults):
  XIAN_YU_KEYWORDS, XIAN_YU_KEYWORD, MONITOR_MAX_PRICE, MONITOR_PAGES
  XIAN_YU_COOKIE, XIAN_YU_SEARCH_URL
  MONITOR_USE_PROXY_POOL, PROXY_POOL_API, PROXY_POOL_PARAMS
"""

from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

from app.config import settings
from app.repositories import insert_listings
from app.schemas import ListingIn
from app.services.xianyu_client import XianyuClient
from app.services.cookie_provider import CookieProvider
from app.services.proxy_resolver import resolve_proxy


def main() -> None:
    client = XianyuClient()
    cookie_provider = CookieProvider()
    cookie = cookie_provider.get_cookie()
    proxies = resolve_proxy()
    pages = max(1, min(10, settings.monitor_pages))
    keywords = [kw.strip() for kw in settings.monitor_keywords if kw and kw.strip()]
    if not keywords:
        fallback = settings.monitor_keyword.strip()
        keywords = [fallback] if fallback else []

    all_items: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, float]] = set()
    for keyword in keywords:
        for p in range(1, pages + 1):
            print(f"[spider] fetch keyword={keyword} page={p}")
            items = client.fetch(page=p, proxies=proxies, cookie_override=cookie, keyword=keyword)
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    price_value = float(item.get("price", 0) or 0)
                except Exception:
                    price_value = 0.0
                dedupe_key = (
                    str(item.get("id") or "").strip(),
                    str(item.get("title") or "").strip(),
                    price_value,
                )
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                normalized = dict(item)
                normalized.setdefault("keyword", keyword)
                all_items.append(normalized)

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
