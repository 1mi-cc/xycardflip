from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

import browser_snapshot_bridge as bridge  # noqa: E402


def test_jd_defaults_to_virtual_goods_seed() -> None:
    cfg = bridge.PROVIDER_CONFIG["jd"]
    assert cfg["default_keyword"] == "Q coin auto recharge"
    assert cfg["default_virtual_goods_only"] is True


def test_keyword_variants_add_expected_aliases() -> None:
    variants = bridge._keyword_variants("Pokemon Card PSA 10")
    lowered = {item.lower() for item in variants}
    assert "pokemon" in lowered
    assert "card" in lowered
    assert "psa" in lowered
    assert "宝可梦" in lowered
    assert "卡牌" in lowered


def test_keyword_score_requires_strong_overlap() -> None:
    assert bridge._keyword_score("宝可梦 快龙 ex PSA10 收藏卡", "Pokemon Card PSA 10") >= 2
    assert bridge._keyword_score("特步 跑鞋 男鞋", "Pokemon Card PSA 10") == 0


def test_coerce_bridge_items_filters_irrelevant_candidates() -> None:
    raw_items = [
        {
            "skuId": "1",
            "skuName": "特步 跑鞋 男鞋",
            "materialUrl": "https://item.jd.com/1.html",
            "priceText": "到手价 ¥295.00",
            "listed_at": "2026-04-11T00:00:00Z",
        },
        {
            "skuId": "2",
            "skuName": "宝可梦 快龙 ex PSA10 收藏卡",
            "materialUrl": "https://item.jd.com/2.html",
            "priceText": "到手价 ¥63.00",
            "listed_at": "2026-04-11T00:00:00Z",
        },
    ]

    accepted, diagnostics = bridge._coerce_bridge_items(
        "jd",
        raw_items,
        body_text="",
        keyword="Pokemon Card PSA 10",
        limit=5,
    )

    assert len(accepted) == 1
    assert accepted[0]["skuId"] == "2"
    assert any(item["accepted"] for item in diagnostics)
    assert any(not item["accepted"] for item in diagnostics)


def test_jd_accepts_virtual_goods_candidate() -> None:
    accepted, diagnostics = bridge._coerce_bridge_items(
        "jd",
        raw_items=[
            {
                "skuId": "jd-v1",
                "skuName": "Q coin auto recharge instant delivery direct topup",
                "materialUrl": "https://item.jd.com/10001.html",
                "priceText": "Q coin auto recharge instant delivery direct topup Price 50.00",
                "listed_at": "2026-04-11T00:00:00Z",
            }
        ],
        body_text="search results",
        keyword="Q coin auto recharge",
        limit=5,
        virtual_goods_only=True,
    )

    assert len(accepted) == 1
    assert accepted[0]["skuId"] == "jd-v1"
    assert accepted[0]["item_type"] == "virtual_goods"
    assert accepted[0]["fulfillment_mode"] == "virtual"
    assert any(item["accepted"] for item in diagnostics)


def test_jd_rejects_physical_goods_noise_for_virtual_keyword() -> None:
    accepted, diagnostics = bridge._coerce_bridge_items(
        "jd",
        raw_items=[
            {
                "skuId": "jd-physical",
                "skuName": "Plastic toy coin prop set",
                "materialUrl": "https://item.jd.com/20001.html",
                "priceText": "Plastic toy coin prop set Price 8.88",
                "listed_at": "2026-04-11T00:00:00Z",
            }
        ],
        body_text="search results",
        keyword="Q coin auto recharge",
        limit=5,
        virtual_goods_only=True,
    )

    assert accepted == []
    assert diagnostics
    assert all(not item["accepted"] for item in diagnostics)


def test_jd_snapshot_state_allows_ready_virtual_goods_push() -> None:
    snapshot_state = bridge._build_snapshot_state(
        provider="jd",
        raw_items=[
            {
                "skuId": "jd-v1",
                "skuName": "Q coin auto recharge instant delivery direct topup",
                "materialUrl": "https://item.jd.com/10001.html",
                "priceText": "Price 50.00",
            }
        ],
        filtered_items=[
            {
                "skuId": "jd-v1",
                "skuName": "Q coin auto recharge instant delivery direct topup",
                "price": 50.0,
                "item_type": "virtual_goods",
                "fulfillment_mode": "virtual",
            }
        ],
        diagnostics=[
            {
                "title": "Q coin auto recharge instant delivery direct topup",
                "price": 50.0,
                "link_present": True,
                "fulfillment_mode": "virtual",
                "keyword_score": 4,
                "score": 0.99,
                "accepted": True,
                "source": "anchor",
            }
        ],
        login_required=False,
        virtual_goods_only_applied=True,
    )

    assert snapshot_state["page_state"] == "search_results"
    assert snapshot_state["accepted_item_count"] == 1
    assert snapshot_state["virtual_candidate_count"] == 1
    assert snapshot_state["ready_for_push"] is True


def test_jd_snapshot_state_marks_risk_challenge_not_ready_for_push() -> None:
    snapshot_state = bridge._build_snapshot_state(
        provider="jd",
        raw_items=[],
        filtered_items=[],
        diagnostics=[],
        login_required=False,
        risk_challenge_required=True,
        virtual_goods_only_applied=True,
    )

    assert snapshot_state["page_state"] == "risk_challenge"
    assert snapshot_state["risk_challenge_required"] is True
    assert snapshot_state["ready_for_push"] is False


def test_jd_selects_risk_challenge_page_over_unrelated_search_tab() -> None:
    selected = bridge._select_debug_page(
        "jd",
        [
            {
                "type": "page",
                "title": "拼多多",
                "url": "https://mobile.yangkeduo.com/search_result.html?search_key=Q",
                "webSocketDebuggerUrl": "ws://pdd",
                "id": "pdd",
            },
            {
                "type": "page",
                "title": "JD verification",
                "url": "https://cfe.m.jd.com/privatedomain/risk_handler/03101900/",
                "webSocketDebuggerUrl": "ws://jd-risk",
                "id": "jd-risk",
            },
        ],
        "https://search.jd.com/Search?keyword=Q%20coin%20auto%20recharge",
    )

    assert selected is not None
    assert selected["webSocketDebuggerUrl"] == "ws://jd-risk"
