from __future__ import annotations

import json
import random
import re
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

    def fetch(self, page: int = 1, proxies: dict[str, str] | None = None) -> list[dict[str, Any]]:
        params = {
            "keywords": self.keyword,
            "page": page,
            "sort": "time",
            "pageSize": 20,
        }
        headers = {
            # Mobile UA lowers risk of full page JS challenges
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": f"{self.search_url}?{urlencode({'keywords': self.keyword})}",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

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
        )
        try:
            price = float(str(price_raw).replace("¥", "").strip())
        except Exception:
            price = 0.0

        title = (
            item.get("title")
            or item.get("itemTitle")
            or item.get("raw_title")
            or item.get("rawTitle")
            or ""
        )
        desc = item.get("description") or item.get("desc") or ""
        seller = (
            item.get("sellerId")
            or item.get("userId")
            or item.get("user_id")
            or item.get("uid")
        )

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
