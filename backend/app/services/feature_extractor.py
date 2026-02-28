from __future__ import annotations

import re
from typing import Any

from ..schemas import FeatureData
from .gemini_client import GeminiClient

RARITY_TOKENS = ("UR", "SSR", "SR", "R", "N")
CONDITION_TOKENS = ("mint", "near mint", "nm", "lp", "played", "damaged")
NOISE_WORDS = {
    "mint",
    "near",
    "nm",
    "lp",
    "played",
    "damaged",
    "first",
    "owner",
    "clean",
    "scratch",
    "scratches",
}


class FeatureExtractor:
    def __init__(self) -> None:
        self.gemini = GeminiClient()

    async def extract(self, title: str, description: str) -> tuple[FeatureData, str]:
        model_result = await self.gemini.extract_card_features(title, description)
        if model_result:
            normalized = self._normalize(model_result)
            return normalized, "gemini"
        return self._fallback(title, description), "rule_based"

    def _normalize(self, data: dict[str, Any]) -> FeatureData:
        return FeatureData(
            card_name=str(data.get("card_name", "unknown")).strip() or "unknown",
            rarity=str(data.get("rarity", "unknown")).strip() or "unknown",
            edition=str(data.get("edition", "unknown")).strip() or "unknown",
            card_condition=str(data.get("card_condition", "unknown")).strip() or "unknown",
            extras=data.get("extras", {}) if isinstance(data.get("extras"), dict) else {},
            confidence=float(data.get("confidence", 0.5) or 0.5),
        )

    def _fallback(self, title: str, description: str) -> FeatureData:
        text = f"{title} {description}".strip()
        rarity = "unknown"
        for token in RARITY_TOKENS:
            if re.search(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", text, re.IGNORECASE):
                rarity = token.upper()
                break

        condition = "unknown"
        for token in CONDITION_TOKENS:
            if token in text.lower():
                condition = token
                break

        card_name = self._guess_name(title)
        return FeatureData(
            card_name=card_name,
            rarity=rarity,
            edition="unknown",
            card_condition=condition,
            extras={},
            confidence=0.35,
        )

    def _guess_name(self, title: str) -> str:
        cleaned = re.sub(r"\[[^\]]+\]|\([^)]*\)", " ", title)
        for token in RARITY_TOKENS:
            cleaned = re.sub(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", " ", cleaned, flags=re.IGNORECASE)
        for token in CONDITION_TOKENS:
            cleaned = re.sub(re.escape(token), " ", cleaned, flags=re.IGNORECASE)
        words = [w for w in re.split(r"\s+", cleaned) if w and w.lower() not in NOISE_WORDS]
        cleaned = " ".join(words).strip()
        if not cleaned:
            return "unknown"
        return cleaned[:64]
