from __future__ import annotations

import json
from typing import Any, Iterable

import httpx

from ..config import settings


class GeminiClient:
    def __init__(self) -> None:
        self.api_keys = self._parse_keys(settings.gemini_api_key)
        self.model = settings.gemini_model
        self._key_index = 0

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
        if not self.api_keys:
            return ""
        key = self.api_keys[self._key_index % len(self.api_keys)]
        self._key_index = (self._key_index + 1) % len(self.api_keys)
        return key

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
        async with httpx.AsyncClient(timeout=timeout) as client:
            last_error: Exception | None = None
            for _ in range(len(self.api_keys)):
                key = self._next_key()
                if not key:
                    break
                url = f"{base_url}?key={key}"
                try:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text)
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
