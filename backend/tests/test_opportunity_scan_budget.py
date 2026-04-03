from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from app.database import init_db
from app.services.opportunity_scan import _allocate_source_scan_budget
import app.services.opportunity_scan as opportunity_scan_module


@pytest.fixture
def isolated_scan_budget_sqlite(tmp_path: Path):
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "scan_budget.db"))
    init_db()
    try:
        yield Path(settings.sqlite_path)
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_allocate_source_scan_budget_prefers_widen_sources() -> None:
    listings = [
        {"id": 1, "source": "alpha", "listed_at": "2026-03-22T10:00:00+00:00"},
        {"id": 2, "source": "alpha", "listed_at": "2026-03-22T09:59:00+00:00"},
        {"id": 3, "source": "beta", "listed_at": "2026-03-22T09:58:00+00:00"},
        {"id": 4, "source": "beta", "listed_at": "2026-03-22T09:57:00+00:00"},
        {"id": 5, "source": "gamma", "listed_at": "2026-03-22T09:56:00+00:00"},
        {"id": 6, "source": "gamma", "listed_at": "2026-03-22T09:55:00+00:00"},
    ]
    metrics = {
        "profit_cockpit": {
            "source_leaderboard_7d": [
                {"source": "alpha", "intake_multiplier": 1.15},
                {"source": "beta", "intake_multiplier": 0.6},
                {"source": "gamma", "intake_multiplier": 1.0},
            ],
        },
    }

    selected, budget = _allocate_source_scan_budget(listings, limit=4, metrics=metrics)

    selected_ids = [int(item["id"]) for item in selected]
    alpha_budget = next(item for item in budget if item["source"] == "alpha")
    beta_budget = next(item for item in budget if item["source"] == "beta")

    assert len(selected_ids) == 4
    assert alpha_budget["quota"] >= beta_budget["quota"]
    assert selected_ids.count(1) + selected_ids.count(2) >= 1


def test_allocate_source_scan_budget_falls_back_when_metrics_missing() -> None:
    listings = [
        {"id": 1, "source": "alpha", "listed_at": "2026-03-22T10:00:00+00:00"},
        {"id": 2, "source": "beta", "listed_at": "2026-03-22T09:59:00+00:00"},
        {"id": 3, "source": "beta", "listed_at": "2026-03-22T09:58:00+00:00"},
    ]

    selected, budget = _allocate_source_scan_budget(listings, limit=2, metrics={})

    assert len(selected) == 2
    assert {item["source"] for item in budget} == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_scan_open_listings_skips_frozen_sellers(
    isolated_scan_budget_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        opportunity_scan_module.repo,
        "get_open_listings",
        lambda limit=0, include_noise_filtered=False: [
            {
                "id": 1,
                "source": "alpha",
                "seller_id": "seller-frozen",
                "title": "Frozen card",
                "description": "",
                "list_price": 100.0,
                "listed_at": "2026-03-22T10:00:00+00:00",
                "normalized_title": "Frozen card",
                "normalized_key": "manual_card:Frozen card",
                "normalization_blocked": 0,
                "normalization_version": "listing_normalizer_v1",
            },
            {
                "id": 2,
                "source": "alpha",
                "seller_id": "seller-open",
                "title": "Open card",
                "description": "",
                "list_price": 100.0,
                "listed_at": "2026-03-22T09:00:00+00:00",
                "normalized_title": "Open card",
                "normalized_key": "manual_card:Open card",
                "normalization_blocked": 0,
                "normalization_version": "listing_normalizer_v1",
            },
        ],
    )
    monkeypatch.setattr(opportunity_scan_module.repo, "get_dashboard_metrics", lambda: {})
    monkeypatch.setattr(opportunity_scan_module.seller_controls_service, "sync_from_metrics", lambda **kwargs: {"status": {"active_freeze_count": 1}})
    monkeypatch.setattr(
        opportunity_scan_module.seller_controls_service,
        "is_seller_frozen",
        lambda *, source, seller_id: seller_id == "seller-frozen",
    )
    monkeypatch.setattr(opportunity_scan_module.repo, "get_opportunity_status_map_by_listing_rows", lambda listing_ids: {})
    monkeypatch.setattr(opportunity_scan_module.repo, "has_reject_history_for_listing_signature", lambda **kwargs: False)
    monkeypatch.setattr(opportunity_scan_module.repo, "has_frozen_opportunity_for_listing_fingerprint", lambda **kwargs: False)
    monkeypatch.setattr(opportunity_scan_module.repo, "get_features", lambda *args, **kwargs: None)

    async def _fake_extract(title, description):
        class _Feature:
            card_name = title
            rarity = "R"
            edition = "std"
            card_condition = "nm"
            confidence = 0.9
            extras = {}

        return _Feature(), "pytest"

    monkeypatch.setattr(opportunity_scan_module._extractor, "extract", _fake_extract)
    monkeypatch.setattr(opportunity_scan_module.repo, "get_recent_sales", lambda *args, **kwargs: [])

    class _Valuation:
        expected_sale_price = 160.0
        buy_limit = 120.0
        suggested_list_price = 170.0
        ci_low = 140.0
        ci_high = 180.0
        model_confidence = 0.9
        comparables_count = 10
        reasoning = "ok"

    monkeypatch.setattr(opportunity_scan_module, "estimate_valuation", lambda **kwargs: _Valuation())
    monkeypatch.setattr(opportunity_scan_module.repo, "get_seller_open_listing_count", lambda **kwargs: 0)
    monkeypatch.setattr(
        opportunity_scan_module,
        "assess_opportunity_risk",
        lambda **kwargs: type("Risk", (), {"score": 10.0, "reasons": (), "level": "low", "hard_block": False})(),
    )
    monkeypatch.setattr(opportunity_scan_module, "score_opportunity", lambda **kwargs: (30.0, 0.3, 88.0, "pending_review"))
    monkeypatch.setattr(opportunity_scan_module, "apply_risk_gate", lambda status, risk: status)
    monkeypatch.setattr(opportunity_scan_module, "format_risk_note", lambda risk: "risk_score=10")
    monkeypatch.setattr(opportunity_scan_module.repo, "persist_scan_batch", lambda items: None)

    result = await opportunity_scan_module.scan_open_listings(limit=2)

    assert result["processed"] == 2
    assert result["seller_frozen"] == 1
    assert result["noise_filtered"] == 0


@pytest.mark.asyncio
async def test_scan_open_listings_counts_noise_filtered_rows(
    isolated_scan_budget_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        opportunity_scan_module.repo,
        "get_open_listings",
        lambda limit=0, include_noise_filtered=False: [
            {
                "id": 10,
                "source": "alpha",
                "seller_id": "seller-noise",
                "title": "Account service",
                "description": "",
                "list_price": 10.0,
                "listed_at": "2026-03-22T10:00:00+00:00",
                "normalized_title": "Account service",
                "normalized_key": "account_service:Account service",
                "normalization_blocked": 1,
                "normalization_version": "listing_normalizer_v1",
            },
            {
                "id": 11,
                "source": "alpha",
                "seller_id": "seller-open",
                "title": "Open card",
                "description": "",
                "list_price": 100.0,
                "listed_at": "2026-03-22T09:00:00+00:00",
                "normalized_title": "Open card",
                "normalized_key": "manual_card:Open card",
                "normalization_blocked": 0,
                "normalization_version": "listing_normalizer_v1",
            },
        ],
    )
    monkeypatch.setattr(opportunity_scan_module.repo, "get_dashboard_metrics", lambda: {})
    monkeypatch.setattr(opportunity_scan_module.seller_controls_service, "sync_from_metrics", lambda **kwargs: {"status": {}})
    monkeypatch.setattr(opportunity_scan_module.seller_controls_service, "is_seller_frozen", lambda **kwargs: False)
    monkeypatch.setattr(opportunity_scan_module.repo, "get_opportunity_status_map_by_listing_rows", lambda listing_ids: {})
    monkeypatch.setattr(opportunity_scan_module.repo, "has_reject_history_for_listing_signature", lambda **kwargs: False)
    monkeypatch.setattr(opportunity_scan_module.repo, "has_frozen_opportunity_for_listing_fingerprint", lambda **kwargs: False)
    monkeypatch.setattr(opportunity_scan_module.repo, "get_features", lambda *args, **kwargs: None)

    async def _fake_extract(title, description):
        class _Feature:
            card_name = title
            rarity = "R"
            edition = "std"
            card_condition = "nm"
            confidence = 0.9
            extras = {}

        return _Feature(), "pytest"

    monkeypatch.setattr(opportunity_scan_module._extractor, "extract", _fake_extract)
    monkeypatch.setattr(opportunity_scan_module.repo, "get_recent_sales", lambda *args, **kwargs: [])

    class _Valuation:
        expected_sale_price = 160.0
        buy_limit = 120.0
        suggested_list_price = 170.0
        ci_low = 140.0
        ci_high = 180.0
        model_confidence = 0.9
        comparables_count = 10
        reasoning = "ok"

    monkeypatch.setattr(opportunity_scan_module, "estimate_valuation", lambda **kwargs: _Valuation())
    monkeypatch.setattr(opportunity_scan_module.repo, "get_seller_open_listing_count", lambda **kwargs: 0)
    monkeypatch.setattr(
        opportunity_scan_module,
        "assess_opportunity_risk",
        lambda **kwargs: type("Risk", (), {"score": 10.0, "reasons": (), "level": "low", "hard_block": False})(),
    )
    monkeypatch.setattr(opportunity_scan_module, "score_opportunity", lambda **kwargs: (30.0, 0.3, 88.0, "pending_review"))
    monkeypatch.setattr(opportunity_scan_module, "apply_risk_gate", lambda status, risk: status)
    monkeypatch.setattr(opportunity_scan_module, "format_risk_note", lambda risk: "risk_score=10")
    monkeypatch.setattr(opportunity_scan_module.repo, "persist_scan_batch", lambda items: None)

    result = await opportunity_scan_module.scan_open_listings(limit=2)

    assert result["candidate_pool_size"] == 2
    assert result["processed"] == 1
    assert result["noise_filtered"] == 1
