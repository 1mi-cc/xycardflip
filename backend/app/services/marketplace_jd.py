from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..schemas import MarketplaceOfferIn
from .cookie_provider import GenericCookieProvider
from .marketplace_normalizer import normalize_marketplace_canonical_key
from .proxy_resolver import request_get
from .proxy_resolver import request_post
from .proxy_resolver import resolve_proxy_for_url


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _datetime(value: Any) -> datetime:
    text = _text(value)
    if not text:
        return datetime.now(timezone.utc)
    normalized = text.replace("Z", "+00:00")
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for root_key in (
            "jd_union_open_goods_query_responce",
            "jd_union_open_goods_query_response",
            "jd_union_open_selling_goods_query_responce",
            "jd_union_open_selling_goods_query_response",
        ):
            if root_key in payload and isinstance(payload[root_key], dict):
                payload = payload[root_key]
                break
        for key in ("queryResult", "result", "data", "response"):
            value = payload.get(key) if isinstance(payload, dict) else None
            if isinstance(value, dict):
                for subkey in ("goodsList", "items", "list", "data"):
                    subvalue = value.get(subkey)
                    if isinstance(subvalue, list):
                        return [item for item in subvalue if isinstance(item, dict)]
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        for key in ("goodsList", "items", "list", "data"):
            value = payload.get(key) if isinstance(payload, dict) else None
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def normalize_jd_snapshot(payload: Any) -> list[MarketplaceOfferIn]:
    items = _as_list(payload)
    normalized: list[MarketplaceOfferIn] = []
    for raw in items:
        title = _text(raw.get("skuName") or raw.get("productName") or raw.get("title") or raw.get("name"))
        price = _float(raw.get("price") or raw.get("lowestPrice") or raw.get("unitPrice"))
        if not title or price <= 0:
            continue
        normalized.append(
            MarketplaceOfferIn(
                platform="jd",
                offer_id=_text(raw.get("skuId") or raw.get("wareId") or raw.get("offer_id") or raw.get("id")),
                seller_id=_text(raw.get("owner") or raw.get("shopId") or raw.get("seller_id")) or None,
                title=title,
                canonical_key=normalize_marketplace_canonical_key(
                    raw.get("canonical_key") or raw.get("skuName") or title,
                ),
                item_type=_text(raw.get("item_type") or raw.get("categoryName") or "generic") or "generic",
                list_price=price,
                shipping_cost=_float(raw.get("shipping_cost") or 0.0),
                fee_rate=_float(raw.get("commisionRatioWl") or raw.get("fee_rate") or 0.0),
                currency=_text(raw.get("currency") or "CNY") or "CNY",
                listed_at=_datetime(raw.get("listed_at") or raw.get("create_time")),
                status=_text(raw.get("status") or "open") or "open",
                listing_url=_text(raw.get("materialUrl") or raw.get("skuUrl") or raw.get("url")),
                raw=raw,
            )
        )
    return normalized


class JDOpenClient:
    def __init__(self) -> None:
        self.api_url = str(settings.jd_api_url or "").strip()
        self.app_key = str(settings.jd_app_key or "").strip()
        self.app_secret = str(settings.jd_app_secret or "").strip()
        self.method = str(settings.jd_method or "jd.union.open.goods.query").strip()
        self.access_token = str(settings.jd_access_token or "").strip()
        self.sign_method = str(settings.jd_sign_method or "md5").strip().lower()
        self.version = str(settings.jd_version or "1.0").strip() or "1.0"
        self.format = str(settings.jd_format or "json").strip() or "json"
        self.param_json = str(settings.jd_param_json or "").strip()
        self.timeout_sec = float(settings.jd_timeout_sec or 15.0)
        self.snapshot_provider_url = str(settings.jd_snapshot_provider_url or "").strip()
        self.cookie_provider = GenericCookieProvider(
            env_key="JD_COOKIE",
            initial_cookie=settings.jd_cookie,
            provider_url=settings.jd_cookie_provider_url,
            refresh_url=settings.jd_cookie_refresh_url,
            ttl_sec=settings.jd_cookie_ttl_sec,
            refresh_min_ttl_sec=settings.jd_cookie_refresh_min_ttl_sec,
            refresh_on_start=settings.jd_cookie_refresh_on_start,
        )

    @property
    def official_configured(self) -> bool:
        return bool(self.api_url and self.app_key and self.app_secret and self.method and self.param_json)

    @property
    def cookie_configured(self) -> bool:
        return bool(self.cookie_provider.has_cookie())

    @property
    def provider_url_configured(self) -> bool:
        return bool(self.cookie_provider.has_provider_url())

    @property
    def active_mode(self) -> str:
        if self.cookie_configured or self.provider_url_configured:
            return "cookie"
        if self.official_configured:
            return "official"
        return "unavailable"

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.active_mode != "unavailable",
            "official_configured": self.official_configured,
            "cookie_configured": self.cookie_configured,
            "provider_url_configured": self.provider_url_configured,
            "snapshot_provider_url_configured": bool(self.snapshot_provider_url),
            "snapshot_provider_url": self.snapshot_provider_url,
            "active_mode": self.active_mode,
            "risk_level": "high-risk-unstable" if self.active_mode == "cookie" else "official",
            "api_url": self.api_url,
            "method": self.method,
            "sign_method": self.sign_method,
            "version": self.version,
            "format": self.format,
            "param_json_configured": bool(self.param_json),
            "access_token_configured": bool(self.access_token),
            "last_cookie_error": self.cookie_provider.last_error,
        }

    def _base_params(self, *, param_json_override: str = "") -> dict[str, str]:
        payload_text = _text(param_json_override or self.param_json)
        if not payload_text:
            raise RuntimeError("JD_PARAM_JSON is missing.")
        try:
            body = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JD_PARAM_JSON: {exc}") from exc
        if not isinstance(body, dict):
            raise RuntimeError("JD_PARAM_JSON must decode to an object.")

        params = {
            "method": self.method,
            "app_key": self.app_key,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "v": self.version,
            "format": self.format,
            "sign_method": self.sign_method,
            "360buy_param_json": json.dumps(body, ensure_ascii=False, separators=(",", ":")),
        }
        if self.access_token:
            params["access_token"] = self.access_token
        return params

    def _sign(self, params: dict[str, str]) -> str:
        pairs = sorted((str(key), str(value)) for key, value in params.items() if key != "sign" and value is not None)
        raw = self.app_secret + "".join(f"{key}{value}" for key, value in pairs) + self.app_secret
        return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()

    def fetch_snapshot(
        self,
        *,
        param_json_override: str = "",
        snapshot_provider_url_override: str = "",
    ) -> dict[str, Any]:
        if self.active_mode == "cookie":
            return self._fetch_cookie_snapshot(
                param_json_override=param_json_override,
                snapshot_provider_url_override=snapshot_provider_url_override,
            )
        if not self.official_configured:
            raise RuntimeError("JD config missing. Provide cookie mode or set JD_API_URL, JD_APP_KEY, JD_APP_SECRET, and JD_PARAM_JSON.")
        params = self._base_params(param_json_override=param_json_override)
        params["sign"] = self._sign(params)
        response = request_post(
            self.api_url,
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
            timeout=self.timeout_sec,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error_response"):
            error = payload["error_response"] or {}
            raise RuntimeError(_text(error.get("zh_desc") or error.get("message") or "JD request failed"))
        return payload

    def _fetch_cookie_snapshot(
        self,
        *,
        param_json_override: str = "",
        snapshot_provider_url_override: str = "",
    ) -> dict[str, Any]:
        snapshot_url = str(snapshot_provider_url_override or self.snapshot_provider_url or "").strip()
        if not snapshot_url:
            raise RuntimeError(
                "JD cookie mode needs JD_SNAPSHOT_PROVIDER_URL or use ingest-snapshot."
            )
        cookie = self.cookie_provider.get_cookie(force_refresh=False)
        if not cookie:
            raise RuntimeError("JD cookie mode requires JD_COOKIE or JD_COOKIE_PROVIDER_URL.")
        params = {}
        payload_text = _text(param_json_override or self.param_json)
        if payload_text:
            try:
                parsed = json.loads(payload_text)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid JD_PARAM_JSON: {exc}") from exc
            if isinstance(parsed, dict):
                params = parsed
        response = request_get(
            snapshot_url,
            params=params,
            headers={
                "Cookie": cookie,
                "Accept": "application/json,text/plain,*/*",
                "User-Agent": settings.xianyu_desktop_user_agent,
            },
            timeout=self.timeout_sec,
            proxies=resolve_proxy_for_url(snapshot_url),
        )
        response.raise_for_status()
        try:
            return response.json()
        except Exception as exc:
            raise RuntimeError(f"JD cookie snapshot response is not valid JSON: {exc}") from exc

    def sync_once(
        self,
        *,
        param_json_override: str = "",
        snapshot_provider_url_override: str = "",
    ) -> dict[str, Any]:
        payload = self.fetch_snapshot(
            param_json_override=param_json_override,
            snapshot_provider_url_override=snapshot_provider_url_override,
        )
        rows = normalize_jd_snapshot(payload)
        return {
            "count": len(rows),
            "rows": rows,
            "raw": payload,
        }


jd_open_client = JDOpenClient()
