from __future__ import annotations

import hashlib
import json
import random
import re
import time
from typing import Any
from urllib.parse import urlencode

import requests

from ..config import settings


class XianyuClient:
    """
    Lightweight Xianyu search scraper with simple anti-crawl disguises.
    It relies on a mobile User-Agent and optional user-supplied cookie.
    """

    def __init__(self) -> None:
        self.search_url = settings.xianyu_search_url
        self.keyword = settings.monitor_keyword
        self.cookie = settings.xianyu_cookie.strip()

    def fetch(
        self,
        page: int = 1,
        proxies: dict[str, str] | None = None,
        cookie_override: str | None = None,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        keyword_value = (keyword or "").strip() or self.keyword
        params = {
            "keywords": keyword_value,
            "page": page,
            "sort": "time",
            "pageSize": 20,
        }
        cookie_value = (cookie_override or "").strip() or self.cookie
        headers = {
            # Mobile UA lowers risk of full page JS challenges
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": f"{self.search_url}?{urlencode({'keywords': keyword_value})}",
        }
        if cookie_value:
            headers["Cookie"] = cookie_value

        mtop_items = self._fetch_mtop_search(
            page=page,
            proxies=proxies,
            cookie_value=cookie_value,
            keyword=keyword_value,
        )
        if mtop_items is not None:
            return mtop_items

        resp = requests.get(
            self.search_url, params=params, headers=headers, timeout=12, proxies=proxies
        )
        # 403 will be handled by caller; surface status for monitoring
        if resp.status_code != 200:
            raise XianyuHttpError(resp.status_code, resp.text[:200])

        text = resp.text
        data = self._extract_json(text)
        items = self._parse_items(data) if data else self._regex_parse_items(text)
        return items

    def _fetch_mtop_search(
        self,
        page: int,
        proxies: dict[str, str] | None,
        cookie_value: str,
        keyword: str,
    ) -> list[dict[str, Any]] | None:
        if not cookie_value:
            return None

        cookies = self._parse_cookie(cookie_value)
        token_raw = cookies.get("_m_h5_tk", "")
        if "_" not in token_raw:
            return None

        token = token_raw.split("_", 1)[0]
        app_key = "34839810"
        t = str(int(time.time() * 1000))
        payload = {
            "pageNumber": page,
            "keyword": keyword,
            "fromFilter": "",
            "rowsPerPage": 30,
            "sortValue": "desc",
            "sortField": "publishTime",
            "customDistance": "",
            "gps": "",
            "propValueStr": {},
            "customGps": "",
            "searchReqFromPage": "pcSearch",
            "extraFilterValue": "",
            "userPositionJson": "",
        }
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        sign_raw = f"{token}&{t}&{app_key}&{data}"
        sign = hashlib.md5(sign_raw.encode("utf-8")).hexdigest()

        mtop_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/"
        params = {
            "jsv": "2.7.4",
            "appKey": app_key,
            "t": t,
            "sign": sign,
            "api": "mtop.taobao.idlemtopsearch.pc.search",
            "v": "1.0",
            "type": "originaljson",
            "dataType": "json",
            "timeout": "10000",
            "data": data,
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Origin": "https://www.goofish.com",
            "Referer": "https://www.goofish.com/",
        }
        if cookie_value:
            headers["Cookie"] = cookie_value

        resp = requests.get(mtop_url, params=params, headers=headers, timeout=12, proxies=proxies)
        if resp.status_code != 200:
            raise XianyuHttpError(resp.status_code, resp.text[:200])

        payload = resp.json()
        ret = payload.get("ret") or []
        if ret and not any("SUCCESS" in str(r) for r in ret):
            raise XianyuHttpError(resp.status_code, ";".join([str(r) for r in ret])[:200])

        data = payload.get("data") or {}
        items_raw = self._extract_mtop_items(data)
        items: list[dict[str, Any]] = []
        for raw in items_raw:
            if not isinstance(raw, dict):
                continue
            node = raw
            if isinstance(raw.get("data"), dict):
                node = raw["data"]
            candidate = node
            if isinstance(node.get("item"), dict):
                item_node = node["item"]
                if isinstance(item_node.get("main"), dict):
                    ex_content = item_node.get("main", {}).get("exContent")
                    if isinstance(ex_content, dict):
                        candidate = ex_content
                    else:
                        candidate = item_node
                else:
                    candidate = item_node
                if isinstance(node.get("seller"), dict) and isinstance(candidate, dict):
                    candidate = dict(candidate)
                    candidate.setdefault("seller", node["seller"])
            items.append(self._normalize_item(candidate))
        return items

    def _extract_mtop_items(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(data, dict):
            return []

        def _maybe_json(value: Any) -> Any:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return value
            return value

        for key in ("resultList", "items", "itemList", "list", "result"):
            value = _maybe_json(data.get(key))
            if isinstance(value, dict):
                for subkey in ("resultList", "items", "itemList", "list"):
                    sub = _maybe_json(value.get(subkey))
                    if isinstance(sub, list):
                        return sub
            if isinstance(value, list):
                return value

        for value in data.values():
            value = _maybe_json(value)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value
            if isinstance(value, dict):
                for sub in value.values():
                    sub = _maybe_json(sub)
                    if isinstance(sub, list) and sub and isinstance(sub[0], dict):
                        return sub
        return []

    def _parse_cookie(self, cookie: str) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for chunk in cookie.split(";"):
            chunk = chunk.strip()
            if not chunk or "=" not in chunk:
                continue
            key, value = chunk.split("=", 1)
            pairs[key.strip()] = value.strip()
        return pairs

    def _coerce_price(self, value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item.get("text") or ""))
                    continue
                if isinstance(item, (str, int, float)):
                    parts.append(str(item))
            value = "".join(parts)
        elif isinstance(value, dict):
            if "text" in value:
                value = value.get("text")
            elif "price" in value:
                value = value.get("price")
                if isinstance(value, list):
                    parts: list[str] = []
                    for item in value:
                        if isinstance(item, dict) and "text" in item:
                            parts.append(str(item.get("text") or ""))
                            continue
                        if isinstance(item, (str, int, float)):
                            parts.append(str(item))
                    value = "".join(parts)
        raw = str(value).strip()
        if not raw:
            return 0.0
        multiplier = 1.0
        if raw.endswith("\u4e07"):
            multiplier = 10000.0
            raw = raw[:-1]
        raw = raw.replace("\u697c", "").replace("\u00a5", "").replace(",", "").strip()
        try:
            return float(raw) * multiplier
        except Exception:
            return 0.0
    def _extract_json(self, html: str) -> dict[str, Any] | None:
        # Multiple possible bootstrap variables
        patterns = [
            r"__INIT_DATA__\s*=\s*(\{.*?\})\s*;</script>",
            r"__initialState__\s*=\s*(\{.*?\})\s*;</script>",
            r"window\.__initData__\s*=\s*(\{.*?\})\s*;</script>",
        ]
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if not m:
                continue
            raw = m.group(1)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # Some pages have trailing comments; attempt a lenient fix
                try:
                    cleaned = raw.split("};", 1)[0] + "}"
                    return json.loads(cleaned)
                except Exception:
                    continue
        return None

    def _parse_items(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Attempt to traverse common Xianyu search JSON shapes.
        """
        # Shape 1: data["result"]["data"]["items"]
        paths = [
            ("result", "data", "items"),
            ("pageInfo", "items"),
            ("data", "items"),
        ]
        for path in paths:
            node: Any = data
            for key in path:
                node = node.get(key) if isinstance(node, dict) else None
                if node is None:
                    break
            if isinstance(node, list) and node:
                return [self._normalize_item(item) for item in node if isinstance(item, dict)]

        return []

    def _regex_parse_items(self, html: str) -> list[dict[str, Any]]:
        """
        Fallback: crude regex extraction when JSON bootstrap is absent.
        """
        items: list[dict[str, Any]] = []
        pattern = re.compile(
            r'"itemId"\s*:\s*"(?P<id>[^"]+)"[^}]*?"price"\s*:\s*"?(?P<price>[0-9.]+)"?[^}]*?'
            r'"title"\s*:\s*"(?P<title>[^"]+)"',
            re.S,
        )
        for match in pattern.finditer(html):
            try:
                items.append(
                    {
                        "id": match.group("id"),
                        "price": float(match.group("price")),
                        "title": match.group("title"),
                        "description": "",
                        "seller_id": None,
                    }
                )
            except Exception:
                continue
        return items

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        # Common key variants
        item_id = item.get("itemId") or item.get("id") or item.get("item_id") or item.get("productId")
        price_raw = (
            item.get("price")
            or item.get("priceText")
            or item.get("price_info")
            or item.get("priceContent")
            or item.get("priceInfo")
        )
        if isinstance(price_raw, dict):
            price_raw = price_raw.get("price") or price_raw.get("text") or price_raw.get("priceText")
        price = self._coerce_price(price_raw)

        title = (
            item.get("title")
            or item.get("richTitle")
            or item.get("itemTitle")
            or item.get("raw_title")
            or item.get("rawTitle")
            or ""
        )
        if "<" in str(title):
            title = re.sub(r"<[^>]+>", "", str(title))
        desc = item.get("description") or item.get("desc") or ""
        seller = (
            item.get("sellerId")
            or item.get("userId")
            or item.get("user_id")
            or item.get("uid")
        )
        if not seller:
            for key in ("seller", "user", "sellerInfo", "userInfo"):
                node = item.get(key)
                if isinstance(node, dict):
                    seller = (
                        node.get("userId")
                        or node.get("sellerId")
                        or node.get("id")
                        or node.get("uid")
                    )
                    if seller:
                        break

        return {
            "id": str(item_id or "").strip(),
            "price": price,
            "title": str(title or "").strip(),
            "description": str(desc or "").strip(),
            "seller_id": str(seller or "").strip() or None,
            "raw": item,
        }


class XianyuHttpError(RuntimeError):
    def __init__(self, status: int, body_excerpt: str = "") -> None:
        super().__init__(f"xianyu status {status}: {body_excerpt}")
        self.status = status
        self.body_excerpt = body_excerpt


