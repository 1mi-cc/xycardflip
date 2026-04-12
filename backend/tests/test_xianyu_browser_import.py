from __future__ import annotations

from datetime import datetime, timezone
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app import repositories as repo
from app.config import settings
from app.database import init_db
from app.main import create_app
from app.schemas import MarketplaceOfferIn


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

import import_xianyu_browser_offers as xianyu_import  # noqa: E402


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_normalize_xianyu_browser_items_keeps_virtual_goods() -> None:
    rows = xianyu_import.normalize_xianyu_browser_items(
        [
            {
                "id": "xy-browser-1",
                "title": "Q coin auto recharge instant delivery direct topup",
                "description": "虚拟商品 游戏内交易 不退不换 秒发",
                "seller_id": "xy-seller",
                "price": 58.5,
            }
        ],
        keyword="Q coin auto recharge",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["platform"] == "xianyu"
    assert row["offer_id"] == "xy-browser-1"
    assert row["item_type"] == "virtual_goods"
    assert row["shipping_cost"] == 0.0
    assert row["status"] == "open"
    assert row["raw"]["provenance"] == "operator_xianyu_browser_session"
    assert row["raw"]["keyword"] == "Q coin auto recharge"


def test_normalize_xianyu_browser_items_skips_physical_noise_when_virtual_only() -> None:
    rows = xianyu_import.normalize_xianyu_browser_items(
        [
            {
                "id": "xy-browser-physical-1",
                "title": "Plastic toy coin prop set",
                "description": "实体玩具 包邮",
                "seller_id": "xy-seller",
                "price": 8.88,
            }
        ],
        keyword="coin",
        virtual_only=True,
    )

    assert rows == []


def test_xianyu_browser_offer_ingest_creates_virtual_only_arbitrage(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "xianyu_browser_import.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="pinduoduo",
                    offer_id="pdd-browser-baseline",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=49.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/pdd-browser-baseline",
                    raw={},
                )
            ]
        )

        xianyu_rows = xianyu_import.normalize_xianyu_browser_items(
            [
                {
                    "id": "xy-browser-baseline",
                    "title": "Q coin auto recharge instant delivery direct topup",
                    "description": "虚拟商品 游戏内交易 不退不换 秒发",
                    "seller_id": "xy-seller",
                    "price": 65.0,
                    "listed_at": listed_at.isoformat(),
                    "listing_url": "https://www.goofish.com/item?id=xy-browser-baseline",
                }
            ],
            keyword="Q coin auto recharge",
        )

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={"username": settings.ui_auth_username, "password": settings.ui_auth_password},
            )
            assert login.status_code == 200
            token = login.json()["data"]["token"]

            imported = client.post("/marketplace/offers/ingest", json=xianyu_rows, headers=_bearer(token))
            assert imported.status_code == 200
            assert imported.json()["inserted"] == 1

            preview = client.get(
                "/analysis/arbitrage/matching-preview",
                params={"limit": 5, "window_hours": 72, "virtual_only": True},
                headers=_bearer(token),
            )
            assert preview.status_code == 200
            preview_payload = preview.json()
            assert preview_payload["virtual_only"] is True
            assert preview_payload["items"][0]["sources"] == ["pinduoduo", "xianyu"]

            opportunities = client.get(
                "/analysis/arbitrage/opportunities",
                params={"limit": 5, "window_hours": 72, "virtual_only": True, "shipping_cost": 0.0},
                headers=_bearer(token),
            )
            assert opportunities.status_code == 200
            opportunity_payload = opportunities.json()
            assert opportunity_payload["summary"]["opportunity_count"] == 1
            assert opportunity_payload["items"][0]["buy_source"] == "pinduoduo"
            assert opportunity_payload["items"][0]["sell_source"] == "xianyu"
            assert opportunity_payload["items"][0]["item_type"] == "virtual_goods"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
