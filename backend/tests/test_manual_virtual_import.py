from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import repositories as repo
from app.config import settings
from app.database import init_db
from app.main import create_app
from app.schemas import MarketplaceOfferIn


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

import import_manual_virtual_offers as manual_import  # noqa: E402


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_normalize_manual_virtual_offer_forces_virtual_fields() -> None:
    rows = manual_import.normalize_manual_virtual_offers(
        [
            {
                "title": "Q coin auto recharge instant delivery direct topup",
                "list_price": 58.5,
                "listing_url": "https://example.com/manual-q-coin",
                "platform": "manual_virtual",
                "shipping_cost": 12,
            }
        ]
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["platform"] == "manual_virtual"
    assert row["item_type"] == "virtual_goods"
    assert row["shipping_cost"] == 0.0
    assert row["status"] == "open"
    assert row["raw"]["provenance"] == "operator_manual_virtual_baseline"


def test_manual_virtual_import_rejects_reserved_platform() -> None:
    with pytest.raises(ValueError, match="reserved platform"):
        manual_import.normalize_manual_virtual_offers(
            [
                {
                    "platform": "jd",
                    "title": "Q coin auto recharge instant delivery direct topup",
                    "list_price": 58.5,
                    "listing_url": "https://example.com/manual-q-coin",
                }
            ]
        )


def test_manual_virtual_import_rejects_physical_goods_terms() -> None:
    with pytest.raises(ValueError, match="physical goods keyword"):
        manual_import.normalize_manual_virtual_offers(
            [
                {
                    "title": "Plastic toy coin prop set",
                    "list_price": 8.88,
                    "listing_url": "https://example.com/plastic-toy",
                }
            ]
        )


def test_manual_virtual_import_rejects_invalid_price() -> None:
    with pytest.raises(ValueError, match="positive list_price"):
        manual_import.normalize_manual_virtual_offers(
            [
                {
                    "title": "Q coin auto recharge instant delivery direct topup",
                    "list_price": 0,
                    "listing_url": "https://example.com/manual-q-coin",
                }
            ]
        )


def test_manual_virtual_import_summary_flags_duplicates_and_stale_rows() -> None:
    old_listed_at = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
    rows = manual_import.normalize_manual_virtual_offers(
        [
            {
                "offer_id": "manual-q-coin",
                "title": "Q coin auto recharge instant delivery direct topup",
                "list_price": 58.5,
                "listing_url": "https://example.com/manual-q-coin",
                "listed_at": old_listed_at,
            },
            {
                "offer_id": "manual-q-coin",
                "title": "Q coin auto recharge instant delivery direct topup",
                "list_price": 59.5,
                "listing_url": "https://example.com/manual-q-coin-dup",
            },
        ]
    )

    summary = manual_import.summarize_manual_virtual_offers(rows, max_age_hours=48)

    assert summary["duplicate_count"] == 1
    assert summary["stale_count"] == 1
    assert summary["stale_rows"][0]["offer_id"] == "manual-q-coin"


def test_manual_virtual_offer_ingest_creates_virtual_only_arbitrage(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "manual_virtual.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="pinduoduo",
                    offer_id="pdd-virtual-baseline",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=49.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/pdd-virtual-baseline",
                    raw={},
                )
            ]
        )

        manual_rows = manual_import.normalize_manual_virtual_offers(
            [
                {
                    "offer_id": "manual-virtual-baseline",
                    "title": "Q coin auto recharge instant delivery direct topup",
                    "canonical_key": "q coin auto recharge instant delivery direct topup",
                    "list_price": 65.0,
                    "listing_url": "https://example.com/manual-virtual-baseline",
                    "listed_at": listed_at.isoformat(),
                }
            ]
        )

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={"username": settings.ui_auth_username, "password": settings.ui_auth_password},
            )
            assert login.status_code == 200
            token = login.json()["data"]["token"]

            imported = client.post("/marketplace/offers/ingest", json=manual_rows, headers=_bearer(token))
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
            assert preview_payload["items"][0]["sources"] == ["manual_virtual", "pinduoduo"]
            assert all(offer["item_type"] == "virtual_goods" for offer in preview_payload["items"][0]["offers"])

            opportunities = client.get(
                "/analysis/arbitrage/opportunities",
                params={"limit": 5, "window_hours": 72, "virtual_only": True, "shipping_cost": 0.0},
                headers=_bearer(token),
            )
            assert opportunities.status_code == 200
            opportunity_payload = opportunities.json()
            assert opportunity_payload["summary"]["opportunity_count"] == 1
            assert opportunity_payload["items"][0]["buy_source"] == "pinduoduo"
            assert opportunity_payload["items"][0]["sell_source"] == "manual_virtual"
            assert opportunity_payload["items"][0]["item_type"] == "virtual_goods"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
