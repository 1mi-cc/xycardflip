from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

import browser_snapshot_bridge as bridge  # noqa: E402


def test_pinduoduo_keyword_variants_include_ascii_terms() -> None:
    variants = bridge._keyword_variants("Pokemon Card PSA 10")
    lowered = {item.lower() for item in variants}
    assert "pokemon" in lowered
    assert "card" in lowered
    assert "psa" in lowered


def test_pinduoduo_coerce_bridge_items_stays_empty_for_irrelevant_candidates() -> None:
    accepted, diagnostics = bridge._coerce_bridge_items(
        "pinduoduo",
        raw_items=[
            {
                "goods_id": "pdd-x",
                "goods_name": "Running shoes lightweight men",
                "goods_link": "https://mobile.yangkeduo.com/goods.html?goods_id=654321",
                "priceText": "Price 89.00",
                "listed_at": "2026-04-11T00:00:00Z",
            }
        ],
        body_text="search results",
        keyword="Pokemon Card PSA 10",
        limit=5,
    )

    assert accepted == []
    assert diagnostics
    assert all(not item["accepted"] for item in diagnostics)


def test_pinduoduo_snapshot_state_marks_login_page_not_ready_for_push() -> None:
    snapshot_state = bridge._build_snapshot_state(
        provider="pinduoduo",
        raw_items=[],
        filtered_items=[],
        diagnostics=[],
        login_required=True,
        virtual_goods_only_applied=True,
    )

    assert snapshot_state["page_state"] == "login"
    assert snapshot_state["login_required"] is True
    assert snapshot_state["accepted_item_count"] == 0
    assert snapshot_state["virtual_goods_only_applied"] is True
    assert snapshot_state["ready_for_push"] is False


def test_pinduoduo_snapshot_state_marks_search_results_without_virtual_matches_not_ready_for_push() -> None:
    snapshot_state = bridge._build_snapshot_state(
        provider="pinduoduo",
        raw_items=[
            {
                "goods_id": "pdd-x",
                "goods_name": "Plastic toy coin",
                "goods_link": "https://mobile.yangkeduo.com/goods.html?goods_id=654321",
                "priceText": "Price 8.88",
            }
        ],
        filtered_items=[],
        diagnostics=[
            {
                "title": "Plastic toy coin",
                "price": 8.88,
                "link_present": False,
                "fulfillment_mode": "physical",
                "keyword_score": 0,
                "score": 0.0,
                "accepted": False,
                "source": "anchor",
            }
        ],
        login_required=False,
        virtual_goods_only_applied=True,
    )

    assert snapshot_state["page_state"] == "search_results"
    assert snapshot_state["low_confidence"] is True
    assert snapshot_state["virtual_candidate_count"] == 0
    assert snapshot_state["physical_candidate_count"] == 1
    assert snapshot_state["accepted_item_count"] == 0
    assert snapshot_state["ready_for_push"] is False


def test_pinduoduo_coerce_bridge_items_accepts_relevant_candidate() -> None:
    raw_items = [
        {
            "goods_id": "pdd-1",
            "goods_name": "Pokemon Card Charizard ex PSA10 collector card",
            "goods_link": "https://mobile.yangkeduo.com/goods.html?goods_id=123456",
            "priceText": "Pokemon Card Charizard ex PSA10 collector card Price 63.00",
            "listed_at": "2026-04-11T00:00:00Z",
        }
    ]
    accepted, diagnostics = bridge._coerce_bridge_items(
        "pinduoduo",
        raw_items=raw_items,
        body_text="search results",
        keyword="Pokemon Card PSA 10",
        limit=5,
    )

    assert len(accepted) == 1
    assert accepted[0]["goods_id"] == "pdd-1"
    assert any(item["accepted"] for item in diagnostics)


def test_pinduoduo_accepts_virtual_goods_candidate() -> None:
    raw_items = [
        {
            "goods_id": "pdd-v1",
            "goods_name": "Q coin auto recharge instant delivery direct topup",
            "goods_link": "https://mobile.yangkeduo.com/goods.html?goods_id=987654",
            "priceText": "Q coin auto recharge instant delivery direct topup Price 50.00",
            "listed_at": "2026-04-11T00:00:00Z",
        }
    ]

    accepted, diagnostics = bridge._coerce_bridge_items(
        "pinduoduo",
        raw_items=raw_items,
        body_text="search results",
        keyword="q coin recharge",
        limit=5,
    )

    assert len(accepted) == 1
    assert accepted[0]["goods_id"] == "pdd-v1"
    assert accepted[0]["item_type"] == "virtual_goods"
    assert accepted[0]["fulfillment_mode"] == "virtual"
    assert any(item["accepted"] for item in diagnostics)


def test_pinduoduo_rejects_physical_goods_noise_for_virtual_keyword() -> None:
    raw_items = [
        {
            "goods_id": "pdd-physical",
            "goods_name": "Plastic toy coin prop set",
            "goods_link": "https://mobile.yangkeduo.com/goods.html?goods_id=111111",
            "priceText": "Plastic toy coin prop set Price 8.88",
            "listed_at": "2026-04-11T00:00:00Z",
        }
    ]

    accepted, diagnostics = bridge._coerce_bridge_items(
        "pinduoduo",
        raw_items=raw_items,
        body_text="search results",
        keyword="q coin recharge",
        limit=5,
        virtual_goods_only=True,
    )

    assert accepted == []
    assert diagnostics
    assert all(not item["accepted"] for item in diagnostics)
