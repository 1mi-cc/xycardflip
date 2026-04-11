from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

import browser_session_keeper as keeper  # noqa: E402


def test_probe_state_detects_pinduoduo_login_page() -> None:
    state = keeper._infer_page_state(
        "pinduoduo",
        current_url="https://mobile.yangkeduo.com/login.html",
        page_title="鐧诲綍 - 涓汉",
    )

    assert state == "login"


def test_probe_state_detects_pinduoduo_search_results() -> None:
    state = keeper._infer_page_state(
        "pinduoduo",
        current_url="https://mobile.yangkeduo.com/search_result.html?search_key=Pokemon%20Card%20PSA%2010",
        page_title="Pokemon Card PSA 10",
    )

    assert state == "search_results"


def test_probe_state_treats_search_result_url_as_results_even_with_login_referrer() -> None:
    state = keeper._infer_page_state(
        "pinduoduo",
        current_url=(
            "https://mobile.yangkeduo.com/search_result.html?search_key=Q%E5%B8%81"
            "&refer_page_name=login"
        ),
        page_title="Q币 自动充值",
    )

    assert state == "search_results"
