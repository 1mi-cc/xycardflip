from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..schemas import MarketplaceOfferIn
from .marketplace_normalizer import normalize_marketplace_canonical_key
from .proxy_resolver import request_post


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                rows.append(item)
            elif isinstance(item, str):
                try:
                    parsed = json.loads(item)
                except Exception:
                    continue
                if isinstance(parsed, dict):
                    rows.append(parsed)
        return rows
    if isinstance(payload, dict):
        if "alibaba_tuike_offer_get_response" in payload:
            return _as_list(payload["alibaba_tuike_offer_get_response"])
        if "result" in payload and isinstance(payload["result"], dict):
            result = payload["result"]
            for key in ("data_list", "items", "list", "results"):
                if key in result:
                    return _as_list(result[key])
        for key in ("items", "list", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                for subkey in ("items", "list", "results"):
                    subvalue = value.get(subkey)
                    if isinstance(subvalue, list):
                        return [item for item in subvalue if isinstance(item, dict)]
    return []


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


def _canonical_key(raw: dict[str, Any]) -> str:
    return normalize_marketplace_canonical_key(
        raw.get("canonical_key")
        or raw.get("normalized_key")
        or raw.get("normalized_title")
        or raw.get("title")
        or raw.get("item_title")
        or raw.get("name")
    )


def _stable_offer_id(raw: dict[str, Any]) -> str:
    direct = _text(raw.get("offer_id") or raw.get("num_iid") or raw.get("item_id") or raw.get("id"))
    if direct:
        return direct
    digest_source = "|".join(
        [
            _text(raw.get("title") or raw.get("item_title") or raw.get("name")),
            _text(raw.get("seller_id") or raw.get("nick") or raw.get("shop_id")),
            str(_float(raw.get("price") or raw.get("zk_final_price") or raw.get("reserve_price"))),
        ]
    )
    return hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:24]


def normalize_taobao_snapshot(payload: Any) -> list[MarketplaceOfferIn]:
    items = _as_list(payload)
    normalized: list[MarketplaceOfferIn] = []
    for raw in items:
        title = _text(raw.get("title") or raw.get("item_title") or raw.get("name"))
        price = _float(raw.get("price") or raw.get("zk_final_price") or raw.get("reserve_price"))
        if not title or price <= 0:
            continue
        normalized.append(
            MarketplaceOfferIn(
                platform="taobao",
                offer_id=_stable_offer_id(raw),
                seller_id=_text(raw.get("seller_id") or raw.get("nick") or raw.get("shop_id")) or None,
                title=title,
                canonical_key=_canonical_key(raw) or normalize_marketplace_canonical_key(title=title),
                item_type=_text(raw.get("item_type") or raw.get("category") or "generic") or "generic",
                list_price=price,
                shipping_cost=_float(raw.get("shipping_cost") or raw.get("post_fee") or 0.0),
                fee_rate=_float(raw.get("fee_rate") or 0.0),
                currency=_text(raw.get("currency") or "CNY") or "CNY",
                listed_at=_datetime(raw.get("listed_at") or raw.get("gmt_create") or raw.get("create_time")),
                status=_text(raw.get("status") or "open") or "open",
                listing_url=_text(raw.get("listing_url") or raw.get("item_url") or raw.get("url")),
                raw=raw,
            )
        )
    return normalized


class TaobaoTopClient:
    def __init__(self) -> None:
        self.gateway_url = str(settings.taobao_top_gateway_url or "").strip()
        self.app_key = str(settings.taobao_top_app_key or "").strip()
        self.app_secret = str(settings.taobao_top_app_secret or "").strip()
        self.method = str(settings.taobao_top_method or "alibaba.tuike.offer.get").strip()
        self.sign_method = str(settings.taobao_top_sign_method or "hmac").strip().lower()
        self.isv_code = str(settings.taobao_top_isv_code or "").strip()
        self.query_string = str(settings.taobao_top_query_string or "").strip()
        self.session = str(settings.taobao_top_session or "").strip()
        self.timeout_sec = float(settings.taobao_top_timeout_sec or 15.0)

    @property
    def configured(self) -> bool:
        return bool(self.gateway_url and self.app_key and self.app_secret and self.method and self.query_string)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "gateway_url": self.gateway_url,
            "method": self.method,
            "sign_method": self.sign_method,
            "query_string_configured": bool(self.query_string),
            "session_configured": bool(self.session),
            "isv_code_configured": bool(self.isv_code),
        }

    def _sign(self, params: dict[str, str]) -> str:
        pairs = sorted(
            (
                str(key),
                str(value),
            )
            for key, value in params.items()
            if key != "sign" and value is not None
        )
        payload = "".join(f"{key}{value}" for key, value in pairs).encode("utf-8")
        if self.sign_method == "md5":
            digest = hashlib.md5(self.app_secret.encode("utf-8") + payload + self.app_secret.encode("utf-8")).hexdigest()
            return digest.upper()
        if self.sign_method in {"hmac", "hmac-md5"}:
            digest = hmac.new(self.app_secret.encode("utf-8"), payload, hashlib.md5).hexdigest()
            return digest.upper()
        if self.sign_method == "hmac-sha256":
            digest = hmac.new(self.app_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
            return digest.upper()
        raise RuntimeError(f"Unsupported TAOBAO_TOP_SIGN_METHOD: {self.sign_method}")

    def build_request_params(self, *, query_string_override: str = "") -> dict[str, str]:
        query_string = str(query_string_override or self.query_string or "").strip()
        if not query_string:
            raise RuntimeError("TAOBAO_TOP_QUERY_STRING is missing.")
        params = {
            "method": self.method,
            "app_key": self.app_key,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "v": "2.0",
            "sign_method": self.sign_method,
            "format": "json",
            "simplify": "true",
            "query_string": query_string,
        }
        if self.isv_code:
            params["isv_code"] = self.isv_code
        if self.session:
            params["session"] = self.session
        params["sign"] = self._sign(params)
        return params

    def fetch_snapshot(self, *, query_string_override: str = "") -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("Taobao TOP config missing. Set TAOBAO_TOP_GATEWAY_URL, TAOBAO_TOP_APP_KEY, TAOBAO_TOP_APP_SECRET, TAOBAO_TOP_QUERY_STRING.")
        params = self.build_request_params(query_string_override=query_string_override)
        response = request_post(
            self.gateway_url,
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
            timeout=self.timeout_sec,
        )
        response.raise_for_status()
        payload = response.json()
        if "error_response" in payload:
            error = payload.get("error_response") or {}
            raise RuntimeError(str(error.get("sub_msg") or error.get("msg") or "Taobao TOP request failed"))
        return payload

    def sync_once(self, *, query_string_override: str = "") -> dict[str, Any]:
        payload = self.fetch_snapshot(query_string_override=query_string_override)
        rows = normalize_taobao_snapshot(payload)
        return {
            "count": len(rows),
            "rows": rows,
            "raw": payload,
        }


taobao_top_client = TaobaoTopClient()
