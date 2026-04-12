from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import repositories as repo
from app.auth_utils import hash_password
from app.config import settings
from app.database import get_conn
from app.database import init_db
from app.main import create_app
from app.schemas import ListingIn, MarketplaceOfferIn, SaleIn, ValuationOut
import app.routers.marketplace as marketplace_router_module
import app.services.marketplace_jd as jd_module
import app.services.marketplace_pinduoduo as pdd_module


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user(username: str, password: str, role: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users (
                username,
                email,
                password_hash,
                nickname,
                role,
                is_active,
                is_seeded_admin,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                username,
                f"{username}@example.com",
                hash_password(password),
                username,
                role,
            ),
        )


def _seed_data() -> None:
    sold_base = datetime(2026, 4, 1, tzinfo=timezone.utc)
    repo.insert_sales(
        [
            SaleIn(
                source="pytest",
                item_id="sale-1",
                title="Blue-Eyes White Dragon",
                description="sold",
                sold_price=100.0,
                sold_at=sold_base,
                raw={},
            ),
            SaleIn(
                source="pytest",
                item_id="sale-2",
                title="Blue-Eyes White Dragon",
                description="sold",
                sold_price=120.0,
                sold_at=sold_base.replace(day=11),
                raw={},
            ),
            SaleIn(
                source="pytest",
                item_id="sale-3",
                title="Blue-Eyes White Dragon",
                description="sold",
                sold_price=110.0,
                sold_at=sold_base.replace(day=12),
                raw={},
            ),
        ]
    )

    listing_a = ListingIn(
        source="pytest",
        listing_id="listing-a",
        seller_id="seller-a",
        title="Card A",
        description="desc",
        list_price=80.0,
        listed_at=sold_base,
        status="open",
        raw={},
    )
    listing_b = ListingIn(
        source="pytest",
        listing_id="listing-b",
        seller_id="seller-b",
        title="Card B",
        description="desc",
        list_price=140.0,
        listed_at=sold_base,
        status="open",
        raw={},
    )
    listing_a_id, _ = repo.upsert_listing(listing_a)
    listing_b_id, _ = repo.upsert_listing(listing_b)
    assert listing_a_id is not None and listing_b_id is not None

    repo.insert_marketplace_offers(
        [
            MarketplaceOfferIn(
                platform="taobao",
                offer_id="tb-1",
                seller_id="seller-tb",
                title="Blue-Eyes White Dragon",
                canonical_key="blue-eyes white dragon",
                item_type="card",
                list_price=70.0,
                listed_at=sold_base,
                status="open",
                listing_url="https://example.com/tb-1",
                raw={},
            ),
            MarketplaceOfferIn(
                platform="jd",
                offer_id="jd-1",
                seller_id="seller-jd",
                title="Blue-Eyes White Dragon",
                canonical_key="blue-eyes white dragon",
                item_type="card",
                list_price=108.0,
                listed_at=sold_base,
                status="open",
                listing_url="https://example.com/jd-1",
                raw={},
            ),
        ]
    )

    valuation_a = repo.save_valuation(
        ValuationOut(
            listing_row_id=listing_a_id,
            expected_sale_price=130.0,
            buy_limit=90.0,
            suggested_list_price=135.0,
            ci_low=120.0,
            ci_high=140.0,
            model_confidence=0.9,
            comparables_count=12,
            reasoning="seed",
        )
    )
    valuation_b = repo.save_valuation(
        ValuationOut(
            listing_row_id=listing_b_id,
            expected_sale_price=150.0,
            buy_limit=95.0,
            suggested_list_price=155.0,
            ci_low=130.0,
            ci_high=170.0,
            model_confidence=0.7,
            comparables_count=8,
            reasoning="seed",
        )
    )
    opp_a = repo.upsert_opportunity(
        listing_row_id=listing_a_id,
        valuation_id=valuation_a,
        expected_profit=30.0,
        roi=0.375,
        score=75.0,
        status="pending_review",
        note="risk_score=20;risk_level=low;reasons=none",
    )
    repo.upsert_opportunity(
        listing_row_id=listing_b_id,
        valuation_id=valuation_b,
        expected_profit=5.0,
        roi=0.03,
        score=35.0,
        status="blocked_risk",
        note="risk_score=80;risk_level=high;reasons=list_price_above_buy_limit",
    )
    repo.approve_opportunity_idempotent(
        opportunity_id=opp_a,
        approved_buy_price=82.0,
        approved_by="pytest",
        note="seed trade",
    )


def test_analysis_endpoints(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "analysis_api.db"))
    try:
        init_db()
        _seed_data()
        with TestClient(create_app()) as client:
            price_history = client.get("/analysis/data/price-history", params={"limit": 5})
            assert price_history.status_code == 200
            history_payload = price_history.json()
            assert history_payload["count"] == 3

            trade_records = client.get("/analysis/data/trade-records")
            assert trade_records.status_code == 200
            assert trade_records.json()["count"] >= 1

            snapshot = client.get("/analysis/data/market-snapshot")
            assert snapshot.status_code == 200
            snapshot_payload = snapshot.json()
            assert "open_listing_count" in snapshot_payload
            assert "normalized_market_preview" in snapshot_payload
            assert "normalized_market_count" in snapshot_payload
            assert "tradable_market_preview" in snapshot_payload
            assert "tradable_market_count" in snapshot_payload
            assert "strategy_market_count" in snapshot_payload

            normalized_market = client.get("/analysis/data/normalized-market", params={"limit": 10})
            assert normalized_market.status_code == 200
            normalized_payload = normalized_market.json()
            assert "items" in normalized_payload
            assert "count" in normalized_payload
            assert normalized_payload["scope"] == "full"

            tradable_market_alias = client.get("/analysis/data/tradable-market", params={"limit": 10})
            assert tradable_market_alias.status_code == 200
            tradable_alias_payload = tradable_market_alias.json()
            assert tradable_alias_payload["scope"] == "tradable"

            tradable_market = client.get(
                "/analysis/data/normalized-market",
                params={"limit": 10, "scope": "tradable"},
            )
            assert tradable_market.status_code == 200
            tradable_payload = tradable_market.json()
            assert tradable_payload["scope"] == "tradable"
            assert all(item["is_tradable"] is True for item in tradable_payload["items"])
            assert tradable_payload == tradable_alias_payload

            calc = client.get("/analysis/calculation/overview")
            assert calc.status_code == 200
            calc_payload = calc.json()
            assert "trend_analysis" in calc_payload
            assert "volatility" in calc_payload
            assert "risk_assessment" in calc_payload
            assert "opportunity_identification" in calc_payload

            advanced_calc = client.get("/analysis/calculation/advanced")
            assert advanced_calc.status_code == 200
            advanced_payload = advanced_calc.json()
            assert "momentum" in advanced_payload
            assert "liquidity" in advanced_payload
            assert "anomaly_detection" in advanced_payload

            arbitrage_sources = client.get("/arbitrage/sources/health", params={"listing_hours": 24 * 30})
            assert arbitrage_sources.status_code == 200
            arbitrage_sources_payload = arbitrage_sources.json()
            assert arbitrage_sources_payload["count"] >= 2
            assert arbitrage_sources_payload["cross_source_products"] >= 1

            arbitrage_candidates = client.get(
                "/arbitrage/candidates",
                params={
                    "limit": 10,
                    "listing_hours": 24 * 30,
                    "min_distinct_sources": 2,
                    "min_expected_profit": 0,
                    "min_roi": 0,
                },
            )
            assert arbitrage_candidates.status_code == 200
            arbitrage_payload = arbitrage_candidates.json()
            assert arbitrage_payload["count"] >= 1
            candidate = arbitrage_payload["items"][0]
            assert candidate["buy_source"] == "taobao"
            assert candidate["sell_source"] == "jd"
            assert candidate["expected_profit"] > 0
            assert candidate["source_count"] >= 2

            decision = client.get("/analysis/decision/overview")
            assert decision.status_code == 200
            decision_payload = decision.json()
            assert "buy_sell_signals" in decision_payload
            assert "pricing_suggestions" in decision_payload
            assert "risk_alerts" in decision_payload
            assert len(decision_payload["risk_alerts"]) >= 1

            market_docs = client.get(
                "/analysis/decision/market-docs",
                params={"limit": 5, "listing_hours": 24 * 30, "sales_days": 30, "scope": "full"},
            )
            assert market_docs.status_code == 200
            market_docs_payload = market_docs.json()
            assert market_docs_payload["count"] >= 1
            assert market_docs_payload["scope"] == "full"
            assert "filename" in market_docs_payload["items"][0]
            assert "content" in market_docs_payload["items"][0]

            strategy = client.get(
                "/analysis/decision/strategy-proposal",
                params={"limit": 5, "listing_hours": 24 * 30, "sales_days": 30},
            )
            assert strategy.status_code == 200
            strategy_payload = strategy.json()
            assert "available" in strategy_payload
            assert "snapshots" in strategy_payload
            assert "prompt" in strategy_payload
            assert all(item["is_tradable"] is True for item in strategy_payload["snapshots"])

            auto_reco = client.get("/analysis/automation/recommendation")
            assert auto_reco.status_code == 200
            auto_reco_payload = auto_reco.json()
            assert "allow_run_once" in auto_reco_payload
            assert "suggested_autotrade_limit" in auto_reco_payload
            assert "autotrade_status" in auto_reco_payload

            auto_run = client.post(
                "/analysis/automation/run-once",
                params={"force": True, "limit": 5},
            )
            assert auto_run.status_code == 200
            auto_run_payload = auto_run.json()
            assert "recommendation" in auto_run_payload
            assert "result" in auto_run_payload

            report = client.get("/analysis/report")
            assert report.status_code == 200
            report_payload = report.json()
            assert "data_layer" in report_payload
            assert "calculation_layer" in report_payload
            assert "advanced_calculation_layer" in report_payload
            assert "decision_layer" in report_payload
            assert "automation_layer" in report_payload
            assert "report_text" in report_payload

            stream = client.get(
                "/analysis/stream",
                params={"interval_seconds": 0, "max_events": 2},
                headers={"accept": "text/event-stream"},
            )
            assert stream.status_code == 200
            assert "text/event-stream" in stream.headers.get("content-type", "")
            assert "data:" in stream.text
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_admin_overview_requires_admin_auth(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    old_username = settings.ui_auth_username
    old_password = settings.ui_auth_password
    old_nickname = settings.ui_auth_nickname
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "analysis_admin.db"))
    object.__setattr__(settings, "ui_auth_username", "admin")
    object.__setattr__(settings, "ui_auth_password", "admin123456")
    object.__setattr__(settings, "ui_auth_nickname", "Analysis Admin")
    try:
        init_db()
        _seed_data()
        _create_user("viewer_user", "secret123", "viewer")
        with TestClient(create_app()) as client:
            anonymous = client.get("/analysis/admin-overview")
            assert anonymous.status_code == 401

            user_login = client.post(
                "/auth/login",
                json={"username": "viewer_user", "password": "secret123"},
            )
            assert user_login.status_code == 200
            user_token = user_login.json()["data"]["token"]

            forbidden = client.get(
                "/analysis/admin-overview",
                headers=_bearer(user_token),
            )
            assert forbidden.status_code == 403

            admin_login = client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin123456"},
            )
            assert admin_login.status_code == 200
            admin_token = admin_login.json()["data"]["token"]

            overview = client.get(
                "/analysis/admin-overview",
                headers=_bearer(admin_token),
            )
            assert overview.status_code == 200
            payload = overview.json()
            assert payload["viewer"]["isAdmin"] is True
            assert "profitability" in payload
            assert "runtime" in payload
            assert "alerts" in payload
            assert payload["runtime"]["services"]["autotrade"]["enabled"] in {True, False}
            assert "profit_cockpit" in payload["profitability"]
            assert payload["runtime"]["operating_profile"]["mode"] in {
                "single-account-local",
                "standard",
            }
            assert "operating_profile" in payload["deployment_readiness"]
            assert "validation_baseline" in payload["runtime"]["services"]["autotrade"]
            assert "validation_baseline" in payload["deployment_readiness"]
            assert payload["deployment_readiness"]["validation_baseline"]["ready_for_scale"] in {
                True,
                False,
            }
            assert "snapshot_history" in payload["deployment_readiness"]["validation_baseline"]

            stream = client.get(
                "/analysis/admin-overview/stream",
                params={"interval_seconds": 0, "max_events": 1},
                headers={
                    **_bearer(admin_token),
                    "accept": "text/event-stream",
                },
            )
            assert stream.status_code == 200
            assert "text/event-stream" in stream.headers.get("content-type", "")
            assert "event: overview" in stream.text
            assert '"profitability"' in stream.text
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
        object.__setattr__(settings, "ui_auth_username", old_username)
        object.__setattr__(settings, "ui_auth_password", old_password)
        object.__setattr__(settings, "ui_auth_nickname", old_nickname)


def test_opportunities_route_excludes_simulation_by_default(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "opportunities_api.db"))
    try:
        init_db()
        _seed_data()

        listed_at = datetime(2026, 3, 13, tzinfo=timezone.utc)
        listing_row_id, _ = repo.upsert_listing(
            ListingIn(
                source="simulation_seed",
                listing_id="sim-1",
                seller_id="sim-seller-1",
                title="Simulation Only Card",
                description="seed",
                list_price=66.0,
                listed_at=listed_at,
                status="open",
                raw={},
            )
        )
        assert listing_row_id is not None
        valuation_id = repo.save_valuation(
            ValuationOut(
                listing_row_id=listing_row_id,
                expected_sale_price=99.0,
                buy_limit=75.0,
                suggested_list_price=105.0,
                ci_low=92.0,
                ci_high=111.0,
                model_confidence=0.95,
                comparables_count=10,
                reasoning="simulation",
            )
        )
        repo.upsert_opportunity(
            listing_row_id=listing_row_id,
            valuation_id=valuation_id,
            expected_profit=21.0,
            roi=0.31,
            score=91.0,
            status="pending_review",
            note="simulation_seed;risk_score=0;risk_level=low;reasons=none",
        )

        real_listing_row_id, _ = repo.upsert_listing(
            ListingIn(
                source="xianyu_monitor",
                listing_id="real-1",
                seller_id="real-seller-1",
                title="Real Pending Card",
                description="real seed",
                list_price=72.0,
                listed_at=listed_at,
                status="open",
                raw={},
            )
        )
        assert real_listing_row_id is not None
        real_valuation_id = repo.save_valuation(
            ValuationOut(
                listing_row_id=real_listing_row_id,
                expected_sale_price=121.0,
                buy_limit=84.0,
                suggested_list_price=128.0,
                ci_low=112.0,
                ci_high=136.0,
                model_confidence=0.89,
                comparables_count=11,
                reasoning="real",
            )
        )
        repo.upsert_opportunity(
            listing_row_id=real_listing_row_id,
            valuation_id=real_valuation_id,
            expected_profit=33.0,
            roi=0.45,
            score=87.0,
            status="pending_review",
            note="risk_score=12;risk_level=low;reasons=none",
        )

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            pending = client.get(
                "/opportunities",
                params={"status": "pending_review", "limit": 10},
                headers=_bearer(admin_token),
            )
            assert pending.status_code == 200
            pending_items = pending.json()["items"]
            assert len(pending_items) == 1
            assert pending_items[0]["source"] == "xianyu_monitor"
            assert pending_items[0]["listing_id"] == "real-1"

            with_simulation = client.get(
                "/opportunities",
                params={"status": "pending_review", "limit": 10, "include_simulation": True},
                headers=_bearer(admin_token),
            )
            assert with_simulation.status_code == 200
            sources = {item["source"] for item in with_simulation.json()["items"]}
            assert "xianyu_monitor" in sources
            assert "simulation_seed" in sources
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_simulation_cleanup_archives_seed_data(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "simulation_cleanup.db"))
    try:
        init_db()

        listed_at = datetime(2026, 3, 13, tzinfo=timezone.utc)
        listing_row_id, _ = repo.upsert_listing(
            ListingIn(
                source="simulation_seed",
                listing_id="sim-cleanup-1",
                seller_id="sim-cleanup-seller",
                title="Simulation Cleanup Card",
                description="cleanup",
                list_price=55.0,
                listed_at=listed_at,
                status="open",
                raw={},
            )
        )
        assert listing_row_id is not None
        valuation_id = repo.save_valuation(
            ValuationOut(
                listing_row_id=listing_row_id,
                expected_sale_price=88.0,
                buy_limit=66.0,
                suggested_list_price=92.0,
                ci_low=81.0,
                ci_high=96.0,
                model_confidence=0.9,
                comparables_count=9,
                reasoning="cleanup",
            )
        )
        repo.upsert_opportunity(
            listing_row_id=listing_row_id,
            valuation_id=valuation_id,
            expected_profit=18.0,
            roi=0.32,
            score=82.0,
            status="pending_review",
            note="simulation_seed;risk_score=0;risk_level=low;reasons=none",
        )

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            cleanup = client.post(
                "/automation/simulation-cleanup",
                headers=_bearer(admin_token),
            )
            assert cleanup.status_code == 200
            payload = cleanup.json()
            assert payload["simulation_listing_count"] == 1
            assert payload["archived_listing_count"] == 1
            assert payload["pending_review_rejected_count"] == 1
            assert payload["updated_opportunity_count"] == 1

        with get_conn() as conn:
            listing_status = conn.execute(
                "SELECT status FROM listings_raw WHERE listing_id = ?",
                ("sim-cleanup-1",),
            ).fetchone()["status"]
            opportunity_status = conn.execute(
                """
                SELECT o.status
                FROM opportunities o
                JOIN listings_raw l ON l.id = o.listing_row_id
                WHERE l.listing_id = ?
                """,
                ("sim-cleanup-1",),
            ).fetchone()["status"]
        assert listing_status == "archived"
        assert opportunity_status == "rejected"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_arbitrage_opportunities_report_cross_source_spread(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "arbitrage_api.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu_monitor",
                    offer_id="xy-1",
                    seller_id="xianyu_monitor-seller",
                    title="PSA 10 Pikachu Promo",
                    canonical_key="psa 10 pikachu promo",
                    item_type="card",
                    list_price=80.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-1",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="taobao",
                    offer_id="tb-1",
                    seller_id="taobao-seller",
                    title="PSA 10 Pikachu Promo",
                    canonical_key="psa 10 pikachu promo",
                    item_type="card",
                    list_price=118.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/tb-1",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="jd",
                    offer_id="jd-1",
                    seller_id="jd-seller",
                    title="PSA 10 Pikachu Promo",
                    canonical_key="psa 10 pikachu promo",
                    item_type="card",
                    list_price=109.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/jd-1",
                    raw={},
                ),
            ]
        )

        with TestClient(create_app()) as client:
            response = client.get(
                "/analysis/arbitrage/opportunities",
                params={
                    "limit": 5,
                    "window_hours": 72,
                    "min_platforms": 2,
                    "buy_fee_rate": 0.0,
                    "sell_fee_rate": 0.0,
                    "shipping_cost": 0.0,
                },
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["summary"]["scanned_listing_count"] == 3
            assert payload["summary"]["opportunity_count"] >= 1
            item = payload["items"][0]
            assert item["buy"]["source"] == "xianyu"
            assert item["sell"]["source"] == "taobao"
            assert item["gross_spread"] == 38.0
            assert item["estimated_net_profit"] == 38.0
            assert item["source_count"] == 3
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_marketplace_offer_import_and_arbitrage_candidates(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "marketplace_offers.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            payload = [
                MarketplaceOfferIn(
                    platform="taobao",
                    offer_id="tb-sku-1",
                    seller_id="tb-seller",
                    title="Nintendo Switch OLED White",
                    canonical_key="nintendo switch oled white",
                    item_type="console",
                    list_price=1799,
                    shipping_cost=0,
                    fee_rate=0.0,
                    currency="CNY",
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/tb-sku-1",
                    raw={},
                ).model_dump(mode="json"),
                MarketplaceOfferIn(
                    platform="jd",
                    offer_id="jd-sku-1",
                    seller_id="jd-seller",
                    title="Nintendo Switch OLED White",
                    canonical_key="nintendo switch oled white",
                    item_type="console",
                    list_price=2099,
                    shipping_cost=0,
                    fee_rate=0.0,
                    currency="CNY",
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/jd-sku-1",
                    raw={},
                ).model_dump(mode="json"),
            ]
            imported = client.post(
                "/arbitrage/offers/import",
                json=payload,
                headers=_bearer(admin_token),
            )
            assert imported.status_code == 200
            assert imported.json()["inserted"] == 2

            offers = client.get("/arbitrage/offers", headers=_bearer(admin_token))
            assert offers.status_code == 200
            assert offers.json()["count"] == 2

            candidates = client.get(
                "/arbitrage/candidates",
                params={"limit": 10, "listing_hours": 72, "min_distinct_sources": 2},
                headers=_bearer(admin_token),
            )
            assert candidates.status_code == 200
            candidates_payload = candidates.json()
            assert candidates_payload["count"] >= 1
            assert candidates_payload["assumptions"]["data_mode"] == "marketplace_offers"
            first = candidates_payload["items"][0]
            assert first["buy_source"] == "taobao"
            assert first["sell_source"] == "jd"
            assert first["expected_profit"] > 0
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_marketplace_backfill_from_xianyu_listings(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "marketplace_backfill.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.upsert_listing(
            ListingIn(
                source="xianyu_monitor",
                listing_id="xy-backfill-1",
                seller_id="xy-seller",
                title="PSA 10 Charizard",
                description="real xianyu source",
                list_price=1888.0,
                listed_at=listed_at,
                status="open",
                raw={},
            )
        )
        repo.upsert_listing(
            ListingIn(
                source="xianyu_monitor",
                listing_id="xy-backfill-virtual-1",
                seller_id="xy-seller-virtual",
                title="咸鱼之王功法卡 虚拟道具 游戏内直接交易 秒发 售出不退",
                description="虚拟商品，拍下发区服和ID",
                list_price=6.0,
                listed_at=listed_at,
                status="open",
                raw={},
            )
        )
        repo.upsert_listing(
            ListingIn(
                source="xianyu_vnpy",
                listing_id="xy-backfill-vnpy-1",
                seller_id="xy-seller-vnpy",
                title="Q coin auto recharge instant delivery",
                description="vnpy xianyu collector path",
                list_price=48.0,
                listed_at=listed_at,
                status="open",
                raw={},
            )
        )
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE listings_raw
                SET item_type = 'manual_card',
                    normalized_key = 'manual_card:legacy',
                    normalized_title = 'legacy'
                WHERE listing_id = 'xy-backfill-virtual-1'
                """
            )

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            backfill = client.post(
                "/marketplace/offers/backfill",
                params={"sources": "xianyu_monitor,xianyu_vnpy", "limit": 20, "listing_hours": 72},
                headers=_bearer(admin_token),
            )
            assert backfill.status_code == 200
            assert backfill.json()["inserted"] == 3

            offers = client.get("/marketplace/offers", headers=_bearer(admin_token))
            assert offers.status_code == 200
            offers_payload = offers.json()
            assert offers_payload["count"] == 3
            assert {item["platform"] for item in offers_payload["items"]} == {"xianyu"}
            virtual_offer = next(item for item in offers_payload["items"] if item["offer_id"] == "xy-backfill-virtual-1")
            assert virtual_offer["item_type"] == "virtual_goods"

            readiness = client.get("/marketplace/providers/status", headers=_bearer(admin_token))
            assert readiness.status_code == 200
            readiness_payload = readiness.json()["items"]
            xianyu_row = next(item for item in readiness_payload if item["provider"] == "xianyu")
            assert xianyu_row["offer_count"] == 3
            assert xianyu_row["legacy_open_listing_count"] >= 2
            assert xianyu_row["backfill_ready"] is True
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_taobao_snapshot_ingest_creates_arbitrage_candidate(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "taobao_snapshot.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-snapshot-1",
                    seller_id="xy-seller",
                    title="Pokemon Card Charizard PSA 10",
                    canonical_key="pokemon card charizard psa 10",
                    item_type="card",
                    list_price=1888.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-snapshot-1",
                    raw={},
                )
            ]
        )

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            snapshot = {
                "items": [
                    {
                        "num_iid": "tb-snapshot-1",
                        "title": "Pokemon Card Charizard PSA 10",
                        "seller_id": "tb-seller",
                        "price": 2388.0,
                        "item_url": "https://example.com/tb-snapshot-1",
                        "listed_at": listed_at.isoformat(),
                    }
                ]
            }
            ingested = client.post(
                "/marketplace/providers/taobao/ingest-snapshot",
                json=snapshot,
                headers=_bearer(admin_token),
            )
            assert ingested.status_code == 200
            ingest_payload = ingested.json()
            assert ingest_payload["count"] == 1
            assert ingest_payload["inserted"] == 1

            candidates = client.get(
                "/analysis/arbitrage/opportunities",
                params={"limit": 5, "window_hours": 72, "min_platforms": 2},
                headers=_bearer(admin_token),
            )
            assert candidates.status_code == 200
            payload = candidates.json()
            assert payload["summary"]["opportunity_count"] >= 1
            first = payload["items"][0]
            assert first["buy_source"] == "xianyu"
            assert first["sell_source"] == "taobao"
            assert first["estimated_net_profit"] > 0
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_taobao_sync_once_route_ingests_marketplace_offers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "taobao_sync_once.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-sync-1",
                    seller_id="xy-seller",
                    title="Pokemon Card Venusaur PSA 10",
                    canonical_key="pokemon card venusaur psa 10",
                    item_type="card",
                    list_price=1288.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-sync-1",
                    raw={},
                )
            ]
        )

        def _fake_sync_once(*, query_string_override: str = ""):
            rows = [
                MarketplaceOfferIn(
                    platform="taobao",
                    offer_id="tb-sync-1",
                    seller_id="tb-seller",
                    title="Pokemon Card Venusaur PSA 10",
                    canonical_key="pokemon card venusaur psa 10",
                    item_type="card",
                    list_price=1688.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/tb-sync-1",
                    raw={"query_string_override": query_string_override},
                )
            ]
            return {"count": 1, "rows": rows, "raw": {"ok": True}}

        monkeypatch.setattr(marketplace_router_module.taobao_top_client, "sync_once", _fake_sync_once)

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            sync_resp = client.post(
                "/marketplace/providers/taobao/sync-once",
                headers=_bearer(admin_token),
            )
            assert sync_resp.status_code == 200
            payload = sync_resp.json()
            assert payload["count"] == 1
            assert payload["inserted"] == 1

            arbitrage = client.get(
                "/analysis/arbitrage/opportunities",
                params={"limit": 5, "window_hours": 72, "min_platforms": 2},
                headers=_bearer(admin_token),
            )
            assert arbitrage.status_code == 200
            items = arbitrage.json()["items"]
            assert len(items) >= 1
            assert items[0]["buy_source"] == "xianyu"
            assert items[0]["sell_source"] == "taobao"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_pinduoduo_snapshot_ingest_creates_arbitrage_candidate(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "pinduoduo_snapshot.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-pdd-snapshot-1",
                    seller_id="xy-seller",
                    title="Pokemon Card Blastoise PSA 10",
                    canonical_key="pokemon card blastoise psa 10",
                    item_type="card",
                    list_price=1588.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-pdd-snapshot-1",
                    raw={},
                )
            ]
        )

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            snapshot = {
                "goods_search_response": {
                    "goods_list": [
                        {
                            "goods_id": "pdd-snapshot-1",
                            "goods_name": "Pokemon Card Blastoise PSA 10",
                            "mall_id": "pdd-mall",
                            "min_group_price": 198800,
                            "goods_link": "https://example.com/pdd-snapshot-1",
                            "listed_at": listed_at.isoformat(),
                        }
                    ]
                }
            }
            ingested = client.post(
                "/marketplace/providers/pinduoduo/ingest-snapshot",
                json=snapshot,
                headers=_bearer(admin_token),
            )
            assert ingested.status_code == 200
            ingest_payload = ingested.json()
            assert ingest_payload["count"] == 1
            assert ingest_payload["inserted"] == 1

            candidates = client.get(
                "/analysis/arbitrage/opportunities",
                params={"limit": 5, "window_hours": 72, "min_platforms": 2},
                headers=_bearer(admin_token),
            )
            assert candidates.status_code == 200
            payload = candidates.json()
            assert payload["summary"]["opportunity_count"] >= 1
            first = payload["items"][0]
            assert first["buy_source"] == "xianyu"
            assert first["sell_source"] == "pinduoduo"
            assert first["estimated_net_profit"] > 0
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_pinduoduo_virtual_goods_snapshot_ingest_supports_virtual_only_arbitrage(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "pinduoduo_virtual_snapshot.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-virtual-1",
                    seller_id="xy-seller",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=45.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-virtual-1",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-physical-1",
                    seller_id="xy-seller",
                    title="Plastic toy coin prop set",
                    canonical_key="plastic toy coin prop set",
                    item_type="generic",
                    list_price=8.0,
                    shipping_cost=8.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-physical-1",
                    raw={},
                ),
            ]
        )

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            snapshot = {
                "goods_search_response": {
                    "goods_list": [
                        {
                            "goods_id": "pdd-virtual-1",
                            "goods_name": "Q coin auto recharge instant delivery direct topup",
                            "mall_id": "pdd-mall",
                            "min_group_price": 6500,
                            "goods_link": "https://example.com/pdd-virtual-1",
                            "listed_at": listed_at.isoformat(),
                            "item_type": "virtual_goods",
                            "fulfillment_mode": "virtual",
                            "shipping_cost": 12.0,
                        },
                        {
                            "goods_id": "pdd-physical-1",
                            "goods_name": "Plastic toy coin prop set",
                            "mall_id": "pdd-mall",
                            "min_group_price": 888,
                            "goods_link": "https://example.com/pdd-physical-1",
                            "listed_at": listed_at.isoformat(),
                            "item_type": "generic",
                            "fulfillment_mode": "physical",
                            "shipping_cost": 12.0,
                        },
                    ]
                }
            }
            ingested = client.post(
                "/marketplace/providers/pinduoduo/ingest-snapshot",
                json=snapshot,
                headers=_bearer(admin_token),
            )
            assert ingested.status_code == 200
            assert ingested.json()["count"] == 2

            offers = repo.list_marketplace_offers(platform="pinduoduo", limit=10)
            virtual_offer = next(row for row in offers if str(row["offer_id"]) == "pdd-virtual-1")
            physical_offer = next(row for row in offers if str(row["offer_id"]) == "pdd-physical-1")
            assert str(virtual_offer["item_type"]) == "virtual_goods"
            assert float(virtual_offer["shipping_cost"] or 0.0) == 0.0
            assert str(physical_offer["item_type"]) == "generic"

            candidates = client.get(
                "/analysis/arbitrage/opportunities",
                params={
                    "limit": 5,
                    "window_hours": 72,
                    "min_platforms": 2,
                    "virtual_only": True,
                    "shipping_cost": 0.0,
                },
                headers=_bearer(admin_token),
            )
            assert candidates.status_code == 200
            payload = candidates.json()
            assert payload["assumptions"]["virtual_only"] is True
            assert payload["summary"]["opportunity_count"] >= 1
            first = payload["items"][0]
            assert first["item_type"] == "virtual_goods"
            assert first["buy_source"] == "xianyu"
            assert first["sell_source"] == "pinduoduo"

            preview = client.get(
                "/analysis/arbitrage/matching-preview",
                params={"limit": 5, "window_hours": 72, "virtual_only": True},
                headers=_bearer(admin_token),
            )
            assert preview.status_code == 200
            preview_payload = preview.json()
            assert preview_payload["virtual_only"] is True
            assert preview_payload["count"] >= 1
            assert all(offer["item_type"] == "virtual_goods" for offer in preview_payload["items"][0]["offers"])
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_pinduoduo_sync_once_route_ingests_marketplace_offers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "pinduoduo_sync_once.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-pdd-sync-1",
                    seller_id="xy-seller",
                    title="Pokemon Card Mewtwo PSA 10",
                    canonical_key="pokemon card mewtwo psa 10",
                    item_type="card",
                    list_price=1188.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-pdd-sync-1",
                    raw={},
                )
            ]
        )

        def _fake_sync_once(*, params_json_override: str = "", snapshot_provider_url_override: str = ""):
            rows = [
                MarketplaceOfferIn(
                    platform="pinduoduo",
                    offer_id="pdd-sync-1",
                    seller_id="pdd-seller",
                    title="Pokemon Card Mewtwo PSA 10",
                    canonical_key="pokemon card mewtwo psa 10",
                    item_type="card",
                    list_price=1499.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/pdd-sync-1",
                        raw={
                            "params_json_override": params_json_override,
                            "snapshot_provider_url_override": snapshot_provider_url_override,
                        },
                    )
                ]
            return {"count": 1, "rows": rows, "raw": {"ok": True}}

        monkeypatch.setattr(marketplace_router_module.pinduoduo_open_client, "sync_once", _fake_sync_once)

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            sync_resp = client.post(
                "/marketplace/providers/pinduoduo/sync-once",
                headers=_bearer(admin_token),
            )
            assert sync_resp.status_code == 200
            payload = sync_resp.json()
            assert payload["count"] == 1
            assert payload["inserted"] == 1

            arbitrage = client.get(
                "/analysis/arbitrage/opportunities",
                params={"limit": 5, "window_hours": 72, "min_platforms": 2},
                headers=_bearer(admin_token),
            )
            assert arbitrage.status_code == 200
            items = arbitrage.json()["items"]
            assert len(items) >= 1
            assert items[0]["buy_source"] == "xianyu"
            assert items[0]["sell_source"] == "pinduoduo"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_jd_snapshot_ingest_creates_arbitrage_candidate(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "jd_snapshot.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-jd-snapshot-1",
                    seller_id="xy-seller",
                    title="Pokemon Card Lugia PSA 10",
                    canonical_key="pokemon card lugia psa 10",
                    item_type="card",
                    list_price=2688.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-jd-snapshot-1",
                    raw={},
                )
            ]
        )

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            snapshot = {
                "jd_union_open_goods_query_response": {
                    "queryResult": {
                        "goodsList": [
                            {
                                "skuId": "jd-snapshot-1",
                                "skuName": "Pokemon Card Lugia PSA 10",
                                "owner": "jd-shop",
                                "price": 3188.0,
                                "materialUrl": "https://example.com/jd-snapshot-1",
                                "listed_at": listed_at.isoformat(),
                            }
                        ]
                    }
                }
            }
            ingested = client.post(
                "/marketplace/providers/jd/ingest-snapshot",
                json=snapshot,
                headers=_bearer(admin_token),
            )
            assert ingested.status_code == 200
            ingest_payload = ingested.json()
            assert ingest_payload["count"] == 1
            assert ingest_payload["inserted"] == 1

            candidates = client.get(
                "/analysis/arbitrage/opportunities",
                params={"limit": 5, "window_hours": 72, "min_platforms": 2},
                headers=_bearer(admin_token),
            )
            assert candidates.status_code == 200
            payload = candidates.json()
            assert payload["summary"]["opportunity_count"] >= 1
            first = payload["items"][0]
            assert first["buy_source"] == "xianyu"
            assert first["sell_source"] == "jd"
            assert first["estimated_net_profit"] > 0
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_jd_virtual_goods_snapshot_ingest_supports_virtual_only_arbitrage(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "jd_virtual_snapshot.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-jd-virtual-1",
                    seller_id="xy-seller",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=45.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-jd-virtual-1",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-jd-physical-1",
                    seller_id="xy-seller",
                    title="Plastic toy coin prop set",
                    canonical_key="plastic toy coin prop set",
                    item_type="generic",
                    list_price=8.0,
                    shipping_cost=8.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-jd-physical-1",
                    raw={},
                ),
            ]
        )

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            snapshot = {
                "jd_union_open_goods_query_response": {
                    "queryResult": {
                        "goodsList": [
                            {
                                "skuId": "jd-virtual-1",
                                "skuName": "Q coin auto recharge instant delivery direct topup",
                                "owner": "jd-shop",
                                "price": 65.0,
                                "materialUrl": "https://example.com/jd-virtual-1",
                                "listed_at": listed_at.isoformat(),
                                "item_type": "virtual_goods",
                                "fulfillment_mode": "virtual",
                                "shipping_cost": 12.0,
                            },
                            {
                                "skuId": "jd-physical-1",
                                "skuName": "Plastic toy coin prop set",
                                "owner": "jd-shop",
                                "price": 8.88,
                                "materialUrl": "https://example.com/jd-physical-1",
                                "listed_at": listed_at.isoformat(),
                                "item_type": "generic",
                                "fulfillment_mode": "physical",
                                "shipping_cost": 12.0,
                            },
                        ]
                    }
                }
            }
            ingested = client.post(
                "/marketplace/providers/jd/ingest-snapshot",
                json=snapshot,
                headers=_bearer(admin_token),
            )
            assert ingested.status_code == 200
            assert ingested.json()["count"] == 2

            offers = repo.list_marketplace_offers(platform="jd", limit=10)
            virtual_offer = next(row for row in offers if str(row["offer_id"]) == "jd-virtual-1")
            physical_offer = next(row for row in offers if str(row["offer_id"]) == "jd-physical-1")
            assert str(virtual_offer["item_type"]) == "virtual_goods"
            assert float(virtual_offer["shipping_cost"] or 0.0) == 0.0
            assert str(physical_offer["item_type"]) == "generic"

            candidates = client.get(
                "/analysis/arbitrage/opportunities",
                params={
                    "limit": 5,
                    "window_hours": 72,
                    "min_platforms": 2,
                    "virtual_only": True,
                    "shipping_cost": 0.0,
                },
                headers=_bearer(admin_token),
            )
            assert candidates.status_code == 200
            payload = candidates.json()
            assert payload["assumptions"]["virtual_only"] is True
            assert payload["summary"]["opportunity_count"] >= 1
            first = payload["items"][0]
            assert first["item_type"] == "virtual_goods"
            assert first["buy_source"] == "xianyu"
            assert first["sell_source"] == "jd"

            preview = client.get(
                "/analysis/arbitrage/matching-preview",
                params={"limit": 5, "window_hours": 72, "virtual_only": True},
                headers=_bearer(admin_token),
            )
            assert preview.status_code == 200
            preview_payload = preview.json()
            assert preview_payload["virtual_only"] is True
            assert preview_payload["count"] >= 1
            assert all(offer["item_type"] == "virtual_goods" for offer in preview_payload["items"][0]["offers"])
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_jd_sync_once_route_ingests_marketplace_offers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "jd_sync_once.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-jd-sync-1",
                    seller_id="xy-seller",
                    title="Pokemon Card Ho-Oh PSA 10",
                    canonical_key="pokemon card ho-oh psa 10",
                    item_type="card",
                    list_price=2188.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-jd-sync-1",
                    raw={},
                )
            ]
        )

        def _fake_sync_once(*, param_json_override: str = "", snapshot_provider_url_override: str = ""):
            rows = [
                MarketplaceOfferIn(
                    platform="jd",
                    offer_id="jd-sync-1",
                    seller_id="jd-seller",
                    title="Pokemon Card Ho-Oh PSA 10",
                    canonical_key="pokemon card ho-oh psa 10",
                    item_type="card",
                    list_price=2599.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/jd-sync-1",
                        raw={
                            "param_json_override": param_json_override,
                            "snapshot_provider_url_override": snapshot_provider_url_override,
                        },
                    )
                ]
            return {"count": 1, "rows": rows, "raw": {"ok": True}}

        monkeypatch.setattr(marketplace_router_module.jd_open_client, "sync_once", _fake_sync_once)

        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            sync_resp = client.post(
                "/marketplace/providers/jd/sync-once",
                headers=_bearer(admin_token),
            )
            assert sync_resp.status_code == 200
            payload = sync_resp.json()
            assert payload["count"] == 1
            assert payload["inserted"] == 1

            arbitrage = client.get(
                "/analysis/arbitrage/opportunities",
                params={"limit": 5, "window_hours": 72, "min_platforms": 2},
                headers=_bearer(admin_token),
            )
            assert arbitrage.status_code == 200
            items = arbitrage.json()["items"]
            assert len(items) >= 1
            assert items[0]["buy_source"] == "xianyu"
            assert items[0]["sell_source"] == "jd"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_arbitrage_matching_preview_explains_single_platform_group(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "matching_preview.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-match-1",
                    seller_id="xy-seller",
                    title="Pokemon Card Rayquaza PSA 10",
                    canonical_key="pokemon card rayquaza psa 10",
                    item_type="card",
                    list_price=1999.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-match-1",
                    raw={},
                )
            ]
        )
        with TestClient(create_app()) as client:
            response = client.get(
                "/analysis/arbitrage/matching-preview",
                params={"limit": 5, "window_hours": 72},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["count"] >= 1
            first = payload["items"][0]
            assert first["status"] == "single_platform_only"
            assert first["source_count"] == 1
            assert "Only one platform" in first["reason"]
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_marketplace_normalizer_groups_title_variants_into_one_match(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "matching_variants.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-variant-1",
                    seller_id="xy-seller",
                    title="Pokemon Card Charizard PSA10 现货",
                    canonical_key="",
                    item_type="card",
                    list_price=1888.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-variant-1",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="taobao",
                    offer_id="tb-variant-1",
                    seller_id="tb-seller",
                    title="Pokemon Card Charizard PSA 10 官方旗舰店",
                    canonical_key="",
                    item_type="card",
                    list_price=2388.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/tb-variant-1",
                    raw={},
                ),
            ]
        )
        rows = repo.list_marketplace_offers(limit=10)
        assert len(rows) == 2
        keys = {str(row["canonical_key"] or "").strip() for row in rows}
        assert len(keys) == 1
        assert "pokemon card charizard psa 10" in keys
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_arbitrage_validate_match_endpoint_explains_verdict(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "validate_match.db"))
    try:
        init_db()
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            response = client.post(
                "/analysis/arbitrage/validate-match",
                json={
                    "left_title": "Pokemon Card Charizard PSA10 现货",
                    "right_title": "Pokemon Card Charizard PSA 10 官方旗舰店",
                },
                headers=_bearer(admin_token),
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["left_canonical_key"] == "pokemon card charizard psa 10"
            assert payload["right_canonical_key"] == "pokemon card charizard psa 10"
            assert payload["exact_match"] is True
            assert payload["verdict"] == "same_group"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_arbitrage_validate_batch_endpoint(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "validate_batch.db"))
    try:
        init_db()
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            response = client.post(
                "/analysis/arbitrage/validate-batch",
                json=[
                    {
                        "left_title": "Pokemon Card Charizard PSA10 现货",
                        "right_title": "Pokemon Card Charizard PSA 10 官方旗舰店",
                    },
                    {
                        "left_title": "Pokemon Card Mewtwo PSA 10",
                        "right_title": "Pokemon Card Lugia PSA 10",
                    },
                ],
                headers=_bearer(admin_token),
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["count"] == 2
            assert len(payload["items"]) == 2
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_arbitrage_match_samples_crud(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "match_samples.db"))
    try:
        init_db()
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            created = client.post(
                "/analysis/arbitrage/match-samples",
                json={
                    "left_title": "Pokemon Card Charizard PSA10 现货",
                    "right_title": "Pokemon Card Charizard PSA 10 官方旗舰店",
                    "expected_verdict": "same_group",
                    "note": "charizard psa variant",
                },
                headers=_bearer(admin_token),
            )
            assert created.status_code == 200
            created_payload = created.json()
            assert created_payload["id"] >= 1
            assert created_payload["expected_verdict"] == "same_group"
            assert created_payload["result"]["verdict"] == "same_group"

            listed = client.get(
                "/analysis/arbitrage/match-samples",
                headers=_bearer(admin_token),
            )
            assert listed.status_code == 200
            listed_payload = listed.json()
            assert listed_payload["count"] >= 1
            assert listed_payload["items"][0]["result"]["verdict"] == "same_group"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_arbitrage_match_sample_report(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "match_sample_report.db"))
    try:
        init_db()
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            for payload in [
                {
                    "left_title": "Pokemon Card Charizard PSA10 现货",
                    "right_title": "Pokemon Card Charizard PSA 10 官方旗舰店",
                    "expected_verdict": "same_group",
                },
                {
                    "left_title": "Pokemon Card Mewtwo PSA 10",
                    "right_title": "Pokemon Card Lugia PSA 10",
                    "expected_verdict": "different_group",
                },
            ]:
                created = client.post(
                    "/analysis/arbitrage/match-samples",
                    json=payload,
                    headers=_bearer(admin_token),
                )
                assert created.status_code == 200

            report = client.get(
                "/analysis/arbitrage/match-samples/report",
                headers=_bearer(admin_token),
            )
            assert report.status_code == 200
            report_payload = report.json()
            assert report_payload["summary"]["total_samples"] >= 2
            assert report_payload["summary"]["scored_samples"] >= 2
            assert "actual_distribution" in report_payload
            assert "gate" in report_payload
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_arbitrage_review_queue_lists_high_similarity_candidates(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "review_queue.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-review-1",
                    seller_id="xy-seller",
                    title="Pokemon Card Charizard PSA10 in stock",
                    canonical_key="pokemon card charizard psa 10",
                    item_type="card",
                    list_price=1888.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-review-1",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="taobao",
                    offer_id="tb-review-1",
                    seller_id="tb-seller",
                    title="Pokemon Card Charizard PSA 10 flagship listing",
                    canonical_key="pokemon card charizard psa 10",
                    item_type="card",
                    list_price=2088.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/tb-review-1",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="jd",
                    offer_id="jd-review-1",
                    seller_id="jd-seller",
                    title="Pokemon Card Pikachu PSA 10",
                    canonical_key="pokemon card pikachu psa 10",
                    item_type="card",
                    list_price=1188.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/jd-review-1",
                    raw={},
                ),
            ]
        )
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            response = client.get(
                "/analysis/arbitrage/review-queue",
                params={"limit": 10, "candidate_pool": 100, "min_token_overlap": 0.35},
                headers=_bearer(admin_token),
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["count"] >= 1
            first = payload["items"][0]
            assert first["predicted_verdict"] in {"same_group", "close_match"}
            assert first["left"]["platform"] != first["right"]["platform"]
            assert "charizard" in " ".join(first["overlap_tokens"]).lower()
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_arbitrage_review_queue_label_creates_sample_and_excludes_repeat(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "review_queue_label.db"))
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="xianyu",
                    offer_id="xy-review-2",
                    seller_id="xy-seller",
                    title="Pokemon Card Blastoise PSA10 in stock",
                    canonical_key="pokemon card blastoise psa 10",
                    item_type="card",
                    list_price=1688.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/xy-review-2",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="taobao",
                    offer_id="tb-review-2",
                    seller_id="tb-seller",
                    title="Pokemon Card Blastoise PSA 10 flagship listing",
                    canonical_key="pokemon card blastoise psa 10",
                    item_type="card",
                    list_price=1988.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/tb-review-2",
                    raw={},
                ),
            ]
        )
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            queue = client.get(
                "/analysis/arbitrage/review-queue",
                params={"limit": 10, "candidate_pool": 100, "min_token_overlap": 0.35},
                headers=_bearer(admin_token),
            )
            assert queue.status_code == 200
            queue_payload = queue.json()
            assert queue_payload["count"] >= 1
            review_id = queue_payload["items"][0]["review_id"]

            labeled = client.post(
                f"/analysis/arbitrage/review-queue/{review_id}/label",
                params={"candidate_pool": 100, "min_token_overlap": 0.35},
                json={"expected_verdict": "same_group", "note": "queue label"},
                headers=_bearer(admin_token),
            )
            assert labeled.status_code == 200
            labeled_payload = labeled.json()
            assert labeled_payload["sample"]["expected_verdict"] == "same_group"
            assert labeled_payload["sample"]["result"]["pair_signature"].startswith("offerpair:")

            samples = client.get(
                "/analysis/arbitrage/match-samples",
                headers=_bearer(admin_token),
            )
            assert samples.status_code == 200
            assert samples.json()["count"] >= 1

            queue_after = client.get(
                "/analysis/arbitrage/review-queue",
                params={"limit": 10, "candidate_pool": 100, "min_token_overlap": 0.35},
                headers=_bearer(admin_token),
            )
            assert queue_after.status_code == 200
            assert all(item["review_id"] != review_id for item in queue_after.json()["items"])
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_marketplace_shadow_run_once_creates_dry_run_intent_only(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    old_enabled = settings.marketplace_shadow_enabled
    old_min_net_profit = settings.marketplace_shadow_min_net_profit
    old_min_roi = settings.marketplace_shadow_min_roi
    old_min_confidence = settings.marketplace_shadow_min_confidence
    old_candidate_limit = settings.marketplace_shadow_candidate_limit
    old_cooldown = settings.marketplace_shadow_cooldown_minutes
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "marketplace_shadow.db"))
    object.__setattr__(settings, "marketplace_shadow_enabled", True)
    object.__setattr__(settings, "marketplace_shadow_min_net_profit", 50.0)
    object.__setattr__(settings, "marketplace_shadow_min_roi", 0.02)
    object.__setattr__(settings, "marketplace_shadow_min_confidence", 0.75)
    object.__setattr__(settings, "marketplace_shadow_candidate_limit", 10)
    object.__setattr__(settings, "marketplace_shadow_cooldown_minutes", 240)
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="taobao",
                    offer_id="tb-shadow-1",
                    seller_id="tb-seller",
                    title="Pokemon Card Charizard PSA 10",
                    canonical_key="pokemon card charizard psa 10",
                    item_type="card",
                    list_price=1800.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/tb-shadow-1",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="jd",
                    offer_id="jd-shadow-1",
                    seller_id="jd-seller",
                    title="Pokemon Card Charizard PSA 10",
                    canonical_key="pokemon card charizard psa 10",
                    item_type="card",
                    list_price=2499.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/jd-shadow-1",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="pinduoduo",
                    offer_id="pdd-shadow-1",
                    seller_id="pdd-seller",
                    title="Pokemon Card Charizard PSA 10",
                    canonical_key="pokemon card charizard psa 10",
                    item_type="card",
                    list_price=2288.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/pdd-shadow-1",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="manual_virtual",
                    offer_id="manual-shadow-1",
                    seller_id="manual-seller",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=49.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/manual-shadow-1",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="pinduoduo",
                    offer_id="pdd-shadow-virtual-1",
                    seller_id="pdd-seller",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=130.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/pdd-shadow-virtual-1",
                    raw={},
                ),
            ]
        )
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            run = client.post(
                "/marketplace/shadow/run-once",
                headers=_bearer(admin_token),
            )
            assert run.status_code == 200
            payload = run.json()
            assert payload["accepted_count"] >= 1
            assert payload["blocked_count"] >= 0
            assert payload["dry_run_only"] is True
            accepted = [item for item in payload["intents"] if item.get("decision_status") == "accepted"]
            assert accepted

            intents = client.get(
                "/marketplace/shadow/intents",
                headers=_bearer(admin_token),
            )
            assert intents.status_code == 200
            assert intents.json()["count"] >= 1

            runs = client.get(
                "/marketplace/shadow/runs",
                headers=_bearer(admin_token),
            )
            assert runs.status_code == 200
            assert runs.json()["count"] >= 1

            assert repo.list_trades(limit=20) == []
            assert repo.get_execution_log_summary(limit=20)["sample_size"] == 0
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
        object.__setattr__(settings, "marketplace_shadow_enabled", old_enabled)
        object.__setattr__(settings, "marketplace_shadow_min_net_profit", old_min_net_profit)
        object.__setattr__(settings, "marketplace_shadow_min_roi", old_min_roi)
        object.__setattr__(settings, "marketplace_shadow_min_confidence", old_min_confidence)
        object.__setattr__(settings, "marketplace_shadow_candidate_limit", old_candidate_limit)
        object.__setattr__(settings, "marketplace_shadow_cooldown_minutes", old_cooldown)


def test_marketplace_shadow_run_once_can_target_virtual_only_candidates(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    old_enabled = settings.marketplace_shadow_enabled
    old_min_net_profit = settings.marketplace_shadow_min_net_profit
    old_min_roi = settings.marketplace_shadow_min_roi
    old_min_confidence = settings.marketplace_shadow_min_confidence
    old_virtual_min_net_profit = settings.marketplace_shadow_virtual_min_net_profit
    old_virtual_min_roi = settings.marketplace_shadow_virtual_min_roi
    old_virtual_min_confidence = settings.marketplace_shadow_virtual_min_confidence
    old_candidate_limit = settings.marketplace_shadow_candidate_limit
    old_cooldown = settings.marketplace_shadow_cooldown_minutes
    old_manual_age = settings.marketplace_shadow_manual_virtual_max_age_hours
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "marketplace_shadow_virtual.db"))
    object.__setattr__(settings, "marketplace_shadow_enabled", True)
    object.__setattr__(settings, "marketplace_shadow_min_net_profit", 100.0)
    object.__setattr__(settings, "marketplace_shadow_min_roi", 0.12)
    object.__setattr__(settings, "marketplace_shadow_min_confidence", 0.75)
    object.__setattr__(settings, "marketplace_shadow_virtual_min_net_profit", 20.0)
    object.__setattr__(settings, "marketplace_shadow_virtual_min_roi", 0.02)
    object.__setattr__(settings, "marketplace_shadow_virtual_min_confidence", 0.75)
    object.__setattr__(settings, "marketplace_shadow_candidate_limit", 10)
    object.__setattr__(settings, "marketplace_shadow_cooldown_minutes", 240)
    object.__setattr__(settings, "marketplace_shadow_manual_virtual_max_age_hours", 48)
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="pinduoduo",
                    offer_id="pdd-virtual-shadow",
                    seller_id="pdd-seller",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=49.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/pdd-virtual-shadow",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="manual_virtual",
                    offer_id="manual-virtual-shadow",
                    seller_id="operator-baseline",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=79.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/manual-virtual-shadow",
                    raw={"provenance": "operator_manual_virtual_baseline"},
                ),
                MarketplaceOfferIn(
                    platform="pinduoduo",
                    offer_id="pdd-generic-shadow",
                    seller_id="pdd-seller",
                    title="Pokemon Card Charizard PSA 10",
                    canonical_key="pokemon card charizard psa 10",
                    item_type="generic",
                    list_price=2000.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/pdd-generic-shadow",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="jd",
                    offer_id="jd-generic-shadow",
                    seller_id="jd-seller",
                    title="Pokemon Card Charizard PSA 10",
                    canonical_key="pokemon card charizard psa 10",
                    item_type="generic",
                    list_price=2600.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/jd-generic-shadow",
                    raw={},
                ),
            ]
        )
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            run = client.post(
                "/marketplace/shadow/run-once",
                params={"virtual_only": True, "force": True},
                headers=_bearer(admin_token),
            )
            assert run.status_code == 200
            payload = run.json()
            assert payload["accepted_count"] >= 1
            assert payload["run"]["config"]["virtual_only"] is True
            assert payload["run"]["config"]["min_net_profit"] == 20.0
            assert payload["run"]["config"]["min_roi"] == 0.02
            assert payload["run"]["config"]["threshold_source"] == "virtual"
            assert payload["run"]["summary"]["arbitrage_summary"]["opportunity_count"] == 1
            accepted = [item for item in payload["intents"] if item.get("decision_status") == "accepted"]
            assert accepted
            candidate = accepted[0]["snapshot"]["candidate"]
            assert candidate["item_type"] == "virtual_goods"
            assert candidate["sources"] == ["manual_virtual", "pinduoduo"]
            assert "Pokemon" not in candidate["reference_title"]

            intent_id = int(accepted[0]["id"])
            detail = client.get(
                f"/marketplace/shadow/intents/{intent_id}",
                headers=_bearer(admin_token),
            )
            assert detail.status_code == 200
            detail_payload = detail.json()
            assert detail_payload["id"] == intent_id
            assert detail_payload["decision_pack"]["item_type"] == "virtual_goods"
            assert detail_payload["decision_pack"]["virtual_only"] is True
            assert detail_payload["decision_pack"]["threshold_source"] == "virtual"
            assert detail_payload["decision_pack"]["buy"]["platform"] == "pinduoduo"
            assert detail_payload["decision_pack"]["sell"]["platform"] == "manual_virtual"
            serialized = str(detail_payload).lower()
            assert "cookie" not in serialized
            assert "authorization" not in serialized
            assert "raw html" not in serialized

            review = client.post(
                f"/marketplace/shadow/intents/{intent_id}/review",
                json={"note": "reviewed virtual baseline decision", "verdict": "valid_profit"},
                headers=_bearer(admin_token),
            )
            assert review.status_code == 200
            reviewed_payload = review.json()
            assert reviewed_payload["review_note"] == "reviewed virtual baseline decision"
            assert reviewed_payload["review_verdict"] == "valid_profit"
            assert reviewed_payload["reviewed_at"]
            assert reviewed_payload["reviewed_by"] in {settings.ui_auth_username, "test-bypass"}
            assert reviewed_payload["decision_pack"]["review_note"] == "reviewed virtual baseline decision"
            assert reviewed_payload["decision_pack"]["review_verdict"] == "valid_profit"

            outcome = client.post(
                f"/marketplace/shadow/intents/{intent_id}/outcome",
                json={
                    "observed_buy_price": 50.0,
                    "observed_sell_price": 80.0,
                    "extra_cost": 1.0,
                    "outcome_status": "profitable",
                    "note": "manual observed virtual outcome",
                },
                headers=_bearer(admin_token),
            )
            assert outcome.status_code == 200
            outcome_payload = outcome.json()
            assert outcome_payload["outcome_status"] == "profitable"
            assert outcome_payload["observed_net_profit"] == 29.0
            assert outcome_payload["observed_roi"] == 0.58
            assert outcome_payload["decision_pack"]["outcome"]["status"] == "profitable"
            assert outcome_payload["decision_pack"]["outcome"]["observed_net_profit"] == 29.0

            report = client.get(
                "/marketplace/shadow/virtual-report",
                headers=_bearer(admin_token),
            )
            assert report.status_code == 200
            report_payload = report.json()
            assert report_payload["virtual_only"] is True
            assert report_payload["item_type"] == "virtual_goods"
            assert report_payload["accepted_count"] >= 1
            assert report_payload["valid_profit_count"] >= 1
            assert report_payload["profitable_outcome_count"] >= 1
            assert report_payload["recent_items"][0]["outcome_status"] == "profitable"
            assert report_payload["recent_items"][0]["observed_net_profit"] == 29.0
            assert report_payload["recent_items"][0]["review_verdict"] == "valid_profit"
            serialized = str(report_payload).lower()
            assert "cookie" not in serialized
            assert "authorization" not in serialized
            assert "raw html" not in serialized
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
        object.__setattr__(settings, "marketplace_shadow_enabled", old_enabled)
        object.__setattr__(settings, "marketplace_shadow_min_net_profit", old_min_net_profit)
        object.__setattr__(settings, "marketplace_shadow_min_roi", old_min_roi)
        object.__setattr__(settings, "marketplace_shadow_min_confidence", old_min_confidence)
        object.__setattr__(settings, "marketplace_shadow_virtual_min_net_profit", old_virtual_min_net_profit)
        object.__setattr__(settings, "marketplace_shadow_virtual_min_roi", old_virtual_min_roi)
        object.__setattr__(settings, "marketplace_shadow_virtual_min_confidence", old_virtual_min_confidence)
        object.__setattr__(settings, "marketplace_shadow_candidate_limit", old_candidate_limit)
        object.__setattr__(settings, "marketplace_shadow_cooldown_minutes", old_cooldown)
        object.__setattr__(settings, "marketplace_shadow_manual_virtual_max_age_hours", old_manual_age)


def test_marketplace_shadow_run_once_rejects_non_virtual_runs(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    old_min_net_profit = settings.marketplace_shadow_min_net_profit
    old_min_roi = settings.marketplace_shadow_min_roi
    old_min_confidence = settings.marketplace_shadow_min_confidence
    old_virtual_min_net_profit = settings.marketplace_shadow_virtual_min_net_profit
    old_virtual_min_roi = settings.marketplace_shadow_virtual_min_roi
    old_virtual_min_confidence = settings.marketplace_shadow_virtual_min_confidence
    old_candidate_limit = settings.marketplace_shadow_candidate_limit
    old_cooldown = settings.marketplace_shadow_cooldown_minutes
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "marketplace_shadow_global_threshold.db"))
    object.__setattr__(settings, "marketplace_shadow_min_net_profit", 100.0)
    object.__setattr__(settings, "marketplace_shadow_min_roi", 0.12)
    object.__setattr__(settings, "marketplace_shadow_min_confidence", 0.75)
    object.__setattr__(settings, "marketplace_shadow_virtual_min_net_profit", 20.0)
    object.__setattr__(settings, "marketplace_shadow_virtual_min_roi", 0.02)
    object.__setattr__(settings, "marketplace_shadow_virtual_min_confidence", 0.75)
    object.__setattr__(settings, "marketplace_shadow_candidate_limit", 10)
    object.__setattr__(settings, "marketplace_shadow_cooldown_minutes", 240)
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="pinduoduo",
                    offer_id="pdd-virtual-shadow-global-threshold",
                    seller_id="pdd-seller",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=49.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/pdd-virtual-shadow-global-threshold",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="manual_virtual",
                    offer_id="manual-virtual-shadow-global-threshold",
                    seller_id="operator-baseline",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=79.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/manual-virtual-shadow-global-threshold",
                    raw={"provenance": "operator_manual_virtual_baseline"},
                ),
            ]
        )
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            run = client.post(
                "/marketplace/shadow/run-once",
                params={"virtual_only": False, "force": True},
                headers=_bearer(admin_token),
            )
            assert run.status_code == 400
            payload = run.json()
            assert payload["detail"] == "marketplace shadow runs are virtual-only; virtual_only=false is disabled"
            assert repo.list_marketplace_shadow_runs(limit=10) == []
            assert repo.list_marketplace_shadow_intents(limit=10) == []
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
        object.__setattr__(settings, "marketplace_shadow_min_net_profit", old_min_net_profit)
        object.__setattr__(settings, "marketplace_shadow_min_roi", old_min_roi)
        object.__setattr__(settings, "marketplace_shadow_min_confidence", old_min_confidence)
        object.__setattr__(settings, "marketplace_shadow_virtual_min_net_profit", old_virtual_min_net_profit)
        object.__setattr__(settings, "marketplace_shadow_virtual_min_roi", old_virtual_min_roi)
        object.__setattr__(settings, "marketplace_shadow_virtual_min_confidence", old_virtual_min_confidence)
        object.__setattr__(settings, "marketplace_shadow_candidate_limit", old_candidate_limit)
        object.__setattr__(settings, "marketplace_shadow_cooldown_minutes", old_cooldown)


def test_marketplace_shadow_outcome_rejects_blocked_intent(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "marketplace_shadow_blocked_outcome.db"))
    try:
        init_db()
        intent = repo.create_marketplace_shadow_intent(
            run_id=None,
            intent_key="blocked-virtual-intent",
            arbitrage_key="q coin auto recharge",
            reference_title="Q coin auto recharge instant delivery direct topup",
            buy_platform="pinduoduo",
            sell_platform="manual_virtual",
            buy_listing_id="pdd-blocked",
            sell_listing_id="manual-blocked",
            platform_count=2,
            listing_count=2,
            estimated_net_profit=12.0,
            estimated_roi=0.1,
            confidence_score=0.78,
            decision_status="blocked",
            blocked_reason="net_profit_below_threshold",
            snapshot={
                "candidate": {
                    "item_type": "virtual_goods",
                    "buy": {"source": "pinduoduo", "listing_id": "pdd-blocked", "title": "Q coin", "list_price": 49.0},
                    "sell": {"source": "manual_virtual", "listing_id": "manual-blocked", "title": "Q coin", "list_price": 79.0},
                },
                "decision": {"virtual_only": True, "item_type": "virtual_goods"},
            },
        )
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            outcome = client.post(
                f"/marketplace/shadow/intents/{int(intent['id'])}/outcome",
                json={
                    "observed_buy_price": 50.0,
                    "observed_sell_price": 80.0,
                    "extra_cost": 0.0,
                    "outcome_status": "profitable",
                },
                headers=_bearer(admin_token),
            )
            assert outcome.status_code == 400
            assert outcome.json()["detail"] == "only accepted virtual shadow intents can record an outcome"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_marketplace_shadow_blocks_stale_manual_virtual_baseline(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    old_virtual_min_net_profit = settings.marketplace_shadow_virtual_min_net_profit
    old_virtual_min_roi = settings.marketplace_shadow_virtual_min_roi
    old_virtual_min_confidence = settings.marketplace_shadow_virtual_min_confidence
    old_candidate_limit = settings.marketplace_shadow_candidate_limit
    old_manual_age = settings.marketplace_shadow_manual_virtual_max_age_hours
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "marketplace_shadow_stale_manual.db"))
    object.__setattr__(settings, "marketplace_shadow_virtual_min_net_profit", 20.0)
    object.__setattr__(settings, "marketplace_shadow_virtual_min_roi", 0.02)
    object.__setattr__(settings, "marketplace_shadow_virtual_min_confidence", 0.75)
    object.__setattr__(settings, "marketplace_shadow_candidate_limit", 10)
    object.__setattr__(settings, "marketplace_shadow_manual_virtual_max_age_hours", 24)
    try:
        init_db()
        fresh_listed_at = datetime.now(timezone.utc)
        stale_listed_at = fresh_listed_at - timedelta(hours=36)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="pinduoduo",
                    offer_id="pdd-stale-manual-shadow",
                    seller_id="pdd-seller",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=49.0,
                    shipping_cost=0.0,
                    listed_at=fresh_listed_at,
                    status="open",
                    listing_url="https://example.com/pdd-stale-manual-shadow",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="manual_virtual",
                    offer_id="manual-stale-shadow",
                    seller_id="operator-baseline",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=79.0,
                    shipping_cost=0.0,
                    listed_at=stale_listed_at,
                    status="open",
                    listing_url="https://example.com/manual-stale-shadow",
                    raw={"provenance": "operator_manual_virtual_baseline"},
                ),
            ]
        )
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={"username": settings.ui_auth_username, "password": settings.ui_auth_password},
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            run = client.post(
                "/marketplace/shadow/run-once",
                params={"virtual_only": True, "force": True},
                headers=_bearer(admin_token),
            )
            assert run.status_code == 200
            payload = run.json()
            assert payload["accepted_count"] == 0
            assert payload["blocked_count"] == 1
            intent = payload["intents"][0]
            assert intent["blocked_reason"] == "manual_virtual_baseline_stale"
            freshness = intent["snapshot"]["decision"]["manual_virtual_freshness"]
            assert freshness["stale"] is True
            assert freshness["max_age_hours"] == 24

            report = client.get("/marketplace/shadow/virtual-report", headers=_bearer(admin_token))
            assert report.status_code == 200
            report_payload = report.json()
            assert report_payload["accepted_count"] == 0
            assert report_payload["blocked_count"] == 1
            assert report_payload["recent_items"][0]["blocked_reason"] == "manual_virtual_baseline_stale"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
        object.__setattr__(settings, "marketplace_shadow_virtual_min_net_profit", old_virtual_min_net_profit)
        object.__setattr__(settings, "marketplace_shadow_virtual_min_roi", old_virtual_min_roi)
        object.__setattr__(settings, "marketplace_shadow_virtual_min_confidence", old_virtual_min_confidence)
        object.__setattr__(settings, "marketplace_shadow_candidate_limit", old_candidate_limit)
        object.__setattr__(settings, "marketplace_shadow_manual_virtual_max_age_hours", old_manual_age)


def test_marketplace_shadow_run_once_respects_cooldown(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    old_min_net_profit = settings.marketplace_shadow_min_net_profit
    old_min_roi = settings.marketplace_shadow_min_roi
    old_min_confidence = settings.marketplace_shadow_min_confidence
    old_candidate_limit = settings.marketplace_shadow_candidate_limit
    old_cooldown = settings.marketplace_shadow_cooldown_minutes
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "marketplace_shadow_cooldown.db"))
    object.__setattr__(settings, "marketplace_shadow_min_net_profit", 50.0)
    object.__setattr__(settings, "marketplace_shadow_min_roi", 0.02)
    object.__setattr__(settings, "marketplace_shadow_min_confidence", 0.75)
    object.__setattr__(settings, "marketplace_shadow_candidate_limit", 10)
    object.__setattr__(settings, "marketplace_shadow_cooldown_minutes", 240)
    try:
        init_db()
        listed_at = datetime.now(timezone.utc)
        repo.insert_marketplace_offers(
            [
                MarketplaceOfferIn(
                    platform="manual_virtual",
                    offer_id="manual-shadow-2",
                    seller_id="manual-seller",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=49.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/manual-shadow-2",
                    raw={},
                ),
                MarketplaceOfferIn(
                    platform="pinduoduo",
                    offer_id="pdd-shadow-virtual-2",
                    seller_id="pdd-seller",
                    title="Q coin auto recharge instant delivery direct topup",
                    canonical_key="q coin auto recharge instant delivery direct topup",
                    item_type="virtual_goods",
                    list_price=130.0,
                    shipping_cost=0.0,
                    listed_at=listed_at,
                    status="open",
                    listing_url="https://example.com/pdd-shadow-virtual-2",
                    raw={},
                ),
            ]
        )
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login",
                json={
                    "username": settings.ui_auth_username,
                    "password": settings.ui_auth_password,
                },
            )
            assert login.status_code == 200
            admin_token = login.json()["data"]["token"]

            first = client.post(
                "/marketplace/shadow/run-once",
                headers=_bearer(admin_token),
            )
            assert first.status_code == 200
            assert first.json()["accepted_count"] >= 1

            second = client.post(
                "/marketplace/shadow/run-once",
                headers=_bearer(admin_token),
            )
            assert second.status_code == 200
            second_payload = second.json()
            assert second_payload["blocked_count"] >= 1
            assert any(
                item.get("blocked_reason") == "cooldown_active"
                for item in second_payload["intents"]
            )
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
        object.__setattr__(settings, "marketplace_shadow_min_net_profit", old_min_net_profit)
        object.__setattr__(settings, "marketplace_shadow_min_roi", old_min_roi)
        object.__setattr__(settings, "marketplace_shadow_min_confidence", old_min_confidence)
        object.__setattr__(settings, "marketplace_shadow_candidate_limit", old_candidate_limit)
        object.__setattr__(settings, "marketplace_shadow_cooldown_minutes", old_cooldown)


def test_pinduoduo_cookie_mode_status_and_sync_once(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "pdd_cookie_mode.db"))
    client = pdd_module.pinduoduo_open_client
    old_snapshot_provider_url = client.snapshot_provider_url
    old_api_url = client.api_url
    old_client_id = client.client_id
    old_client_secret = client.client_secret
    old_api_type = client.api_type
    old_params_json = client.params_json
    old_cookie = client.cookie_provider._cached_cookie
    try:
        init_db()
        client.snapshot_provider_url = ""
        client.api_url = ""
        client.client_id = ""
        client.client_secret = ""
        client.api_type = "pdd.ddk.goods.search"
        client.params_json = '{"keyword":"Pokemon Card PSA 10"}'
        client.cookie_provider._cached_cookie = "foo=bar"

        class _FakeResponse:
            status_code = 200

            @staticmethod
            def raise_for_status() -> None:
                return None

            @staticmethod
            def json() -> dict:
                return {
                    "goods_search_response": {
                        "goods_list": [
                            {
                                "goods_id": "pdd-cookie-1",
                                "goods_name": "Pokemon Card Charizard PSA 10",
                                "mall_id": "pdd-mall",
                                "min_group_price": 228800,
                                "goods_link": "https://example.com/pdd-cookie-1",
                                "listed_at": datetime.now(timezone.utc).isoformat(),
                            }
                        ]
                    }
                }

        with patch.object(pdd_module, "request_get", return_value=_FakeResponse()):
            with TestClient(create_app()) as client_http:
                login = client_http.post(
                    "/auth/login",
                    json={
                        "username": settings.ui_auth_username,
                        "password": settings.ui_auth_password,
                    },
                )
                assert login.status_code == 200
                admin_token = login.json()["data"]["token"]

                status_resp = client_http.get(
                    "/marketplace/providers/pinduoduo/status",
                    headers=_bearer(admin_token),
                )
                assert status_resp.status_code == 200
                status_payload = status_resp.json()
                assert status_payload["active_mode"] == "cookie"
                assert status_payload["cookie_configured"] is True
                assert status_payload["official_configured"] is False

                sync_resp = client_http.post(
                    "/marketplace/providers/pinduoduo/sync-once",
                    params={"snapshot_url": "https://bridge.local/pdd/snapshot"},
                    headers=_bearer(admin_token),
                )
                assert sync_resp.status_code == 200
                sync_payload = sync_resp.json()
                assert sync_payload["inserted"] == 1

                offers = repo.list_marketplace_offers(platform="pinduoduo", limit=10)
                assert len(offers) == 1
                assert str(offers[0]["offer_id"]) == "pdd-cookie-1"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
        client.snapshot_provider_url = old_snapshot_provider_url
        client.api_url = old_api_url
        client.client_id = old_client_id
        client.client_secret = old_client_secret
        client.api_type = old_api_type
        client.params_json = old_params_json
        client.cookie_provider._cached_cookie = old_cookie


def test_jd_cookie_mode_status_and_sync_once(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "jd_cookie_mode.db"))
    client = jd_module.jd_open_client
    old_snapshot_provider_url = client.snapshot_provider_url
    old_api_url = client.api_url
    old_app_key = client.app_key
    old_app_secret = client.app_secret
    old_method = client.method
    old_param_json = client.param_json
    old_cookie = client.cookie_provider._cached_cookie
    try:
        init_db()
        client.snapshot_provider_url = ""
        client.api_url = ""
        client.app_key = ""
        client.app_secret = ""
        client.method = "jd.union.open.goods.query"
        client.param_json = '{"goodsReq":{"keyword":"Pokemon Card PSA 10"}}'
        client.cookie_provider._cached_cookie = "pin=jd_cookie"

        class _FakeResponse:
            status_code = 200

            @staticmethod
            def raise_for_status() -> None:
                return None

            @staticmethod
            def json() -> dict:
                return {
                    "jd_union_open_goods_query_response": {
                        "queryResult": {
                            "goodsList": [
                                {
                                    "skuId": "jd-cookie-1",
                                    "skuName": "Pokemon Card Charizard PSA 10",
                                    "owner": "jd-shop",
                                    "price": 2499.0,
                                    "materialUrl": "https://example.com/jd-cookie-1",
                                    "listed_at": datetime.now(timezone.utc).isoformat(),
                                }
                            ]
                        }
                    }
                }

        with patch.object(jd_module, "request_get", return_value=_FakeResponse()):
            with TestClient(create_app()) as client_http:
                login = client_http.post(
                    "/auth/login",
                    json={
                        "username": settings.ui_auth_username,
                        "password": settings.ui_auth_password,
                    },
                )
                assert login.status_code == 200
                admin_token = login.json()["data"]["token"]

                status_resp = client_http.get(
                    "/marketplace/providers/jd/status",
                    headers=_bearer(admin_token),
                )
                assert status_resp.status_code == 200
                status_payload = status_resp.json()
                assert status_payload["active_mode"] == "cookie"
                assert status_payload["cookie_configured"] is True
                assert status_payload["official_configured"] is False

                sync_resp = client_http.post(
                    "/marketplace/providers/jd/sync-once",
                    params={"snapshot_url": "https://bridge.local/jd/snapshot"},
                    headers=_bearer(admin_token),
                )
                assert sync_resp.status_code == 200
                sync_payload = sync_resp.json()
                assert sync_payload["inserted"] == 1

                offers = repo.list_marketplace_offers(platform="jd", limit=10)
                assert len(offers) == 1
                assert str(offers[0]["offer_id"]) == "jd-cookie-1"
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
        client.snapshot_provider_url = old_snapshot_provider_url
        client.api_url = old_api_url
        client.app_key = old_app_key
        client.app_secret = old_app_secret
        client.method = old_method
        client.param_json = old_param_json
        client.cookie_provider._cached_cookie = old_cookie
