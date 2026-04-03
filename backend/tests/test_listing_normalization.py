from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import repositories as repo
from app.config import settings
from app.database import init_db
from app.schemas import ListingIn, SaleIn


@pytest.fixture
def isolated_normalization_sqlite(tmp_path: Path):
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "listing_normalization.db"))
    init_db()
    try:
        yield Path(settings.sqlite_path)
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_upsert_listing_persists_normalization_fields(
    isolated_normalization_sqlite: Path,
) -> None:
    listing = ListingIn(
        source="pytest",
        listing_id="norm-1",
        seller_id="seller-1",
        title="【咸鱼之王】功法残卷 现货秒发 私聊老板",
        description="支持秒发",
        list_price=6.0,
        listed_at=datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
        raw={},
    )

    listing_row_id, created = repo.upsert_listing(listing)

    assert created is True
    row = repo.get_listing(int(listing_row_id))
    assert row is not None
    assert str(row["item_type"]) == "manual_fragment"
    assert str(row["normalized_title"]) == "功法残卷"
    assert str(row["normalized_key"]) == "manual_fragment:功法残卷"
    assert bool(row["normalization_blocked"]) is False
    assert str(row["normalization_version"]) == "listing_normalizer_v1"
    assert "delivery_marketing" in json.loads(str(row["noise_flags_json"]))


def test_get_open_listings_excludes_noise_filtered_rows_by_default(
    isolated_normalization_sqlite: Path,
) -> None:
    noisy = ListingIn(
        source="pytest",
        listing_id="norm-noisy",
        seller_id="seller-2",
        title="咸鱼之王 金图鉴 红图鉴 礼包 全套秒发",
        description="图鉴礼包",
        list_price=18.0,
        listed_at=datetime(2026, 3, 29, 12, 1, tzinfo=timezone.utc),
        raw={},
    )
    clean = ListingIn(
        source="pytest",
        listing_id="norm-clean",
        seller_id="seller-3",
        title="咸鱼之王 功法书页",
        description="书页单出",
        list_price=3.0,
        listed_at=datetime(2026, 3, 29, 12, 2, tzinfo=timezone.utc),
        raw={},
    )

    noisy_id, _ = repo.upsert_listing(noisy)
    clean_id, _ = repo.upsert_listing(clean)

    noisy_row = repo.get_listing(int(noisy_id))
    assert noisy_row is not None
    assert bool(noisy_row["normalization_blocked"]) is True
    assert str(noisy_row["normalization_reason"]) == "catalog_bundle"

    open_rows = repo.get_open_listings(limit=10)
    open_ids = {int(row["id"]) for row in open_rows}
    assert int(clean_id) in open_ids
    assert int(noisy_id) not in open_ids

    all_rows = repo.get_open_listings(limit=10, include_noise_filtered=True)
    all_ids = {int(row["id"]) for row in all_rows}
    assert {int(noisy_id), int(clean_id)}.issubset(all_ids)


def test_insert_listings_dedupes_same_like_titles_without_listing_id(
    isolated_normalization_sqlite: Path,
) -> None:
    rows = [
        ListingIn(
            source="pytest",
            listing_id=None,
            seller_id="seller-4",
            title="咸鱼之王功法卡 至尊卡 秒发",
            description="虚拟道具",
            list_price=5.5,
            listed_at=datetime(2026, 3, 29, 12, 3, tzinfo=timezone.utc),
            raw={"n": 1},
        ),
        ListingIn(
            source="pytest",
            listing_id=None,
            seller_id="seller-4",
            title="【咸鱼之王】功法卡 满红 至尊 秒发",
            description="现货秒发",
            list_price=5.5,
            listed_at=datetime(2026, 3, 29, 12, 3, 10, tzinfo=timezone.utc),
            raw={"n": 2},
        ),
    ]

    inserted = repo.insert_listings(rows)

    assert inserted == 1


def test_normalized_market_snapshots_group_same_like_titles(
    isolated_normalization_sqlite: Path,
) -> None:
    repo.insert_sales(
        [
            SaleIn(
                source="pytest",
                item_id="sale-norm-1",
                title="咸鱼之王功法残卷",
                description="单出",
                sold_price=4.0,
                sold_at=datetime(2026, 3, 29, 11, 0, tzinfo=timezone.utc),
                raw={},
            ),
            SaleIn(
                source="pytest",
                item_id="sale-norm-2",
                title="【咸鱼之王】功法残卷 秒发",
                description="现货",
                sold_price=5.0,
                sold_at=datetime(2026, 3, 29, 11, 30, tzinfo=timezone.utc),
                raw={},
            ),
        ]
    )
    repo.insert_listings(
        [
            ListingIn(
                source="pytest",
                listing_id="market-a",
                seller_id="seller-a",
                title="咸鱼之王功法残卷 秒发",
                description="私聊老板",
                list_price=5.5,
                listed_at=datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
                raw={},
            ),
            ListingIn(
                source="pytest",
                listing_id="market-b",
                seller_id="seller-b",
                title="【咸鱼之王】功法残卷 现货",
                description="现货秒发",
                list_price=6.0,
                listed_at=datetime(2026, 3, 29, 12, 10, tzinfo=timezone.utc),
                raw={},
            ),
            ListingIn(
                source="pytest",
                listing_id="market-noise",
                seller_id="seller-c",
                title="咸鱼之王金图鉴 全套礼包",
                description="礼包",
                list_price=10.0,
                listed_at=datetime(2026, 3, 29, 12, 20, tzinfo=timezone.utc),
                raw={},
            ),
        ]
    )

    snapshots = repo.get_normalized_market_snapshots(limit=10, listing_hours=24 * 30, sales_days=30)
    fragment = next(item for item in snapshots if item["normalized_key"] == "manual_fragment:功法残卷")

    assert fragment["open_listing_count"] == 2
    assert fragment["recent_sales_count_7d"] == 2
    assert fragment["noise_listing_count"] == 0
    assert fragment["seller_count"] == 2
    assert fragment["regime_tag"] in {"tradable", "wide", "overpriced"}
    assert "功法残卷" in fragment["summary_text"]
