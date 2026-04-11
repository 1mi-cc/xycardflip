from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

import requests


MANUAL_VIRTUAL_PLATFORM = "manual_virtual"
PROVENANCE = "operator_manual_virtual_baseline"
RESERVED_PLATFORMS = {"jd", "pinduoduo", "taobao", "xianyu", "xianyu_monitor", "goofish", "idle"}
PHYSICAL_KEYWORDS = (
    "plastic",
    "toy",
    "prop",
    "physical",
    "shipping",
    "\u5851\u6599",
    "\u73a9\u5177",
    "\u5b9e\u7269",
    "\u5305\u90ae",
    "\u8fd0\u8d39",
    "\u624b\u5de5",
    "\u9970\u54c1",
    "\u5408\u91d1",
    "\u94dc\u94b1",
    "\u76f8\u6846",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load_input(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in ("items", "offers", "rows"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise ValueError("Input JSON must be a list or an object with items/offers/rows.")
    rows = [item for item in payload if isinstance(item, dict)]
    if len(rows) != len(payload):
        raise ValueError("Every input item must be an object.")
    return rows


def _price(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError) as exc:
        raise ValueError("Each manual virtual offer needs a positive list_price.") from exc


def _validate_no_physical_terms(title: str) -> None:
    lowered = title.lower()
    for keyword in PHYSICAL_KEYWORDS:
        if keyword.lower() in lowered:
            raise ValueError(f"Rejected physical goods keyword in title: {keyword}")


def normalize_manual_virtual_offers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for index, row in enumerate(rows, start=1):
        title = _text(row.get("title"))
        if not title:
            raise ValueError(f"Row {index} needs a non-empty title.")
        _validate_no_physical_terms(title)

        platform = _text(row.get("platform"))
        if platform and platform != MANUAL_VIRTUAL_PLATFORM:
            if platform.lower() in RESERVED_PLATFORMS:
                raise ValueError(f"Row {index} uses reserved platform: {platform}")
            raise ValueError(f"Row {index} platform must be {MANUAL_VIRTUAL_PLATFORM}.")

        list_price = _price(row.get("list_price"))
        if list_price <= 0:
            raise ValueError(f"Row {index} needs a positive list_price.")

        listing_url = _text(row.get("listing_url"))
        if not listing_url:
            raise ValueError(f"Row {index} needs a non-empty listing_url.")

        raw = dict(row.get("raw") or {})
        raw.update(
            {
                "provenance": PROVENANCE,
                "source_platform_hint": platform or MANUAL_VIRTUAL_PLATFORM,
            }
        )
        normalized.append(
            {
                "platform": MANUAL_VIRTUAL_PLATFORM,
                "offer_id": _text(row.get("offer_id")) or None,
                "seller_id": _text(row.get("seller_id")) or None,
                "title": title,
                "canonical_key": _text(row.get("canonical_key")) or title,
                "item_type": "virtual_goods",
                "list_price": list_price,
                "shipping_cost": 0.0,
                "fee_rate": 0.0,
                "currency": _text(row.get("currency")) or "CNY",
                "listed_at": _text(row.get("listed_at")) or now,
                "status": "open",
                "listing_url": listing_url,
                "raw": raw,
            }
        )
    return normalized


def _resolve_auth_value(explicit: str, env_key: str, fallback: str) -> str:
    return explicit or os.environ.get(env_key, "").strip() or fallback


def _push_rows(
    rows: list[dict[str, Any]],
    *,
    server_host: str,
    public_app_port: int,
    username: str,
    password: str,
    timeout_sec: float,
) -> dict[str, Any]:
    base_url = f"http://{server_host}:{int(public_app_port)}/card-api"
    login = requests.post(
        f"{base_url}/auth/login",
        json={"username": username, "password": password},
        timeout=timeout_sec,
    )
    login.raise_for_status()
    token = ((login.json() or {}).get("data") or {}).get("token")
    if not token:
        raise RuntimeError("Remote auth token missing.")
    response = requests.post(
        f"{base_url}/marketplace/offers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json=rows,
        timeout=timeout_sec,
    )
    response.raise_for_status()
    return response.json()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import manually verified virtual marketplace offers.")
    parser.add_argument("--input", required=True, help="Path to JSON list or object with items/offers/rows.")
    parser.add_argument("--push", action="store_true", help="Push to the remote marketplace ingest endpoint.")
    parser.add_argument("--server-host", default="61.147.247.54")
    parser.add_argument("--public-app-port", type=int, default=18036)
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--timeout-sec", type=float, default=20.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    rows = normalize_manual_virtual_offers(_load_input(args.input))
    if not args.push:
        print(json.dumps({"dry_run": True, "count": len(rows), "rows": rows}, ensure_ascii=True, indent=2))
        return 0

    result = _push_rows(
        rows,
        server_host=str(args.server_host),
        public_app_port=int(args.public_app_port),
        username=_resolve_auth_value(args.username, "CARD_FLIP_USERNAME", "operator"),
        password=_resolve_auth_value(args.password, "CARD_FLIP_PASSWORD", "Ccj666888.qwer1013"),
        timeout_sec=float(args.timeout_sec),
    )
    print(json.dumps({"dry_run": False, "count": len(rows), "result": result}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
