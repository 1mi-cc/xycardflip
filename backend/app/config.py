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


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    app_name: str = os.getenv("APP_NAME", "Card Flip Assistant API")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    sqlite_path: str = os.getenv("SQLITE_PATH", DEFAULT_SQLITE_PATH)

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    platform_fee_rate: float = float(os.getenv("PLATFORM_FEE_RATE", "0.06"))
    default_shipping_cost: float = float(os.getenv("DEFAULT_SHIPPING_COST", "8.0"))
    min_profit: float = float(os.getenv("MIN_PROFIT", "20.0"))
    min_roi: float = float(os.getenv("MIN_ROI", "0.12"))
    risk_discount: float = float(os.getenv("RISK_DISCOUNT", "0.05"))
    risk_block_score: float = float(os.getenv("RISK_BLOCK_SCORE", "70"))
    risk_review_score: float = float(os.getenv("RISK_REVIEW_SCORE", "40"))
    risk_min_model_confidence: float = float(os.getenv("RISK_MIN_MODEL_CONFIDENCE", "0.45"))
    risk_min_comparables: int = int(os.getenv("RISK_MIN_COMPARABLES", "6"))
    risk_max_ci_spread_ratio: float = float(os.getenv("RISK_MAX_CI_SPREAD_RATIO", "0.35"))
    risk_min_margin_ratio: float = float(os.getenv("RISK_MIN_MARGIN_RATIO", "0.08"))
    risk_seller_open_listing_limit: int = int(os.getenv("RISK_SELLER_OPEN_LISTING_LIMIT", "12"))
    risk_keyword_penalty: float = float(os.getenv("RISK_KEYWORD_PENALTY", "18"))
    risk_suspicious_keywords: str = os.getenv(
        "RISK_SUSPICIOUS_KEYWORDS",
        "urgent sale,quick sale,private chat,vx,wechat,prepay,outside platform,offline deal",
    )
    pricing_age_discount_per_day: float = float(
        os.getenv("PRICING_AGE_DISCOUNT_PER_DAY", "0.003")
    )
    pricing_max_age_discount: float = float(os.getenv("PRICING_MAX_AGE_DISCOUNT", "0.18"))
    pricing_inventory_soft_cap: int = int(os.getenv("PRICING_INVENTORY_SOFT_CAP", "25"))
    pricing_stale_days: int = int(os.getenv("PRICING_STALE_DAYS", "3"))
    pricing_urgent_days: int = int(os.getenv("PRICING_URGENT_DAYS", "7"))
    pricing_mode_balanced_factor: float = float(
        os.getenv("PRICING_MODE_BALANCED_FACTOR", "1.00")
    )
    pricing_mode_fast_exit_factor: float = float(
        os.getenv("PRICING_MODE_FAST_EXIT_FACTOR", "0.96")
    )
    pricing_mode_profit_max_factor: float = float(
        os.getenv("PRICING_MODE_PROFIT_MAX_FACTOR", "1.05")
    )
    pricing_volatility_discount_factor: float = float(
        os.getenv("PRICING_VOLATILITY_DISCOUNT_FACTOR", "0.25")
    )
    pricing_max_volatility_discount: float = float(
        os.getenv("PRICING_MAX_VOLATILITY_DISCOUNT", "0.10")
    )

    monitor_target_url: str = os.getenv(
        "MONITOR_TARGET_URL",
        "https://api.mock-market.com/v1/search/items?keyword=card",
    )
    monitor_timeout_sec: float = float(os.getenv("MONITOR_TIMEOUT_SEC", "10"))
    monitor_min_delay_sec: float = float(os.getenv("MONITOR_MIN_DELAY_SEC", "1.5"))
    monitor_max_delay_sec: float = float(os.getenv("MONITOR_MAX_DELAY_SEC", "4.5"))
    monitor_long_rest_probability: float = float(
        os.getenv("MONITOR_LONG_REST_PROBABILITY", "0.05")
    )
    monitor_long_rest_min_sec: float = float(
        os.getenv("MONITOR_LONG_REST_MIN_SEC", "10")
    )
    monitor_long_rest_max_sec: float = float(
        os.getenv("MONITOR_LONG_REST_MAX_SEC", "30")
    )
    monitor_provider: str = os.getenv("MONITOR_PROVIDER", "xianyu")
    monitor_keyword: str = os.getenv("XIAN_YU_KEYWORD", "咸鱼之王功法")
    monitor_max_price: float = float(os.getenv("MONITOR_MAX_PRICE", "100"))
    monitor_day_delay_min: float = float(os.getenv("MONITOR_DAY_DELAY_MIN", "15"))
    monitor_day_delay_max: float = float(os.getenv("MONITOR_DAY_DELAY_MAX", "30"))
    monitor_peak_delay_min: float = float(os.getenv("MONITOR_PEAK_DELAY_MIN", "3"))
    monitor_peak_delay_max: float = float(os.getenv("MONITOR_PEAK_DELAY_MAX", "8"))
    monitor_night_delay_min: float = float(os.getenv("MONITOR_NIGHT_DELAY_MIN", "25"))
    monitor_night_delay_max: float = float(os.getenv("MONITOR_NIGHT_DELAY_MAX", "45"))
    monitor_circuit_max_errors: int = int(os.getenv("MONITOR_CIRCUIT_MAX_ERRORS", "3"))
    monitor_circuit_403_threshold: int = int(
        os.getenv("MONITOR_CIRCUIT_403_THRESHOLD", "2")
    )
    monitor_circuit_cooldown_sec: float = float(
        os.getenv("MONITOR_CIRCUIT_COOLDOWN_SEC", "900")
    )
    xianyu_search_url: str = os.getenv(
        "XIAN_YU_SEARCH_URL", "https://s.m.xianyu.com/search.htm"
    )
    xianyu_cookie: str = os.getenv("XIAN_YU_COOKIE", "")
    monitor_pages: int = int(os.getenv("MONITOR_PAGES", "1"))
    monitor_use_proxy_pool: bool = _get_bool("MONITOR_USE_PROXY_POOL", False)
    proxy_pool_api: str = os.getenv("PROXY_POOL_API", "http://127.0.0.1:8899/")
    proxy_pool_params: str = os.getenv("PROXY_POOL_PARAMS", "types=0&count=3")

    alert_email_enabled: bool = _get_bool("ALERT_EMAIL_ENABLED", False)
    alert_email_to: str = os.getenv("ALERT_EMAIL_TO", "")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "465"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = _get_bool("SMTP_USE_TLS", True)

    def ensure_paths(self) -> None:
        db_file = Path(self.sqlite_path).expanduser()
        db_file.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
