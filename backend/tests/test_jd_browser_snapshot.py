from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

import browser_snapshot_bridge as bridge  # noqa: E402


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
