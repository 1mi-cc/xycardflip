from __future__ import annotations

import json
from typing import Any

import httpx

from ..config import settings


class GeminiClient:
    def __init__(self) -> None:
        self.api_key = settings.gemini_api_key.strip()
        self.model = settings.gemini_model

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

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

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
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
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None

