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
