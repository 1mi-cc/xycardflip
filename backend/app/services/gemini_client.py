from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
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
        self.api_keys: list[str] = []
        self.model = settings.gemini_model
        self.key_source_path = settings.gemini_key_source_path
        self.resolved_key_source_path = ""
        self.source_type = "none"
        self.external_key_count = 0
        self.local_key_count = 0
        self.external_source_configured = False
        self.external_source_found = False
        self._key_index = 0
        # Maps key → monotonic timestamp after which it may be used again.
        self._rate_limited_until: dict[str, float] = {}
        # Maps key → consecutive 429 count (for exponential backoff).
        self._rate_limit_strikes: dict[str, int] = {}
        self._refresh_keys_from_settings()

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

    @staticmethod
    def _dedupe_keys(keys: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in keys:
            key = str(raw or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            normalized.append(key)
        return normalized

    @staticmethod
    def _resolve_external_source_path(raw_path: str | None) -> Path | None:
        text = str(raw_path or "").strip()
        if not text:
            return None
        path = Path(text).expanduser()
        if path.is_dir():
            env_path = path / ".env"
            return env_path if env_path.exists() else None
        if path.exists():
            return path
        return None

    def _load_keys_from_external_source(self, raw_path: str | None) -> list[str]:
        path = self._resolve_external_source_path(raw_path)
        if path is None:
            return []
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return []

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for prefix in ("API_KEYS=", "GEMINI_API_KEY=", "GEMINI_KEYS="):
                if not stripped.startswith(prefix):
                    continue
                value = stripped[len(prefix):].strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                return self._parse_keys(value)

        stripped_content = content.strip()
        if stripped_content.startswith("[") and stripped_content.endswith("]"):
            return self._parse_keys(stripped_content)
        return []

    def _refresh_keys_from_settings(self) -> None:
        self.model = settings.gemini_model
        self.key_source_path = settings.gemini_key_source_path
        resolved_source = self._resolve_external_source_path(self.key_source_path)
        external_keys = self._dedupe_keys(self._load_keys_from_external_source(self.key_source_path))
        local_keys = self._dedupe_keys(self._parse_keys(settings.gemini_api_key))
        self.api_keys = self._dedupe_keys([*external_keys, *local_keys])
        self.resolved_key_source_path = str(resolved_source) if resolved_source else ""
        self.external_source_configured = bool(str(self.key_source_path or "").strip())
        self.external_source_found = resolved_source is not None
        self.external_key_count = len(external_keys)
        self.local_key_count = len(local_keys)
        if external_keys and local_keys:
            self.source_type = "mixed"
        elif external_keys:
            self.source_type = "external_pool"
        elif local_keys:
            self.source_type = "local_env"
        else:
            self.source_type = "none"

    def get_runtime_status(self) -> dict[str, Any]:
        self._refresh_keys_from_settings()
        now = time.monotonic()
        rate_limited_key_count = sum(
            1 for available_at in self._rate_limited_until.values() if available_at > now
        )
        return {
            "enabled": self.enabled,
            "model": self.model,
            "key_count": len(self.api_keys),
            "local_key_count": self.local_key_count,
            "external_key_count": self.external_key_count,
            "source_type": self.source_type,
            "key_source_path": self.key_source_path,
            "resolved_key_source_path": self.resolved_key_source_path,
            "external_source_configured": self.external_source_configured,
            "external_source_found": self.external_source_found,
            "rate_limited_key_count": rate_limited_key_count,
        }

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
        self._refresh_keys_from_settings()
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

    async def test_connection(self) -> dict[str, Any]:
        status = self.get_runtime_status()
        if not self.enabled:
            return {
                **status,
                "success": False,
                "error": "Gemini key source not configured",
            }

        base_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": 'Return strict JSON: {"ok": true}'}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
        timeout = httpx.Timeout(20.0)
        try:
            proxy_url = proxy_url_from_mapping(resolve_proxy_for_url(base_url))
        except ProxyRequiredError as exc:
            return {
                **status,
                "success": False,
                "error": str(exc),
            }

        async with httpx.AsyncClient(
            timeout=timeout,
            trust_env=not settings.network_ignore_env_proxy,
            proxy=proxy_url,
        ) as client:
            last_error = "unknown error"
            attempts = len(self.api_keys)
            for _ in range(attempts):
                key = self._next_key()
                if not key:
                    break
                wait_sec = self._rate_limited_until.get(key, 0.0) - time.monotonic()
                if wait_sec > 0:
                    await asyncio.sleep(min(wait_sec, _RATE_LIMIT_BACKOFF_MAX))
                url = f"{base_url}?key={key}"
                try:
                    response = await client.post(url, json=payload)
                    if response.status_code == 429:
                        backoff = self._mark_rate_limited(key)
                        last_error = f"429 rate limited (backoff {backoff:.1f}s)"
                        continue
                    response.raise_for_status()
                    self._clear_rate_limit(key)
                    return {
                        **self.get_runtime_status(),
                        "success": True,
                        "error": "",
                    }
                except httpx.HTTPStatusError as exc:
                    last_error = f"http {exc.response.status_code}"
                except httpx.RequestError as exc:
                    last_error = str(exc)
                except Exception as exc:  # pragma: no cover
                    last_error = str(exc)

        return {
            **self.get_runtime_status(),
            "success": False,
            "error": last_error,
        }

