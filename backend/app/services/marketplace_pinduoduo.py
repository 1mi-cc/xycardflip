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


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if "goods_search_response" in payload:
            return _as_list(payload["goods_search_response"])
        for key in ("goods_list", "items", "list", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                for subkey in ("goods_list", "items", "list", "results"):
                    subvalue = value.get(subkey)
                    if isinstance(subvalue, list):
                        return [item for item in subvalue if isinstance(item, dict)]
    return []


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _price(value: Any, *, from_cents: bool = False) -> float:
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if from_cents:
        numeric = numeric / 100.0
    return round(numeric, 2)


def _item_type(raw: dict[str, Any]) -> str:
    explicit = _text(raw.get("item_type") or raw.get("category_name") or "generic") or "generic"
    fulfillment_mode = _text(raw.get("fulfillment_mode")).lower()
    if explicit == "virtual_goods" or fulfillment_mode == "virtual":
        return "virtual_goods"
    return explicit


def _shipping_cost(raw: dict[str, Any]) -> float:
    if _item_type(raw) == "virtual_goods":
        return 0.0
    return _price(raw.get("shipping_cost") or 0)


def normalize_pinduoduo_snapshot(payload: Any) -> list[MarketplaceOfferIn]:
    items = _as_list(payload)
    normalized: list[MarketplaceOfferIn] = []
    for raw in items:
        title = _text(raw.get("goods_name") or raw.get("title") or raw.get("name"))
        price = _price(
            raw.get("list_price")
            or raw.get("min_group_price")
            or raw.get("price"),
            from_cents="min_group_price" in raw and raw.get("list_price") is None and raw.get("price") is None,
        )
        if not title or price <= 0:
            continue
        normalized.append(
            MarketplaceOfferIn(
                platform="pinduoduo",
                offer_id=_text(raw.get("goods_id") or raw.get("offer_id") or raw.get("id")),
                seller_id=_text(raw.get("mall_id") or raw.get("seller_id")) or None,
                title=title,
                canonical_key=normalize_marketplace_canonical_key(
                    raw.get("canonical_key") or raw.get("goods_name") or title,
                ),
                item_type=_item_type(raw),
                list_price=price,
                shipping_cost=_shipping_cost(raw),
                fee_rate=_price(raw.get("fee_rate") or 0),
                currency=_text(raw.get("currency") or "CNY") or "CNY",
                listed_at=_datetime(raw.get("listed_at") or raw.get("create_time")),
                status=_text(raw.get("status") or "open") or "open",
                listing_url=_text(raw.get("listing_url") or raw.get("goods_link") or raw.get("url")),
                raw=raw,
            )
        )
    return normalized


class PinduoduoOpenClient:
    def __init__(self) -> None:
        self.api_url = str(settings.pinduoduo_api_url or "").strip()
        self.client_id = str(settings.pinduoduo_client_id or "").strip()
        self.client_secret = str(settings.pinduoduo_client_secret or "").strip()
        self.api_type = str(settings.pinduoduo_type or "pdd.ddk.goods.search").strip()
        self.access_token = str(settings.pinduoduo_access_token or "").strip()
        self.data_type = str(settings.pinduoduo_data_type or "JSON").strip() or "JSON"
        self.params_json = str(settings.pinduoduo_params_json or "").strip()
        self.timeout_sec = float(settings.pinduoduo_timeout_sec or 15.0)
        self.snapshot_provider_url = str(settings.pinduoduo_snapshot_provider_url or "").strip()
        self.cookie_provider = GenericCookieProvider(
            env_key="PINDUODUO_COOKIE",
            initial_cookie=settings.pinduoduo_cookie,
            provider_url=settings.pinduoduo_cookie_provider_url,
            refresh_url=settings.pinduoduo_cookie_refresh_url,
            ttl_sec=settings.pinduoduo_cookie_ttl_sec,
            refresh_min_ttl_sec=settings.pinduoduo_cookie_refresh_min_ttl_sec,
            refresh_on_start=settings.pinduoduo_cookie_refresh_on_start,
        )

    @property
    def official_configured(self) -> bool:
        return bool(self.api_url and self.client_id and self.client_secret and self.api_type and self.params_json)

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
            "type": self.api_type,
            "data_type": self.data_type,
            "params_json_configured": bool(self.params_json),
            "access_token_configured": bool(self.access_token),
            "last_cookie_error": self.cookie_provider.last_error,
        }

    def _base_params(self, *, params_json_override: str = "") -> dict[str, Any]:
        payload_text = str(params_json_override or self.params_json or "").strip()
        if not payload_text:
            raise RuntimeError("PINDUODUO_PARAMS_JSON is missing.")
        try:
            business_params = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid PINDUODUO_PARAMS_JSON: {exc}") from exc
        if not isinstance(business_params, dict):
            raise RuntimeError("PINDUODUO_PARAMS_JSON must decode to an object.")

        params: dict[str, Any] = {
            "client_id": self.client_id,
            "type": self.api_type,
            "timestamp": int(datetime.now().timestamp()),
            "data_type": self.data_type,
            **business_params,
        }
        if self.access_token:
            params["access_token"] = self.access_token
        return params

    def _sign(self, params: dict[str, Any]) -> str:
        pairs = sorted(
            (str(key), "" if value is None else str(value))
            for key, value in params.items()
            if key != "sign"
        )
        raw = self.client_secret + "".join(f"{key}{value}" for key, value in pairs) + self.client_secret
        return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()

    def fetch_snapshot(
        self,
        *,
        params_json_override: str = "",
        snapshot_provider_url_override: str = "",
    ) -> dict[str, Any]:
        if self.active_mode == "cookie":
            return self._fetch_cookie_snapshot(
                params_json_override=params_json_override,
                snapshot_provider_url_override=snapshot_provider_url_override,
            )
        if not self.official_configured:
            raise RuntimeError("Pinduoduo config missing. Provide cookie mode or set PINDUODUO_API_URL, PINDUODUO_CLIENT_ID, PINDUODUO_CLIENT_SECRET, and PINDUODUO_PARAMS_JSON.")
        params = self._base_params(params_json_override=params_json_override)
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
            raise RuntimeError(str(error.get("sub_msg") or error.get("error_msg") or "Pinduoduo request failed"))
        return payload

    def _fetch_cookie_snapshot(
        self,
        *,
        params_json_override: str = "",
        snapshot_provider_url_override: str = "",
    ) -> dict[str, Any]:
        snapshot_url = str(snapshot_provider_url_override or self.snapshot_provider_url or "").strip()
        if not snapshot_url:
            raise RuntimeError(
                "Pinduoduo cookie mode needs PINDUODUO_SNAPSHOT_PROVIDER_URL or use ingest-snapshot."
            )
        cookie = self.cookie_provider.get_cookie(force_refresh=False)
        if not cookie:
            raise RuntimeError("Pinduoduo cookie mode requires PINDUODUO_COOKIE or PINDUODUO_COOKIE_PROVIDER_URL.")
        params = {}
        payload_text = str(params_json_override or self.params_json or "").strip()
        if payload_text:
            try:
                parsed = json.loads(payload_text)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid PINDUODUO_PARAMS_JSON: {exc}") from exc
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
            raise RuntimeError(f"Pinduoduo cookie snapshot response is not valid JSON: {exc}") from exc

    def sync_once(
        self,
        *,
        params_json_override: str = "",
        snapshot_provider_url_override: str = "",
    ) -> dict[str, Any]:
        payload = self.fetch_snapshot(
            params_json_override=params_json_override,
            snapshot_provider_url_override=snapshot_provider_url_override,
        )
        rows = normalize_pinduoduo_snapshot(payload)
        return {
            "count": len(rows),
            "rows": rows,
            "raw": payload,
        }


pinduoduo_open_client = PinduoduoOpenClient()
