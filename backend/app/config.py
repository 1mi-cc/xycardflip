from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]

_dotenv_path: Path | None = None
env_override = os.getenv("DOTENV_PATH", "").strip()
if env_override:
    _dotenv_path = Path(env_override).expanduser()
elif getattr(sys, "frozen", False):
    _dotenv_path = Path(sys.executable).resolve().parent / ".env"
else:
    _dotenv_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=_dotenv_path if _dotenv_path and _dotenv_path.exists() else None)


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


def _clear_proxy_env_if_needed() -> None:
    if not _get_bool("NETWORK_IGNORE_ENV_PROXY", True):
        return
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    ):
        os.environ.pop(key, None)


_clear_proxy_env_if_needed()


def _parse_monitor_keywords(raw_keywords: str | None, fallback_keyword: str | None) -> tuple[str, ...]:
    raw_text = (raw_keywords or "").strip()
    parts = re.split(r"[,;\n\r|\uFF0C\uFF1B]+", raw_text)
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        token = part.strip()
        if not token:
            continue
        dedupe_key = token.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(token)
    if normalized:
        return tuple(normalized)

    fallback_text = (fallback_keyword or "").strip()
    if fallback_text:
        return (fallback_text,)
    return ("\u54b8\u9c7c\u4e4b\u738b\u529f\u6cd5",)


def _parse_csv_tokens(raw_value: str | None, fallback: tuple[str, ...] = ()) -> tuple[str, ...]:
    raw_text = (raw_value or "").strip()
    if not raw_text:
        return fallback
    parts = re.split(r"[,;\n\r|\uFF0C\uFF1B]+", raw_text)
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        token = part.strip()
        if not token:
            continue
        lowered = token.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(token)
    return tuple(normalized) if normalized else fallback


def _parse_int_tokens(raw_value: str | None, fallback: tuple[int, ...] = ()) -> tuple[int, ...]:
    values: list[int] = []
    seen: set[int] = set()
    for token in _parse_csv_tokens(raw_value):
        try:
            numeric = int(token)
        except ValueError:
            continue
        if numeric in seen:
            continue
        seen.add(numeric)
        values.append(numeric)
    return tuple(values) if values else fallback


def _normalize_strategy_profile(value: str | None) -> str:
    text = (value or "").strip().lower()
    if text in {"aggressive", "agg", "fast"}:
        return "aggressive"
    if text in {"conservative", "cons", "safe"}:
        return "conservative"
    return "balanced"


def normalize_strategy_profile(value: str | None) -> str:
    return _normalize_strategy_profile(value)


def _normalize_execution_action(value: str | None, default: str = "all") -> str:
    text = (value or "").strip().lower()
    if text in {"buy", "list", "sell", "all"}:
        return text
    return default


DEFAULT_UI_MENU_PERMISSIONS: tuple[str, ...] = (
    "dashboard:view",
    "cardflip:view",
)

DEFAULT_UI_ROLE_PERMISSIONS_ADMIN: tuple[str, ...] = DEFAULT_UI_MENU_PERMISSIONS
DEFAULT_UI_ROLE_PERMISSIONS_OPS: tuple[str, ...] = (
    "cardflip:view",
)
DEFAULT_UI_ROLE_PERMISSIONS_VIEWER: tuple[str, ...] = (
    "cardflip:view",
)


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
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = _get_int("API_PORT", 8000)
    uptime_kuma_enabled: bool = _get_bool("UPTIME_KUMA_ENABLED", False)
    uptime_kuma_url: str = os.getenv("UPTIME_KUMA_URL", "http://127.0.0.1:3001")
    supabase_enabled: bool = _get_bool("SUPABASE_ENABLED", False)
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_schema: str = os.getenv("SUPABASE_SCHEMA", "public")
    supabase_table_prefix: str = os.getenv("SUPABASE_TABLE_PREFIX", "cardflip_")
    supabase_timeout_sec: float = _get_float("SUPABASE_TIMEOUT_SEC", 8.0)
    supabase_sync_interval_sec: int = _get_int("SUPABASE_SYNC_INTERVAL_SEC", 30)
    supabase_sync_batch_size: int = _get_int("SUPABASE_SYNC_BATCH_SIZE", 200)
    auto_start_supabase_sync: bool = _get_bool("AUTO_START_SUPABASE_SYNC", False)
    ui_auth_username: str = os.getenv("UI_AUTH_USERNAME", "operator")
    ui_auth_password: str = os.getenv("UI_AUTH_PASSWORD", "")
    ui_auth_nickname: str = os.getenv("UI_AUTH_NICKNAME", "本地操作员")
    ui_auth_default_role: str = os.getenv("UI_AUTH_DEFAULT_ROLE", "admin").strip().lower() or "admin"
    ui_auth_session_hours: int = _get_int("UI_AUTH_SESSION_HOURS", 72)
    ui_auth_enforce_permissions: bool = _get_bool("UI_AUTH_ENFORCE_PERMISSIONS", True)
    ui_user_roles: str = os.getenv("UI_USER_ROLES", "")
    ui_menu_roles: tuple[str, ...] = _parse_csv_tokens(
        os.getenv("UI_MENU_ROLES", "admin"),
        fallback=("admin",),
    )
    ui_menu_permissions: tuple[str, ...] = _parse_csv_tokens(
        os.getenv("UI_MENU_PERMISSIONS", ",".join(DEFAULT_UI_MENU_PERMISSIONS)),
        fallback=DEFAULT_UI_MENU_PERMISSIONS,
    )
    ui_role_permissions_admin: tuple[str, ...] = _parse_csv_tokens(
        os.getenv("UI_ROLE_PERMISSIONS_ADMIN", ",".join(DEFAULT_UI_ROLE_PERMISSIONS_ADMIN)),
        fallback=DEFAULT_UI_ROLE_PERMISSIONS_ADMIN,
    )
    ui_role_permissions_ops: tuple[str, ...] = _parse_csv_tokens(
        os.getenv("UI_ROLE_PERMISSIONS_OPS", ",".join(DEFAULT_UI_ROLE_PERMISSIONS_OPS)),
        fallback=DEFAULT_UI_ROLE_PERMISSIONS_OPS,
    )
    ui_role_permissions_viewer: tuple[str, ...] = _parse_csv_tokens(
        os.getenv("UI_ROLE_PERMISSIONS_VIEWER", ",".join(DEFAULT_UI_ROLE_PERMISSIONS_VIEWER)),
        fallback=DEFAULT_UI_ROLE_PERMISSIONS_VIEWER,
    )
    sqlite_path: str = os.getenv("SQLITE_PATH", DEFAULT_SQLITE_PATH)
    sqlite_journal_mode: str = os.getenv("SQLITE_JOURNAL_MODE", "WAL").strip().upper() or "WAL"
    sqlite_synchronous: str = os.getenv("SQLITE_SYNCHRONOUS", "NORMAL").strip().upper() or "NORMAL"
    sqlite_busy_timeout_ms: int = _get_int("SQLITE_BUSY_TIMEOUT_MS", 5000)
    db_write_batch_size: int = _get_int("DB_WRITE_BATCH_SIZE", 50)

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_key_source_path: str = os.getenv("GEMINI_KEY_SOURCE_PATH", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    ragflow_enabled: bool = _get_bool("RAGFLOW_ENABLED", False)
    ragflow_base_url: str = os.getenv("RAGFLOW_BASE_URL", "http://127.0.0.1:9380")
    ragflow_api_key: str = os.getenv("RAGFLOW_API_KEY", "")
    ragflow_chat_id: str = os.getenv("RAGFLOW_CHAT_ID", "")
    ragflow_market_dataset_id: str = os.getenv("RAGFLOW_MARKET_DATASET_ID", "")
    ragflow_market_dataset_name: str = os.getenv("RAGFLOW_MARKET_DATASET_NAME", "cardflip_market_knowledge")
    ragflow_timeout_sec: float = _get_float("RAGFLOW_TIMEOUT_SEC", 45.0)

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

    single_account_mode: bool = _get_bool("SINGLE_ACCOUNT_MODE", False)
    strategy_profile: str = _normalize_strategy_profile(os.getenv("STRATEGY_PROFILE", "balanced"))
    strategy_thresholds: StrategyThresholds = get_strategy_thresholds(strategy_profile)
    single_account_validation_min_sold_count: int = _get_int(
        "SINGLE_ACCOUNT_VALIDATION_MIN_SOLD_COUNT",
        6,
    )
    single_account_validation_min_source_count: int = _get_int(
        "SINGLE_ACCOUNT_VALIDATION_MIN_SOURCE_COUNT",
        2,
    )
    single_account_validation_min_profit_hit_rate: float = _get_float(
        "SINGLE_ACCOUNT_VALIDATION_MIN_PROFIT_HIT_RATE",
        0.55,
    )
    single_account_validation_min_avg_roi: float = _get_float(
        "SINGLE_ACCOUNT_VALIDATION_MIN_AVG_ROI",
        0.08,
    )
    single_account_validation_max_business_bans: int = _get_int(
        "SINGLE_ACCOUNT_VALIDATION_MAX_BUSINESS_BANS",
        0,
    )
    single_account_validation_max_source_share: float = _get_float(
        "SINGLE_ACCOUNT_VALIDATION_MAX_SOURCE_SHARE",
        0.75,
    )

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
    pricing_rag_sentiment_enabled: bool = _get_bool("PRICING_RAG_SENTIMENT_ENABLED", False)
    pricing_rag_min_confidence: float = _get_float("PRICING_RAG_MIN_CONFIDENCE", 0.45)
    pricing_rag_max_adjustment: float = _get_float("PRICING_RAG_MAX_ADJUSTMENT", 0.08)

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
    monitor_keyword: str = os.getenv("XIAN_YU_KEYWORD", "\u54b8\u9c7c\u4e4b\u738b\u529f\u6cd5")
    monitor_keywords_raw: str = os.getenv("XIAN_YU_KEYWORDS", "")
    monitor_keywords: tuple[str, ...] = _parse_monitor_keywords(
        os.getenv("XIAN_YU_KEYWORDS", ""),
        os.getenv("XIAN_YU_KEYWORD", "\u54b8\u9c7c\u4e4b\u738b\u529f\u6cd5"),
    )
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
    monitor_auto_scan_after_ingest: bool = _get_bool("MONITOR_AUTO_SCAN_AFTER_INGEST", False)
    monitor_auto_scan_limit: int = _get_int("MONITOR_AUTO_SCAN_LIMIT", 80)
    monitor_health_window_size: int = _get_int("MONITOR_HEALTH_WINDOW_SIZE", 40)
    monitor_health_min_samples: int = _get_int("MONITOR_HEALTH_MIN_SAMPLES", 10)
    monitor_health_min_success_rate: float = _get_float("MONITOR_HEALTH_MIN_SUCCESS_RATE", 0.35)
    monitor_user_agents: tuple[str, ...] = _parse_csv_tokens(
        os.getenv("MONITOR_USER_AGENTS", ""),
        fallback=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ),
    )
    auto_start_monitor: bool = _get_bool("AUTO_START_MONITOR", False)
    xianyu_search_url: str = os.getenv(
        "XIAN_YU_SEARCH_URL", "https://s.m.xianyu.com/search.htm"
    )
    xianyu_mobile_user_agent: str = os.getenv(
        "XIAN_YU_MOBILE_USER_AGENT",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
        "Mobile/15E148 Safari/604.1",
    )
    xianyu_desktop_user_agent: str = os.getenv(
        "XIAN_YU_DESKTOP_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36",
    )
    xianyu_accept_language: str = os.getenv("XIAN_YU_ACCEPT_LANGUAGE", "zh-CN,zh;q=0.9")
    xianyu_mtop_app_key: str = os.getenv("XIAN_YU_MTOP_APP_KEY", "34839810")
    xianyu_mtop_api: str = os.getenv(
        "XIAN_YU_MTOP_API",
        "mtop.taobao.idlemtopsearch.pc.search",
    )
    xianyu_mtop_url: str = os.getenv(
        "XIAN_YU_MTOP_URL",
        "https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/",
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
    xianyu_cookie_auto_local_refresh: bool = _get_bool(
        "XIAN_YU_COOKIE_AUTO_LOCAL_REFRESH",
        True,
    )
    xianyu_cookie_refresh_min_ttl_sec: int = _get_int(
        "XIAN_YU_COOKIE_REFRESH_MIN_TTL_SEC",
        1800,
    )
    monitor_pages: int = _get_int("MONITOR_PAGES", 1)
    monitor_use_proxy_pool: bool = _get_bool("MONITOR_USE_PROXY_POOL", False)
    proxy_pool_api: str = os.getenv("PROXY_POOL_API", "http://127.0.0.1:8899/")
    proxy_pool_params: str = os.getenv("PROXY_POOL_PARAMS", "types=0&count=3")
    local_proxy_url: str = os.getenv("LOCAL_PROXY_URL", "")
    network_ignore_env_proxy: bool = _get_bool("NETWORK_IGNORE_ENV_PROXY", True)
    network_force_proxy_only: bool = _get_bool("NETWORK_FORCE_PROXY_ONLY", True)
    network_force_proxy_url: str = os.getenv("NETWORK_FORCE_PROXY_URL", "")
    proxy_bad_ttl_sec: int = _get_int("PROXY_BAD_TTL_SEC", 600)
    proxy_bad_ttl_jitter_sec: float = _get_float("PROXY_BAD_TTL_JITTER_SEC", 30.0)
    proxy_max_failures: int = _get_int("PROXY_MAX_FAILURES", 2)
    proxy_rotation_cooldown_sec: float = _get_float("PROXY_ROTATION_COOLDOWN_SEC", 2.0)

    execution_provider: str = os.getenv("EXECUTION_PROVIDER", "mock")
    execution_timeout_sec: float = _get_float("EXECUTION_TIMEOUT_SEC", 8.0)
    execution_auth_token: str = os.getenv("EXECUTION_AUTH_TOKEN", "")
    execution_webhook_secret: str = os.getenv("EXECUTION_WEBHOOK_SECRET", "")
    execution_webhook_max_retries: int = _get_int("EXECUTION_WEBHOOK_MAX_RETRIES", 2)
    execution_webhook_retry_backoff_sec: float = _get_float(
        "EXECUTION_WEBHOOK_RETRY_BACKOFF_SEC", 1.5
    )
    execution_webhook_buy_url: str = os.getenv("EXECUTION_WEBHOOK_BUY_URL", "")
    execution_webhook_list_url: str = os.getenv("EXECUTION_WEBHOOK_LIST_URL", "")
    execution_webhook_sell_url: str = os.getenv("EXECUTION_WEBHOOK_SELL_URL", "")
    execution_live_enabled: bool = _get_bool("EXECUTION_LIVE_ENABLED", False)
    execution_live_confirm_token: str = os.getenv("EXECUTION_LIVE_CONFIRM_TOKEN", "")
    execution_live_max_buy_price: float = _get_float("EXECUTION_LIVE_MAX_BUY_PRICE", 0.0)
    execution_live_min_list_profit_ratio: float = _get_float(
        "EXECUTION_LIVE_MIN_LIST_PROFIT_RATIO", 0.0
    )
    execution_live_min_sell_profit_ratio: float = _get_float(
        "EXECUTION_LIVE_MIN_SELL_PROFIT_RATIO", 0.0
    )
    execution_retry_enabled: bool = _get_bool("EXECUTION_RETRY_ENABLED", False)
    execution_retry_interval_sec: int = _get_int("EXECUTION_RETRY_INTERVAL_SEC", 45)
    execution_retry_batch_size: int = _get_int("EXECUTION_RETRY_BATCH_SIZE", 20)
    execution_retry_action: str = _normalize_execution_action(
        os.getenv("EXECUTION_RETRY_ACTION", "all")
    )
    execution_retry_dry_run: bool = _get_bool("EXECUTION_RETRY_DRY_RUN", True)
    execution_retry_force: bool = _get_bool("EXECUTION_RETRY_FORCE", False)
    execution_retry_confirm_token: str = os.getenv("EXECUTION_RETRY_CONFIRM_TOKEN", "")
    execution_business_ban_status_codes: tuple[int, ...] = _parse_int_tokens(
        os.getenv("EXECUTION_BUSINESS_BAN_STATUS_CODES", "401,403,407,418,423,429"),
        fallback=(401, 403, 407, 418, 423, 429),
    )
    execution_business_ban_codes: tuple[str, ...] = _parse_csv_tokens(
        os.getenv(
            "EXECUTION_BUSINESS_BAN_CODES",
            "BIZ_BAN,RISK_BLOCK,SECURITY_BLOCK,ACCOUNT_LIMIT,FREQUENCY_LIMIT",
        ),
    )
    execution_auto_rotate_proxy_on_ban: bool = _get_bool(
        "EXECUTION_AUTO_ROTATE_PROXY_ON_BAN",
        True,
    )
    automation_default_include_monitor: bool = _get_bool(
        "AUTOMATION_DEFAULT_INCLUDE_MONITOR", True
    )
    automation_default_include_scan: bool = _get_bool("AUTOMATION_DEFAULT_INCLUDE_SCAN", True)
    automation_default_include_autotrade: bool = _get_bool(
        "AUTOMATION_DEFAULT_INCLUDE_AUTOTRADE", True
    )
    automation_default_include_execution_retry: bool = _get_bool(
        "AUTOMATION_DEFAULT_INCLUDE_EXECUTION_RETRY", True
    )
    automation_default_include_supabase_sync: bool = _get_bool(
        "AUTOMATION_DEFAULT_INCLUDE_SUPABASE_SYNC",
        False,
    )
    automation_default_scan_limit: int = _get_int("AUTOMATION_DEFAULT_SCAN_LIMIT", 120)
    operating_state_execution_window: int = _get_int("OPERATING_STATE_EXECUTION_WINDOW", 24)
    operating_state_min_monitor_samples: int = _get_int("OPERATING_STATE_MIN_MONITOR_SAMPLES", 6)
    operating_state_min_execution_samples: int = _get_int(
        "OPERATING_STATE_MIN_EXECUTION_SAMPLES",
        6,
    )
    operating_state_cautious_success_rate: float = _get_float(
        "OPERATING_STATE_CAUTIOUS_SUCCESS_RATE",
        0.75,
    )
    operating_state_recovery_success_rate: float = _get_float(
        "OPERATING_STATE_RECOVERY_SUCCESS_RATE",
        0.45,
    )
    operating_state_cautious_failure_rate: float = _get_float(
        "OPERATING_STATE_CAUTIOUS_FAILURE_RATE",
        0.35,
    )
    operating_state_recovery_failure_rate: float = _get_float(
        "OPERATING_STATE_RECOVERY_FAILURE_RATE",
        0.60,
    )
    operating_state_cautious_business_bans: int = _get_int(
        "OPERATING_STATE_CAUTIOUS_BUSINESS_BANS",
        1,
    )
    operating_state_recovery_business_bans: int = _get_int(
        "OPERATING_STATE_RECOVERY_BUSINESS_BANS",
        3,
    )
    operating_state_cautious_limit_factor: float = _get_float(
        "OPERATING_STATE_CAUTIOUS_LIMIT_FACTOR",
        0.5,
    )
    operating_state_recovery_limit_factor: float = _get_float(
        "OPERATING_STATE_RECOVERY_LIMIT_FACTOR",
        0.2,
    )

    vnpy_scan_interval_sec: int = _get_int("VNPY_SCAN_INTERVAL_SEC", 300)
    vnpy_scan_pages: int = _get_int("VNPY_SCAN_PAGES", _get_int("MONITOR_PAGES", 1))

    auto_approve_enabled: bool = _get_bool("AUTO_APPROVE_ENABLED", False)
    auto_approve_interval_sec: int = _get_int("AUTO_APPROVE_INTERVAL_SEC", 30)
    auto_approve_batch_size: int = _get_int("AUTO_APPROVE_BATCH_SIZE", 10)
    auto_approve_min_score: float = _get_float("AUTO_APPROVE_MIN_SCORE", 75.0)
    auto_approve_min_roi: float = _get_float("AUTO_APPROVE_MIN_ROI", 0.18)
    auto_approve_max_risk_score: float = _get_float("AUTO_APPROVE_MAX_RISK_SCORE", 30.0)
    auto_approve_require_risk_score: bool = _get_bool("AUTO_APPROVE_REQUIRE_RISK_SCORE", True)
    auto_approve_approved_by: str = os.getenv("AUTO_APPROVE_APPROVED_BY", "autotrade_bot")
    auto_approve_note: str = os.getenv("AUTO_APPROVE_NOTE", "auto approved by service")
    auto_execute_buy_on_approve: bool = _get_bool("AUTO_EXECUTE_BUY_ON_APPROVE", False)
    auto_execute_buy_dry_run: bool = _get_bool("AUTO_EXECUTE_BUY_DRY_RUN", True)
    auto_execute_list_on_buy_success: bool = _get_bool(
        "AUTO_EXECUTE_LIST_ON_BUY_SUCCESS", False
    )
    auto_execute_list_dry_run: bool = _get_bool("AUTO_EXECUTE_LIST_DRY_RUN", True)
    auto_approve_max_consecutive_losses: int = _get_int("AUTO_APPROVE_MAX_CONSECUTIVE_LOSSES", 3)
    auto_approve_daily_loss_limit: float = _get_float("AUTO_APPROVE_DAILY_LOSS_LIMIT", 100.0)
    auto_approve_loss_recovery_enabled: bool = _get_bool("AUTO_APPROVE_LOSS_RECOVERY_ENABLED", True)
    auto_approve_loss_recovery_cooldown_hours: int = _get_int(
        "AUTO_APPROVE_LOSS_RECOVERY_COOLDOWN_HOURS",
        12,
    )
    auto_approve_seller_freeze_enabled: bool = _get_bool("AUTO_APPROVE_SELLER_FREEZE_ENABLED", True)
    auto_approve_seller_freeze_hours: int = _get_int("AUTO_APPROVE_SELLER_FREEZE_HOURS", 48)
    auto_approve_seller_freeze_min_sold_count: int = _get_int(
        "AUTO_APPROVE_SELLER_FREEZE_MIN_SOLD_COUNT",
        2,
    )
    auto_approve_seller_observe_enabled: bool = _get_bool("AUTO_APPROVE_SELLER_OBSERVE_ENABLED", True)
    auto_approve_seller_observe_hours: int = _get_int("AUTO_APPROVE_SELLER_OBSERVE_HOURS", 72)
    auto_approve_seller_observe_base_multiplier: float = _get_float(
        "AUTO_APPROVE_SELLER_OBSERVE_BASE_MULTIPLIER",
        0.6,
    )
    auto_approve_seller_observe_release_streak: int = _get_int(
        "AUTO_APPROVE_SELLER_OBSERVE_RELEASE_STREAK",
        3,
    )
    auto_approve_source_observe_base_multiplier: float = _get_float(
        "AUTO_APPROVE_SOURCE_OBSERVE_BASE_MULTIPLIER",
        0.2,
    )
    auto_approve_source_observe_release_streak: int = _get_int(
        "AUTO_APPROVE_SOURCE_OBSERVE_RELEASE_STREAK",
        3,
    )
    auto_approve_source_cashout_max_holding_days: float = _get_float(
        "AUTO_APPROVE_SOURCE_CASHOUT_MAX_HOLDING_DAYS",
        5.0,
    )
    auto_approve_portfolio_max_deployed_capital: float = _get_float(
        "AUTO_APPROVE_PORTFOLIO_MAX_DEPLOYED_CAPITAL",
        0.0,
    )
    auto_approve_max_source_capital_share: float = _get_float(
        "AUTO_APPROVE_MAX_SOURCE_CAPITAL_SHARE",
        0.6,
    )
    auto_approve_max_cluster_batch_share: float = _get_float(
        "AUTO_APPROVE_MAX_CLUSTER_BATCH_SHARE",
        0.6,
    )
    auto_approve_max_cluster_capital_share: float = _get_float(
        "AUTO_APPROVE_MAX_CLUSTER_CAPITAL_SHARE",
        0.6,
    )
    auto_approve_seller_reputation_decay_days: float = _get_float(
        "AUTO_APPROVE_SELLER_REPUTATION_DECAY_DAYS",
        14.0,
    )
    auto_tune_auto_apply_enabled: bool = _get_bool("AUTO_TUNE_AUTO_APPLY_ENABLED", False)
    auto_tune_cooldown_hours: int = _get_int("AUTO_TUNE_COOLDOWN_HOURS", 24)
    auto_tune_min_closed_batches: int = _get_int("AUTO_TUNE_MIN_CLOSED_BATCHES", 2)
    auto_tune_latest_min_sold_count: int = _get_int("AUTO_TUNE_LATEST_MIN_SOLD_COUNT", 5)
    auto_tune_previous_min_sold_count: int = _get_int("AUTO_TUNE_PREVIOUS_MIN_SOLD_COUNT", 3)
    observation_baseline_min_hit_rate: float = _get_float(
        "OBSERVATION_BASELINE_MIN_HIT_RATE",
        0.55,
    )
    observation_baseline_min_avg_roi: float = _get_float(
        "OBSERVATION_BASELINE_MIN_AVG_ROI",
        0.08,
    )
    observation_baseline_max_avg_holding_days: float = _get_float(
        "OBSERVATION_BASELINE_MAX_AVG_HOLDING_DAYS",
        7.0,
    )
    observation_baseline_min_last_7d_net_profit: float = _get_float(
        "OBSERVATION_BASELINE_MIN_LAST_7D_NET_PROFIT",
        0.0,
    )
    observation_baseline_min_monitor_success_rate: float = _get_float(
        "OBSERVATION_BASELINE_MIN_MONITOR_SUCCESS_RATE",
        0.65,
    )
    observation_baseline_min_live_execution_samples: int = _get_int(
        "OBSERVATION_BASELINE_MIN_LIVE_EXECUTION_SAMPLES",
        6,
    )
    observation_baseline_max_live_execution_failure_rate: float = _get_float(
        "OBSERVATION_BASELINE_MAX_LIVE_EXECUTION_FAILURE_RATE",
        0.35,
    )
    observation_baseline_max_live_execution_business_bans: int = _get_int(
        "OBSERVATION_BASELINE_MAX_LIVE_EXECUTION_BUSINESS_BANS",
        0,
    )
    auto_start_autotrade: bool = _get_bool("AUTO_START_AUTOTRADE", False)
    auto_start_execution_retry: bool = _get_bool("AUTO_START_EXECUTION_RETRY", False)
    autotrade_alert_email_auto_enabled: bool = _get_bool(
        "AUTOTRADE_ALERT_EMAIL_AUTO_ENABLED",
        False,
    )
    autotrade_alert_escalation_minutes: int = _get_int(
        "AUTOTRADE_ALERT_ESCALATION_MINUTES",
        60,
    )
    autotrade_alert_ack_timeout_minutes: int = _get_int(
        "AUTOTRADE_ALERT_ACK_TIMEOUT_MINUTES",
        240,
    )
    autotrade_alert_renotify_minutes: int = _get_int(
        "AUTOTRADE_ALERT_RENOTIFY_MINUTES",
        180,
    )
    autotrade_alert_email_min_severity: str = os.getenv(
        "AUTOTRADE_ALERT_EMAIL_MIN_SEVERITY",
        "warning",
    ).strip().lower() or "warning"
    autotrade_alert_email_cooldown_minutes: int = _get_int(
        "AUTOTRADE_ALERT_EMAIL_COOLDOWN_MINUTES",
        30,
    )
    autotrade_alert_webhook_auto_enabled: bool = _get_bool(
        "AUTOTRADE_ALERT_WEBHOOK_AUTO_ENABLED",
        False,
    )
    autotrade_alert_webhook_min_severity: str = os.getenv(
        "AUTOTRADE_ALERT_WEBHOOK_MIN_SEVERITY",
        "error",
    ).strip().lower() or "error"
    autotrade_alert_webhook_cooldown_minutes: int = _get_int(
        "AUTOTRADE_ALERT_WEBHOOK_COOLDOWN_MINUTES",
        30,
    )
    autotrade_alert_slack_auto_enabled: bool = _get_bool(
        "AUTOTRADE_ALERT_SLACK_AUTO_ENABLED",
        False,
    )
    autotrade_alert_slack_min_severity: str = os.getenv(
        "AUTOTRADE_ALERT_SLACK_MIN_SEVERITY",
        "error",
    ).strip().lower() or "error"
    autotrade_alert_slack_cooldown_minutes: int = _get_int(
        "AUTOTRADE_ALERT_SLACK_COOLDOWN_MINUTES",
        30,
    )
    autotrade_alert_slack_min_stage: int = _get_int(
        "AUTOTRADE_ALERT_SLACK_MIN_STAGE",
        1,
    )
    autotrade_alert_telegram_auto_enabled: bool = _get_bool(
        "AUTOTRADE_ALERT_TELEGRAM_AUTO_ENABLED",
        False,
    )
    autotrade_alert_telegram_min_severity: str = os.getenv(
        "AUTOTRADE_ALERT_TELEGRAM_MIN_SEVERITY",
        "error",
    ).strip().lower() or "error"
    autotrade_alert_telegram_cooldown_minutes: int = _get_int(
        "AUTOTRADE_ALERT_TELEGRAM_COOLDOWN_MINUTES",
        30,
    )
    autotrade_alert_telegram_min_stage: int = _get_int(
        "AUTOTRADE_ALERT_TELEGRAM_MIN_STAGE",
        2,
    )
    autotrade_incident_auto_assign_enabled: bool = _get_bool(
        "AUTOTRADE_INCIDENT_AUTO_ASSIGN_ENABLED",
        True,
    )
    autotrade_incident_default_owner: str = os.getenv(
        "AUTOTRADE_INCIDENT_DEFAULT_OWNER",
        "ops_default",
    ).strip()
    autotrade_incident_rota_timezone: str = os.getenv(
        "AUTOTRADE_INCIDENT_ROTA_TIMEZONE",
        "UTC",
    ).strip() or "UTC"
    autotrade_incident_default_owner_schedule: str = os.getenv(
        "AUTOTRADE_INCIDENT_DEFAULT_OWNER_SCHEDULE",
        "",
    ).strip()
    autotrade_incident_high_priority_owner: str = os.getenv(
        "AUTOTRADE_INCIDENT_HIGH_PRIORITY_OWNER",
        "ops_high_priority",
    ).strip()
    autotrade_incident_high_priority_owner_schedule: str = os.getenv(
        "AUTOTRADE_INCIDENT_HIGH_PRIORITY_OWNER_SCHEDULE",
        "",
    ).strip()
    autotrade_incident_critical_priority_owner: str = os.getenv(
        "AUTOTRADE_INCIDENT_CRITICAL_PRIORITY_OWNER",
        "ops_critical",
    ).strip()
    autotrade_incident_critical_priority_owner_schedule: str = os.getenv(
        "AUTOTRADE_INCIDENT_CRITICAL_PRIORITY_OWNER_SCHEDULE",
        "",
    ).strip()
    autotrade_incident_slack_owner: str = os.getenv(
        "AUTOTRADE_INCIDENT_SLACK_OWNER",
        "",
    ).strip()
    autotrade_incident_slack_owner_schedule: str = os.getenv(
        "AUTOTRADE_INCIDENT_SLACK_OWNER_SCHEDULE",
        "",
    ).strip()
    autotrade_incident_telegram_owner: str = os.getenv(
        "AUTOTRADE_INCIDENT_TELEGRAM_OWNER",
        "",
    ).strip()
    autotrade_incident_telegram_owner_schedule: str = os.getenv(
        "AUTOTRADE_INCIDENT_TELEGRAM_OWNER_SCHEDULE",
        "",
    ).strip()
    autotrade_incident_auto_escalate_on_sla_breach: bool = _get_bool(
        "AUTOTRADE_INCIDENT_AUTO_ESCALATE_ON_SLA_BREACH",
        True,
    )
    autotrade_incident_auto_resolve_enabled: bool = _get_bool(
        "AUTOTRADE_INCIDENT_AUTO_RESOLVE_ENABLED",
        True,
    )

    alert_email_enabled: bool = _get_bool("ALERT_EMAIL_ENABLED", False)
    alert_email_to: str = os.getenv("ALERT_EMAIL_TO", "")
    alert_slack_enabled: bool = _get_bool("ALERT_SLACK_ENABLED", False)
    alert_slack_webhook_url: str = os.getenv("ALERT_SLACK_WEBHOOK_URL", "")
    alert_telegram_enabled: bool = _get_bool("ALERT_TELEGRAM_ENABLED", False)
    alert_webhook_enabled: bool = _get_bool("ALERT_WEBHOOK_ENABLED", False)
    alert_webhook_provider: str = os.getenv(
        "ALERT_WEBHOOK_PROVIDER",
        "generic",
    ).strip().lower() or "generic"
    alert_webhook_url: str = os.getenv("ALERT_WEBHOOK_URL", "")
    alert_webhook_secret: str = os.getenv("ALERT_WEBHOOK_SECRET", "")
    alert_telegram_bot_token: str = os.getenv("ALERT_TELEGRAM_BOT_TOKEN", "")
    alert_telegram_chat_id: str = os.getenv("ALERT_TELEGRAM_CHAT_ID", "")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = _get_int("SMTP_PORT", 465)
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = _get_bool("SMTP_USE_TLS", True)

    def ensure_paths(self) -> None:
        db_file = Path(self.sqlite_path).expanduser()
        db_file.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()


def single_account_guardrail_status(current: Settings | None = None) -> dict[str, Any]:
    cfg = current or settings
    items: list[dict[str, Any]] = [
        {
            "code": "conservative_strategy",
            "label": "Strategy profile",
            "ok": cfg.strategy_profile == "conservative",
            "detail": f"strategy_profile={cfg.strategy_profile}",
        },
        {
            "code": "single_page_monitor",
            "label": "Monitor page budget",
            "ok": int(cfg.monitor_pages) <= 1,
            "detail": f"monitor_pages={cfg.monitor_pages}",
        },
        {
            "code": "slow_monitor_pacing",
            "label": "Monitor pacing",
            "ok": bool(
                float(cfg.monitor_day_delay_min) >= 20.0
                and float(cfg.monitor_peak_delay_min) >= 8.0
                and float(cfg.monitor_night_delay_min) >= 30.0
                and float(cfg.monitor_long_rest_probability) >= 0.10
            ),
            "detail": (
                "day>="
                f"{cfg.monitor_day_delay_min:.0f}s, peak>={cfg.monitor_peak_delay_min:.0f}s, "
                f"night>={cfg.monitor_night_delay_min:.0f}s, rest={cfg.monitor_long_rest_probability:.2f}"
            ),
        },
        {
            "code": "delay_floor_guarded",
            "label": "Delay floor",
            "ok": bool(
                float(cfg.monitor_min_delay_sec) >= 3.0
                and float(cfg.monitor_max_delay_sec) >= 8.0
            ),
            "detail": (
                "min="
                f"{cfg.monitor_min_delay_sec:.1f}s, max={cfg.monitor_max_delay_sec:.1f}s"
            ),
        },
        {
            "code": "defensive_circuit_tripwire",
            "label": "Circuit tripwire",
            "ok": bool(
                int(cfg.monitor_circuit_max_errors) <= 2
                and int(cfg.monitor_circuit_403_threshold) <= 1
                and float(cfg.monitor_circuit_cooldown_sec) >= 1800.0
            ),
            "detail": (
                "max_errors="
                f"{cfg.monitor_circuit_max_errors}, 403_threshold={cfg.monitor_circuit_403_threshold}, "
                f"cooldown={cfg.monitor_circuit_cooldown_sec:.0f}s"
            ),
        },
        {
            "code": "manual_service_start",
            "label": "Auto start",
            "ok": not bool(
                cfg.auto_start_monitor
                or cfg.auto_start_autotrade
                or cfg.auto_start_execution_retry
            ),
            "detail": (
                "monitor="
                f"{cfg.auto_start_monitor}, autotrade={cfg.auto_start_autotrade}, "
                f"retry={cfg.auto_start_execution_retry}"
            ),
        },
        {
            "code": "manual_automation_defaults",
            "label": "Automation defaults",
            "ok": bool(
                not cfg.automation_default_include_monitor
                and cfg.automation_default_include_scan
                and not cfg.automation_default_include_autotrade
                and not cfg.automation_default_include_execution_retry
            ),
            "detail": (
                "monitor="
                f"{cfg.automation_default_include_monitor}, scan={cfg.automation_default_include_scan}, "
                f"autotrade={cfg.automation_default_include_autotrade}, "
                f"retry={cfg.automation_default_include_execution_retry}"
            ),
        },
        {
            "code": "mock_execution_only",
            "label": "Execution mode",
            "ok": bool(
                not cfg.execution_live_enabled
                and str(cfg.execution_provider).strip().lower() in {"mock", "disabled", "none"}
            ),
            "detail": (
                f"provider={cfg.execution_provider}, live_enabled={cfg.execution_live_enabled}"
            ),
        },
        {
            "code": "no_proxy_evasion",
            "label": "Proxy posture",
            "ok": bool(
                not cfg.monitor_use_proxy_pool
                and not str(cfg.network_force_proxy_url or "").strip()
                and not cfg.execution_auto_rotate_proxy_on_ban
            ),
            "detail": (
                "proxy_pool="
                f"{cfg.monitor_use_proxy_pool}, forced_proxy={bool(str(cfg.network_force_proxy_url or '').strip())}, "
                f"rotate_on_ban={cfg.execution_auto_rotate_proxy_on_ban}"
            ),
        },
        {
            "code": "small_scan_budget",
            "label": "Scan budget",
            "ok": int(cfg.automation_default_scan_limit) <= 40,
            "detail": f"automation_default_scan_limit={cfg.automation_default_scan_limit}",
        },
        {
            "code": "portfolio_cap_enabled",
            "label": "Portfolio cap",
            "ok": float(cfg.auto_approve_portfolio_max_deployed_capital) > 0.0,
            "detail": (
                "auto_approve_portfolio_max_deployed_capital="
                f"{cfg.auto_approve_portfolio_max_deployed_capital}"
            ),
        },
        {
            "code": "tight_concentration_caps",
            "label": "Concentration caps",
            "ok": bool(
                float(cfg.auto_approve_max_source_capital_share) <= 0.35
                and float(cfg.auto_approve_max_cluster_batch_share) <= 0.25
                and float(cfg.auto_approve_max_cluster_capital_share) <= 0.25
            ),
            "detail": (
                "source="
                f"{cfg.auto_approve_max_source_capital_share:.2f}, "
                f"cluster_batch={cfg.auto_approve_max_cluster_batch_share:.2f}, "
                f"cluster_capital={cfg.auto_approve_max_cluster_capital_share:.2f}"
            ),
        },
    ]
    failing = [item["code"] for item in items if not bool(item["ok"])]
    return {
        "enabled": bool(cfg.single_account_mode),
        "mode": "single-account-local" if bool(cfg.single_account_mode) else "standard",
        "mode_label": "单账号观察" if bool(cfg.single_account_mode) else "标准模式",
        "strategy_profile": cfg.strategy_profile,
        "aligned": not failing,
        "failing_count": len(failing),
        "failing_codes": failing,
        "items": items,
    }


def resolved_dotenv_path() -> Path:
    if _dotenv_path is not None:
        return _dotenv_path
    return BASE_DIR / ".env"

