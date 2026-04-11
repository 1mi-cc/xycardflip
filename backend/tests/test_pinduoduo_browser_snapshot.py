from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

import browser_snapshot_bridge as bridge  # noqa: E402


def test_pinduoduo_keyword_variants_include_core_aliases() -> None:
    variants = bridge._keyword_variants("Pokemon Card PSA 10")
    lowered = {item.lower() for item in variants}
    assert "pokemon" in lowered
    assert "psa" in lowered
    assert "宝可梦" in lowered


def test_pinduoduo_coerce_bridge_items_stays_empty_for_login_like_page() -> None:
    accepted, diagnostics = bridge._coerce_bridge_items(
        "pinduoduo",
        raw_items=[],
        body_text="\n".join(
            [
                "手机登录",
                "扫码登录",
                "发送验证码",
                "同意协议并登录",
                "返回",
            ]
        ),
        keyword="Pokemon Card PSA 10",
        limit=5,
    )

    assert accepted == []
    assert diagnostics
    assert all(not item["accepted"] for item in diagnostics)


def test_pinduoduo_coerce_bridge_items_accepts_relevant_candidate() -> None:
    accepted, diagnostics = bridge._coerce_bridge_items(
        "pinduoduo",
        raw_items=[
            {
                "goods_id": "pdd-1",
                "goods_name": "宝可梦 快龙 ex PSA10 收藏卡",
                "goods_link": "https://mobile.yangkeduo.com/goods.html?goods_id=123456",
                "priceText": "宝可梦 快龙 ex PSA10 收藏卡 到手价 ¥63.00",
                "listed_at": "2026-04-11T00:00:00Z",
            }
        ],
        body_text="",
        keyword="Pokemon Card PSA 10",
        limit=5,
    )

    assert len(accepted) == 1
    assert accepted[0]["goods_id"] == "pdd-1"
    assert any(item["accepted"] for item in diagnostics)
