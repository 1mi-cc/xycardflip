from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

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
    "game:feature:view",
    "cardflip:view",
    "task:view",
    "task:batch",
    "message:test",
    "token:view",
    "profile:view",
)

DEFAULT_UI_ROLE_PERMISSIONS_ADMIN: tuple[str, ...] = DEFAULT_UI_MENU_PERMISSIONS
DEFAULT_UI_ROLE_PERMISSIONS_OPS: tuple[str, ...] = (
    "dashboard:view",
    "cardflip:view",
    "task:view",
    "task:batch",
    "message:test",
    "token:view",
)
DEFAULT_UI_ROLE_PERMISSIONS_VIEWER: tuple[str, ...] = (
    "dashboard:view",
    "cardflip:view",
    "token:view",
    "profile:view",
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
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
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
    ui_auth_password: str = os.getenv("UI_AUTH_PASSWORD", "admin123456")
    ui_auth_nickname: str = os.getenv("UI_AUTH_NICKNAME", "本地操作员")
    ui_auth_default_role: str = os.getenv("UI_AUTH_DEFAULT_ROLE", "admin").strip().lower() or "admin"
    ui_auth_session_hours: int = _get_int("UI_AUTH_SESSION_HOURS", 72)
    ui_auth_allow_registration: bool = _get_bool("UI_AUTH_ALLOW_REGISTRATION", True)
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

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
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
    auto_start_autotrade: bool = _get_bool("AUTO_START_AUTOTRADE", False)
    auto_start_execution_retry: bool = _get_bool("AUTO_START_EXECUTION_RETRY", False)

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

