from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs

import requests

# ==========================================
# 1. Core disguise: request headers
# ==========================================
HEADERS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
]

TARGET_URL = os.getenv(
    "MONITOR_TARGET_URL",
    "https://api.mock-market.com/v1/search/items?keyword=card",
)
TIMEOUT_SEC = float(os.getenv("MONITOR_TIMEOUT_SEC", "10"))
MIN_DELAY_SEC = float(os.getenv("MONITOR_MIN_DELAY_SEC", "1.5"))
MAX_DELAY_SEC = float(os.getenv("MONITOR_MAX_DELAY_SEC", "4.5"))
LONG_REST_PROBABILITY = float(os.getenv("MONITOR_LONG_REST_PROBABILITY", "0.05"))
LONG_REST_MIN_SEC = float(os.getenv("MONITOR_LONG_REST_MIN_SEC", "10"))
LONG_REST_MAX_SEC = float(os.getenv("MONITOR_LONG_REST_MAX_SEC", "30"))

USE_PROXY_POOL = os.getenv("MONITOR_USE_PROXY_POOL", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
PROXY_POOL_API = os.getenv("PROXY_POOL_API", "http://127.0.0.1:8899/")
PROXY_POOL_PARAMS = os.getenv("PROXY_POOL_PARAMS", "types=0&count=3")

INGEST_URL = os.getenv("INGEST_URL", "http://127.0.0.1:8000/ingest/listings")
AUTO_SCAN_URL = os.getenv("AUTO_SCAN_URL", "http://127.0.0.1:8000/opportunities/scan")
AUTO_SCAN_AFTER_INGEST = os.getenv("AUTO_SCAN_AFTER_INGEST", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def get_proxy_from_pool() -> dict[str, str] | None:
    if not USE_PROXY_POOL:
        return None
    params = {k: v[0] for k, v in parse_qs(PROXY_POOL_PARAMS).items()}
    try:
        resp = requests.get(PROXY_POOL_API, params=params, timeout=5)
        if resp.status_code != 200:
            return None
        ip_ports = json.loads(resp.text)
        if not isinstance(ip_ports, list) or not ip_ports:
            return None
        first = ip_ports[0]
        if not isinstance(first, list) or len(first) < 2:
            return None
        proxy = f"http://{first[0]}:{first[1]}"
        return {"http": proxy, "https": proxy}
    except Exception:
        return None


def fetch_market_data() -> list[dict[str, Any]]:
    headers = {
        "User-Agent": random.choice(HEADERS_LIST),
        "Accept": "application/json",
    }
    proxies = get_proxy_from_pool()
    response = requests.get(
        TARGET_URL,
        headers=headers,
        timeout=TIMEOUT_SEC,
        proxies=proxies,
    )
    if response.status_code != 200:
        print(f"warning: target status {response.status_code}")
        return []

    data = response.json()
    if isinstance(data, dict):
        items = data.get("items", [])
        return items if isinstance(items, list) else []
    if isinstance(data, list):
        return data
    return []


def to_listing_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("name") or item.get("title") or "").strip()
        if not title:
            continue
        try:
            price = float(item.get("price", 0))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue

        rows.append(
            {
                "source": "market_monitor_script",
                "listing_id": (str(item.get("id") or item.get("listing_id") or "").strip() or None),
                "seller_id": (str(item.get("seller_id") or "").strip() or None),
                "title": title,
                "description": str(item.get("description") or ""),
                "list_price": price,
                "listed_at": now,
                "status": "open",
                "raw": item,
            }
        )
    return rows


def push_to_backend(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    ingest_resp = requests.post(INGEST_URL, json=rows, timeout=15)
    ingest_resp.raise_for_status()
    inserted = ingest_resp.json().get("inserted", 0)
    print(f"inserted listings: {inserted}")

    if AUTO_SCAN_AFTER_INGEST:
        scan_resp = requests.post(AUTO_SCAN_URL, params={"limit": 200}, timeout=20)
        scan_resp.raise_for_status()
        print(f"scan result: {scan_resp.json()}")


def main_monitor_loop() -> None:
    print("market monitor loop started")

    while True:
        try:
            items = fetch_market_data()
            for item in items:
                card_name = item.get("name") or item.get("title")
                price = item.get("price")
                attributes = item.get("attributes")
                print(f"found item: {card_name} | price: {price} | attrs: {attributes}")

            rows = to_listing_rows(items)
            push_to_backend(rows)
        except Exception as exc:
            print(f"network or ingest error: {exc}")

        sleep_time = random.uniform(MIN_DELAY_SEC, MAX_DELAY_SEC)
        if random.random() < LONG_REST_PROBABILITY:
            long_rest = random.uniform(LONG_REST_MIN_SEC, LONG_REST_MAX_SEC)
            print(f"long rest {long_rest:.2f}s")
            time.sleep(long_rest)
        else:
            print(f"sleep {sleep_time:.2f}s\n")
            time.sleep(sleep_time)


if __name__ == "__main__":
    main_monitor_loop()
