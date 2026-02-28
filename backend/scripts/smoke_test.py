from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def run() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    temp_db = repo_root / "data" / "smoke_test.db"
    temp_db.parent.mkdir(parents=True, exist_ok=True)
    if temp_db.exists():
        temp_db.unlink()
    os.environ["SQLITE_PATH"] = str(temp_db)

    from app.main import app  # noqa: PLC0415

    with TestClient(app) as client:
        sales = [
            {
                "source": "smoke",
                "item_id": "sale-1",
                "title": "Blue Dragon SSR",
                "description": "near mint",
                "sold_price": 220,
                "sold_at": "2026-02-20T10:00:00Z",
                "raw": {},
            },
            {
                "source": "smoke",
                "item_id": "sale-2",
                "title": "Blue Dragon SSR",
                "description": "nm",
                "sold_price": 210,
                "sold_at": "2026-02-21T10:00:00Z",
                "raw": {},
            },
        ]
        listings = [
            {
                "source": "smoke",
                "listing_id": "list-1",
                "seller_id": "seller-1",
                "title": "Blue Dragon SSR Near Mint",
                "description": "clean",
                "list_price": 80,
                "listed_at": "2026-02-27T09:00:00Z",
                "status": "open",
                "raw": {},
            }
        ]

        assert client.post("/ingest/sales", json=sales).status_code == 200
        assert client.post("/ingest/listings", json=listings).status_code == 200

        scan_res = client.post("/opportunities/scan", params={"limit": 10})
        assert scan_res.status_code == 200

        opps_res = client.get("/opportunities", params={"status": "pending_review"})
        assert opps_res.status_code == 200
        opp_items = opps_res.json().get("items", [])
        assert opp_items, "Expected at least one pending opportunity"

        opp_id = opp_items[0]["opportunity_id"]
        approve_res = client.post(
            "/trades/approve",
            json={
                "opportunity_id": opp_id,
                "approved_buy_price": 80,
                "approved_by": "smoke",
                "note": "auto smoke",
            },
        )
        assert approve_res.status_code == 200
        trade_id = approve_res.json()["trade_id"]

        listed_res = client.post(
            f"/trades/{trade_id}/mark-listed",
            json={"listing_url": "https://example.com/item/1", "note": "listed"},
        )
        assert listed_res.status_code == 200

        sold_res = client.post(
            f"/trades/{trade_id}/mark-sold",
            json={"sold_price": 230, "note": "sold"},
        )
        assert sold_res.status_code == 200

        all_trades = client.get("/trades", params={"limit": 10})
        assert all_trades.status_code == 200
        assert all_trades.json().get("count", 0) >= 1

    if temp_db.exists():
        temp_db.unlink()

    print("smoke_test_passed")


if __name__ == "__main__":
    run()
