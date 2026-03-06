from __future__ import annotations

import json
import re
from typing import Any

from ..config import settings
from .ragflow_client import ragflow_client


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


class MarketSentimentService:
    """
    Optional RAG-assisted market sentiment scorer for dynamic pricing.
    """

    def assess_pricing_adjustment(
        self,
        *,
        title: str,
        mode: str,
        expected_sale_price: float,
        suggested_list_price: float,
        similar_sold_prices: list[float],
    ) -> dict[str, Any]:
        if not settings.pricing_rag_sentiment_enabled:
            return {
                "enabled": False,
                "applied": False,
                "reason": "PRICING_RAG_SENTIMENT_ENABLED=false",
                "adjustment_ratio": 0.0,
                "confidence": 0.0,
                "label": "neutral",
            }

        if not ragflow_client.enabled or not ragflow_client.configured:
            return {
                "enabled": True,
                "applied": False,
                "reason": "ragflow not enabled/configured",
                "adjustment_ratio": 0.0,
                "confidence": 0.0,
                "label": "neutral",
            }

        try:
            response = ragflow_client.create_chat_completion(
                question=self._build_prompt(
                    title=title,
                    mode=mode,
                    expected_sale_price=expected_sale_price,
                    suggested_list_price=suggested_list_price,
                    similar_sold_prices=similar_sold_prices,
                ),
                include_reference=True,
            )
        except Exception as exc:
            return {
                "enabled": True,
                "applied": False,
                "reason": f"ragflow error: {exc}",
                "adjustment_ratio": 0.0,
                "confidence": 0.0,
                "label": "neutral",
            }

        answer = str(response.get("answer") or "").strip()
        parsed = self._parse_answer(answer)
        confidence = _clamp(float(parsed.get("confidence") or 0.0), 0.0, 1.0)
        max_adjustment = max(0.0, float(settings.pricing_rag_max_adjustment))
        raw_adjustment = _clamp(float(parsed.get("adjustment_ratio") or 0.0), -max_adjustment, max_adjustment)
        label = str(parsed.get("label") or "neutral").strip().lower() or "neutral"

        applied = bool(
            confidence >= float(settings.pricing_rag_min_confidence)
            and abs(raw_adjustment) > 0.0001
        )

        return {
            "enabled": True,
            "applied": applied,
            "label": label,
            "confidence": round(confidence, 4),
            "adjustment_ratio": round(raw_adjustment, 4),
            "reason": str(parsed.get("reason") or "")[:240],
            "raw_answer": answer[:1000],
            "reference": response.get("reference"),
        }

    def _build_prompt(
        self,
        *,
        title: str,
        mode: str,
        expected_sale_price: float,
        suggested_list_price: float,
        similar_sold_prices: list[float],
    ) -> str:
        samples = ",".join(f"{v:.2f}" for v in similar_sold_prices[:30]) or "none"
        return (
            "你是游戏道具市场情绪分析器。"
            "请结合知识库（版本更新公告、市场讨论、历史成交截图OCR）判断该品类短期情绪，"
            "并返回严格JSON，不要输出任何额外文字。"
            "\nJSON字段要求: label(bullish|neutral|bearish), confidence(0~1), adjustment_ratio(-0.2~0.2), reason"
            "\n其中 adjustment_ratio 为建议对定价的乘数偏移，例如 0.03 表示 +3%。"
            f"\n标题: {title}"
            f"\n定价模式: {mode}"
            f"\n模型估计售价: {expected_sale_price:.2f}"
            f"\n当前建议挂牌价: {suggested_list_price:.2f}"
            f"\n近期相似成交样本: {samples}"
        )

    def _parse_answer(self, answer: str) -> dict[str, Any]:
        parsed = self._extract_json(answer)
        if parsed is not None:
            return self._normalize_payload(parsed)

        lowered = answer.lower()
        label = "neutral"
        if any(token in lowered for token in ("bullish", "看涨", "利好", "hot", "upward")):
            label = "bullish"
        elif any(token in lowered for token in ("bearish", "看跌", "利空", "downward")):
            label = "bearish"

        adjustment = 0.0
        if label == "bullish":
            adjustment = 0.02
        elif label == "bearish":
            adjustment = -0.02
        return {
            "label": label,
            "confidence": 0.35,
            "adjustment_ratio": adjustment,
            "reason": answer[:240],
        }

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        if not text:
            return None

        candidates: list[str] = []
        markdown_match = re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
        candidates.extend(markdown_match)

        brace_match = re.search(r"(\{[\s\S]*\})", text)
        if brace_match:
            candidates.append(brace_match.group(1))

        candidates.append(text.strip())

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except Exception:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        label = str(payload.get("label") or payload.get("sentiment") or "neutral").strip().lower()
        if label not in {"bullish", "neutral", "bearish"}:
            label = "neutral"

        confidence = payload.get("confidence")
        if confidence is None:
            confidence = payload.get("score", 0.0)
        adjustment = payload.get("adjustment_ratio")
        if adjustment is None:
            adjustment = payload.get("price_bias")
        if adjustment is None:
            adjustment = 0.0

        try:
            confidence_value = float(confidence)
        except Exception:
            confidence_value = 0.0
        try:
            adjustment_value = float(adjustment)
        except Exception:
            adjustment_value = 0.0

        if label == "bullish" and adjustment_value <= 0:
            adjustment_value = 0.02
        if label == "bearish" and adjustment_value >= 0:
            adjustment_value = -0.02

        return {
            "label": label,
            "confidence": confidence_value,
            "adjustment_ratio": adjustment_value,
            "reason": str(payload.get("reason") or payload.get("analysis") or "")[:240],
        }


market_sentiment_service = MarketSentimentService()

