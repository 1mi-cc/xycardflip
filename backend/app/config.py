from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parents[1]


def _get_default_sqlite_path() -> str:
    if getattr(sys, "frozen", False):
        app_data_root = Path(os.getenv("LOCALAPPDATA", Path.home()))
        return str(app_data_root / "CardFlipAssistant" / "data" / "trading.db")
    return str(BASE_DIR / "data" / "trading.db")


DEFAULT_SQLITE_PATH = _get_default_sqlite_path()


def _get_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    text = raw.strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None:
        return default
    text = raw.strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _normalize_strategy_profile(value: str | None) -> str:
    text = (value or "").strip().lower()
    if text in {"aggressive", "agg", "fast"}:
        return "aggressive"
    if text in {"conservative", "cons", "safe"}:
        return "conservative"
    return "balanced"


def normalize_strategy_profile(value: str | None) -> str:
    return _normalize_strategy_profile(value)


def _get_profile_float(
    key: str,
    profile: str,
    default: float,
) -> float:
    raw_global = os.getenv(f"STRATEGY_{key}")
    if raw_global is not None and raw_global.strip() != "":
        try:
            return float(raw_global.strip())
        except ValueError:
            pass
    raw_profile = os.getenv(f"STRATEGY_{profile.upper()}_{key}")
    if raw_profile is not None and raw_profile.strip() != "":
        try:
            return float(raw_profile.strip())
        except ValueError:
            pass
    return default


def _get_profile_bool(
    key: str,
    profile: str,
    default: bool,
) -> bool:
    raw_global = os.getenv(f"STRATEGY_{key}")
    if raw_global is not None and raw_global.strip() != "":
        return raw_global.strip().lower() in {"1", "true", "yes", "on"}
    raw_profile = os.getenv(f"STRATEGY_{profile.upper()}_{key}")
    if raw_profile is not None and raw_profile.strip() != "":
        return raw_profile.strip().lower() in {"1", "true", "yes", "on"}
    return default


@dataclass(frozen=True)
class StrategyThresholds:
    min_score: float
    min_roi: float
    max_risk_score: float
    allow_blocked_review: bool
    auto_reject_unqualified: bool


def get_strategy_thresholds(profile: str | None = None) -> StrategyThresholds:
    selected = _normalize_strategy_profile(profile or os.getenv("STRATEGY_PROFILE", "balanced"))

    defaults = {
        "aggressive": {
            "min_score": 50.0,
            "min_roi": 0.08,
            "max_risk_score": 55.0,
            "allow_blocked_review": True,
            "auto_reject_unqualified": False,
        },
        "balanced": {
            "min_score": 60.0,
            "min_roi": 0.12,
            "max_risk_score": 40.0,
            "allow_blocked_review": True,
            "auto_reject_unqualified": True,
        },
        "conservative": {
            "min_score": 70.0,
            "min_roi": 0.18,
            "max_risk_score": 30.0,
            "allow_blocked_review": False,
            "auto_reject_unqualified": True,
        },
    }
    base = defaults.get(selected, defaults["balanced"])

    min_score = _get_profile_float("MIN_SCORE", selected, base["min_score"])
    min_roi = _get_profile_float("MIN_ROI", selected, base["min_roi"])
    max_risk_score = _get_profile_float("MAX_RISK_SCORE", selected, base["max_risk_score"])
    allow_blocked_review = _get_profile_bool(
        "ALLOW_BLOCKED_REVIEW",
        selected,
        base["allow_blocked_review"],
    )
    auto_reject_unqualified = _get_profile_bool(
        "AUTO_REJECT_UNQUALIFIED",
        selected,
        base["auto_reject_unqualified"],
    )

    return StrategyThresholds(
        min_score=min_score,
        min_roi=min_roi,
        max_risk_score=max_risk_score,
        allow_blocked_review=allow_blocked_review,
        auto_reject_unqualified=auto_reject_unqualified,
    )


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    app_name: str = os.getenv("APP_NAME", "Card Flip Assistant API")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = _get_int("API_PORT", 8000)
    sqlite_path: str = os.getenv("SQLITE_PATH", DEFAULT_SQLITE_PATH)

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    platform_fee_rate: float = _get_float("PLATFORM_FEE_RATE", 0.06)
    default_shipping_cost: float = _get_float("DEFAULT_SHIPPING_COST", 8.0)
    min_profit: float = _get_float("MIN_PROFIT", 20.0)
    min_roi: float = _get_float("MIN_ROI", 0.12)
    risk_discount: float = _get_float("RISK_DISCOUNT", 0.05)
    risk_block_score: float = _get_float("RISK_BLOCK_SCORE", 70.0)
    risk_review_score: float = _get_float("RISK_REVIEW_SCORE", 40.0)
    risk_min_model_confidence: float = _get_float("RISK_MIN_MODEL_CONFIDENCE", 0.45)
    risk_min_comparables: int = _get_int("RISK_MIN_COMPARABLES", 6)
    risk_max_ci_spread_ratio: float = _get_float("RISK_MAX_CI_SPREAD_RATIO", 0.35)
    risk_min_margin_ratio: float = _get_float("RISK_MIN_MARGIN_RATIO", 0.08)
    risk_seller_open_listing_limit: int = _get_int("RISK_SELLER_OPEN_LISTING_LIMIT", 12)
    risk_keyword_penalty: float = _get_float("RISK_KEYWORD_PENALTY", 18.0)
    risk_suspicious_keywords: str = os.getenv(
        "RISK_SUSPICIOUS_KEYWORDS",
        "urgent sale,quick sale,private chat,vx,wechat,prepay,outside platform,offline deal",
    )

    strategy_profile: str = _normalize_strategy_profile(os.getenv("STRATEGY_PROFILE", "balanced"))
    strategy_thresholds: StrategyThresholds = get_strategy_thresholds(strategy_profile)

    pricing_age_discount_per_day: float = _get_float(
        "PRICING_AGE_DISCOUNT_PER_DAY", 0.003
    )
    pricing_max_age_discount: float = _get_float("PRICING_MAX_AGE_DISCOUNT", 0.18)
    pricing_inventory_soft_cap: int = _get_int("PRICING_INVENTORY_SOFT_CAP", 25)
    pricing_stale_days: int = _get_int("PRICING_STALE_DAYS", 3)
    pricing_urgent_days: int = _get_int("PRICING_URGENT_DAYS", 7)
    pricing_mode_balanced_factor: float = _get_float(
        "PRICING_MODE_BALANCED_FACTOR", 1.00
    )
    pricing_mode_fast_exit_factor: float = _get_float(
        "PRICING_MODE_FAST_EXIT_FACTOR", 0.96
    )
    pricing_mode_profit_max_factor: float = _get_float(
        "PRICING_MODE_PROFIT_MAX_FACTOR", 1.05
    )
    pricing_volatility_discount_factor: float = _get_float(
        "PRICING_VOLATILITY_DISCOUNT_FACTOR", 0.25
    )
    pricing_max_volatility_discount: float = _get_float(
        "PRICING_MAX_VOLATILITY_DISCOUNT", 0.10
    )

    monitor_target_url: str = os.getenv(
        "MONITOR_TARGET_URL",
        "https://api.mock-market.com/v1/search/items?keyword=card",
    )
    monitor_timeout_sec: float = _get_float("MONITOR_TIMEOUT_SEC", 10.0)
    monitor_min_delay_sec: float = _get_float("MONITOR_MIN_DELAY_SEC", 1.5)
    monitor_max_delay_sec: float = _get_float("MONITOR_MAX_DELAY_SEC", 4.5)
    monitor_long_rest_probability: float = _get_float(
        "MONITOR_LONG_REST_PROBABILITY", 0.05
    )
    monitor_long_rest_min_sec: float = _get_float(
        "MONITOR_LONG_REST_MIN_SEC", 10.0
    )
    monitor_long_rest_max_sec: float = _get_float(
        "MONITOR_LONG_REST_MAX_SEC", 30.0
    )
    monitor_provider: str = os.getenv("MONITOR_PROVIDER", "xianyu")
    monitor_keyword: str = os.getenv("XIAN_YU_KEYWORD", "咸鱼之王功法")
    monitor_max_price: float = _get_float("MONITOR_MAX_PRICE", 100.0)
    monitor_day_delay_min: float = _get_float("MONITOR_DAY_DELAY_MIN", 15.0)
    monitor_day_delay_max: float = _get_float("MONITOR_DAY_DELAY_MAX", 30.0)
    monitor_peak_delay_min: float = _get_float("MONITOR_PEAK_DELAY_MIN", 3.0)
    monitor_peak_delay_max: float = _get_float("MONITOR_PEAK_DELAY_MAX", 8.0)
    monitor_night_delay_min: float = _get_float("MONITOR_NIGHT_DELAY_MIN", 25.0)
    monitor_night_delay_max: float = _get_float("MONITOR_NIGHT_DELAY_MAX", 45.0)
    monitor_circuit_max_errors: int = _get_int("MONITOR_CIRCUIT_MAX_ERRORS", 3)
    monitor_circuit_403_threshold: int = _get_int(
        "MONITOR_CIRCUIT_403_THRESHOLD", 2
    )
    monitor_circuit_cooldown_sec: float = _get_float(
        "MONITOR_CIRCUIT_COOLDOWN_SEC", 900.0
    )
    xianyu_search_url: str = os.getenv(
        "XIAN_YU_SEARCH_URL", "https://s.m.xianyu.com/search.htm"
    )
    xianyu_cookie: str = os.getenv("XIAN_YU_COOKIE", "")
    xianyu_cookie_provider_url: str = os.getenv(
        "XIAN_YU_COOKIE_PROVIDER_URL", "http://127.0.0.1:5000/api/cookies/latest"
    )
    xianyu_cookie_refresh_url: str = os.getenv(
        "XIAN_YU_COOKIE_REFRESH_URL", "http://127.0.0.1:5000/api/cookies/refresh"
    )
    xianyu_cookie_refresh_on_start: bool = _get_bool(
        "XIAN_YU_COOKIE_REFRESH_ON_START", False
    )
    xianyu_cookie_ttl_sec: int = _get_int("XIAN_YU_COOKIE_TTL_SEC", 540)
    monitor_pages: int = _get_int("MONITOR_PAGES", 1)
    monitor_use_proxy_pool: bool = _get_bool("MONITOR_USE_PROXY_POOL", False)
    proxy_pool_api: str = os.getenv("PROXY_POOL_API", "http://127.0.0.1:8899/")
    proxy_pool_params: str = os.getenv("PROXY_POOL_PARAMS", "types=0&count=3")

    vnpy_scan_interval_sec: int = _get_int("VNPY_SCAN_INTERVAL_SEC", 300)
    vnpy_scan_pages: int = _get_int("VNPY_SCAN_PAGES", _get_int("MONITOR_PAGES", 1))

    alert_email_enabled: bool = _get_bool("ALERT_EMAIL_ENABLED", False)
    alert_email_to: str = os.getenv("ALERT_EMAIL_TO", "")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = _get_int("SMTP_PORT", 465)
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = _get_bool("SMTP_USE_TLS", True)

    def ensure_paths(self) -> None:
        db_file = Path(self.sqlite_path).expanduser()
        db_file.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
