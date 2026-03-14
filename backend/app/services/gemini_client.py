from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Iterable

import httpx

from ..config import settings
from .proxy_resolver import proxy_url_from_mapping
from .proxy_resolver import ProxyRequiredError
from .proxy_resolver import resolve_proxy_for_url

# Keys whose quota is exhausted (HTTP 429) are quarantined for this many seconds
# before being retried.  A value of 0 disables quarantine.
_RATE_LIMIT_BACKOFF_BASE: float = 4.0
_RATE_LIMIT_BACKOFF_MAX: float = 60.0


class GeminiClient:
    def __init__(self) -> None:
        self.api_keys = self._parse_keys(settings.gemini_api_key)
        self.model = settings.gemini_model
        self._key_index = 0
        # Maps key → monotonic timestamp after which it may be used again.
        self._rate_limited_until: dict[str, float] = {}
        # Maps key → consecutive 429 count (for exponential backoff).
        self._rate_limit_strikes: dict[str, int] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.api_keys)

    @staticmethod
    def _parse_keys(raw: str | None) -> list[str]:
        if not raw:
            return []
        text = str(raw).strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
                if isinstance(parsed, str):
                    return [parsed.strip()] if parsed.strip() else []
            except json.JSONDecodeError:
                pass
        parts: Iterable[str]
        if "," in text:
            parts = text.split(",")
        else:
            parts = text.splitlines()
        return [item.strip() for item in parts if item.strip()]

    def _next_key(self) -> str:
        """Return the next available API key, skipping rate-limited ones."""
        if not self.api_keys:
            return ""
        now = time.monotonic()
        for _ in range(len(self.api_keys)):
            key = self.api_keys[self._key_index % len(self.api_keys)]
            self._key_index = (self._key_index + 1) % len(self.api_keys)
            if now >= self._rate_limited_until.get(key, 0.0):
                return key
        # All keys are rate-limited; return the one whose cooldown expires soonest.
        best = min(self.api_keys, key=lambda k: self._rate_limited_until.get(k, 0.0))
        return best

    def _mark_rate_limited(self, key: str) -> float:
        """Quarantine *key* with exponential backoff; return sleep seconds needed."""
        strikes = self._rate_limit_strikes.get(key, 0) + 1
        self._rate_limit_strikes[key] = strikes
        backoff = min(_RATE_LIMIT_BACKOFF_MAX, _RATE_LIMIT_BACKOFF_BASE * (2 ** (strikes - 1)))
        self._rate_limited_until[key] = time.monotonic() + backoff
        return backoff

    def _clear_rate_limit(self, key: str) -> None:
        """Reset quarantine state for a key after a successful call."""
        self._rate_limited_until.pop(key, None)
        self._rate_limit_strikes.pop(key, None)

    async def extract_card_features(self, title: str, description: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        prompt = (
            "Extract structured fields for a collectible game card listing.\n"
            "Return strict JSON with fields: card_name, rarity, edition, card_condition, extras, confidence.\n"
            "confidence must be 0-1 float, extras must be an object.\n"
            "If unknown, use string 'unknown'."
        )
        content = f"title: {title}\ndescription: {description}"

        base_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}, {"text": content}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        timeout = httpx.Timeout(20.0)
        try:
            proxy_url = proxy_url_from_mapping(resolve_proxy_for_url(base_url))
        except ProxyRequiredError:
            # Strict proxy mode configured but no proxy available.
            # Skip Gemini call and let caller fallback to rule-based extraction.
            return None
        async with httpx.AsyncClient(
            timeout=timeout,
            trust_env=not settings.network_ignore_env_proxy,
            proxy=proxy_url,
        ) as client:
            last_error: Exception | None = None
            attempts = len(self.api_keys)
            for attempt in range(attempts):
                key = self._next_key()
                if not key:
                    break

                # Honour any active rate-limit cooldown before sending the request.
                wait_sec = self._rate_limited_until.get(key, 0.0) - time.monotonic()
                if wait_sec > 0:
                    # Only wait if this is not the first attempt with a fresh key.
                    if attempt > 0:
                        await asyncio.sleep(min(wait_sec, _RATE_LIMIT_BACKOFF_MAX))
                    else:
                        # All keys may be rate-limited; at least yield the event loop.
                        await asyncio.sleep(0)

                url = f"{base_url}?key={key}"
                try:
                    response = await client.post(url, json=payload)
                    if response.status_code == 429:
                        backoff = self._mark_rate_limited(key)
                        last_error = httpx.HTTPStatusError(
                            f"429 rate limited (backoff {backoff:.1f}s)",
                            request=response.request,
                            response=response,
                        )
                        continue
                    response.raise_for_status()
                    data = response.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text)
                    self._clear_rate_limit(key)
                    return parsed if isinstance(parsed, dict) else None
                except (
                    httpx.HTTPStatusError,
                    httpx.RequestError,
                    KeyError,
                    IndexError,
                    TypeError,
                    json.JSONDecodeError,
                ) as exc:
                    last_error = exc
                    continue
            _ = last_error
            return None

