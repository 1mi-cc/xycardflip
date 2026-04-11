from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .. import repositories as repo
from ..config import settings
from .arbitrage import build_arbitrage_opportunities


class MarketplaceShadowService:
    """Dry-run only automation layer for cross-platform marketplace candidates."""

    def _confidence_score(self, candidate: dict[str, Any]) -> float:
        platform_count = max(0, int(candidate.get("source_count") or 0))
        listing_count = max(0, int(candidate.get("listing_count") or 0))
        extra_listings = max(0, listing_count - platform_count)
        score = 0.78 + (max(0, platform_count - 2) * 0.08) + (min(3, extra_listings) * 0.04)
        return round(min(0.98, score), 4)

    def _intent_key(self, candidate: dict[str, Any]) -> str:
        raw = "|".join(
            [
                str(candidate.get("arbitrage_key") or "").strip(),
                str((candidate.get("buy") or {}).get("source") or "").strip(),
                str((candidate.get("sell") or {}).get("source") or "").strip(),
            ]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def status(self) -> dict[str, Any]:
        snapshot = repo.get_marketplace_shadow_status()
        return {
            "enabled": bool(settings.marketplace_shadow_enabled),
            "dry_run_only": True,
            "candidate_limit": int(settings.marketplace_shadow_candidate_limit),
            "min_net_profit": float(settings.marketplace_shadow_min_net_profit),
            "min_roi": float(settings.marketplace_shadow_min_roi),
            "min_confidence": float(settings.marketplace_shadow_min_confidence),
            "min_platform_count": int(settings.marketplace_shadow_min_platform_count),
            "cooldown_minutes": int(settings.marketplace_shadow_cooldown_minutes),
            **snapshot,
        }

    def run_once(
        self,
        *,
        limit: int | None = None,
        trigger_source: str = "operator",
        force: bool = False,
    ) -> dict[str, Any]:
        candidate_limit = max(
            1,
            min(100, int(limit or settings.marketplace_shadow_candidate_limit)),
        )
        min_net_profit = float(settings.marketplace_shadow_min_net_profit)
        min_roi = float(settings.marketplace_shadow_min_roi)
        min_confidence = float(settings.marketplace_shadow_min_confidence)
        min_platform_count = max(2, int(settings.marketplace_shadow_min_platform_count))
        cooldown_minutes = max(1, int(settings.marketplace_shadow_cooldown_minutes))

        opportunity_payload = build_arbitrage_opportunities(
            limit=candidate_limit,
            window_hours=72,
            min_platforms=2,
            min_net_profit=0.0,
            min_roi=0.0,
            buy_fee_rate=0.0,
            sell_fee_rate=float(settings.platform_fee_rate or 0.0),
            shipping_cost=float(settings.default_shipping_cost or 0.0),
        )
        candidates = list(opportunity_payload.get("items") or [])
        accepted = 0
        blocked = 0
        errors = 0
        intent_rows: list[dict[str, Any]] = []

        run_row = repo.create_marketplace_shadow_run(
            trigger_source=trigger_source,
            status="completed",
            candidate_count=len(candidates),
            accepted_count=0,
            blocked_count=0,
            error_count=0,
            config={
                "candidate_limit": candidate_limit,
                "min_net_profit": min_net_profit,
                "min_roi": min_roi,
                "min_confidence": min_confidence,
                "min_platform_count": min_platform_count,
                "cooldown_minutes": cooldown_minutes,
                "dry_run_only": True,
                "force": bool(force),
            },
            summary={
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "arbitrage_summary": opportunity_payload.get("summary") or {},
            },
        )
        run_id = int(run_row.get("id") or 0) or None

        for candidate in candidates:
            try:
                confidence_score = self._confidence_score(candidate)
                intent_key = self._intent_key(candidate)
                platform_count = max(0, int(candidate.get("source_count") or 0))
                listing_count = max(0, int(candidate.get("listing_count") or 0))
                estimated_net_profit = float(candidate.get("estimated_net_profit") or 0.0)
                estimated_roi = float(candidate.get("estimated_roi") or 0.0)

                blocked_reason = ""
                if platform_count < min_platform_count:
                    blocked_reason = "platform_count_below_threshold"
                elif estimated_net_profit < min_net_profit:
                    blocked_reason = "net_profit_below_threshold"
                elif estimated_roi < min_roi:
                    blocked_reason = "roi_below_threshold"
                elif confidence_score < min_confidence:
                    blocked_reason = "confidence_below_threshold"
                elif not force and repo.get_recent_marketplace_shadow_accept(
                    intent_key=intent_key,
                    cooldown_minutes=cooldown_minutes,
                ):
                    blocked_reason = "cooldown_active"

                decision_status = "blocked" if blocked_reason else "accepted"
                row = repo.create_marketplace_shadow_intent(
                    run_id=run_id,
                    intent_key=intent_key,
                    arbitrage_key=str(candidate.get("arbitrage_key") or "").strip(),
                    reference_title=str(candidate.get("reference_title") or "").strip(),
                    buy_platform=str((candidate.get("buy") or {}).get("source") or "").strip(),
                    sell_platform=str((candidate.get("sell") or {}).get("source") or "").strip(),
                    buy_listing_id=str((candidate.get("buy") or {}).get("listing_id") or "").strip(),
                    sell_listing_id=str((candidate.get("sell") or {}).get("listing_id") or "").strip(),
                    platform_count=platform_count,
                    listing_count=listing_count,
                    estimated_net_profit=estimated_net_profit,
                    estimated_roi=estimated_roi,
                    confidence_score=confidence_score,
                    decision_status=decision_status,
                    blocked_reason=blocked_reason,
                    snapshot={
                        "candidate": candidate,
                        "decision": {
                            "confidence_score": confidence_score,
                            "decision_status": decision_status,
                            "blocked_reason": blocked_reason,
                            "dry_run_only": True,
                        },
                    },
                )
                intent_rows.append(row)
                if blocked_reason:
                    blocked += 1
                else:
                    accepted += 1
            except Exception as exc:  # pragma: no cover - defensive bookkeeping
                errors += 1
                intent_rows.append(
                    {
                        "run_id": run_id,
                        "decision_status": "error",
                        "blocked_reason": str(exc),
                    }
                )

        final_run = repo.update_marketplace_shadow_run(
            int(run_id or 0),
            status="completed",
            candidate_count=len(candidates),
            accepted_count=accepted,
            blocked_count=blocked,
            error_count=errors,
            config={
                "candidate_limit": candidate_limit,
                "min_net_profit": min_net_profit,
                "min_roi": min_roi,
                "min_confidence": min_confidence,
                "min_platform_count": min_platform_count,
                "cooldown_minutes": cooldown_minutes,
                "dry_run_only": True,
                "force": bool(force),
            },
            summary={
                "run_ref_id": run_id,
                "accepted_intent_ids": [item.get("id") for item in intent_rows if item.get("decision_status") == "accepted"],
                "blocked_intent_ids": [item.get("id") for item in intent_rows if item.get("decision_status") == "blocked"],
                "errors": errors,
            },
        )

        return {
            "enabled": bool(settings.marketplace_shadow_enabled),
            "dry_run_only": True,
            "candidate_count": len(candidates),
            "accepted_count": accepted,
            "blocked_count": blocked,
            "error_count": errors,
            "run": final_run,
            "intents": intent_rows,
        }


marketplace_shadow_service = MarketplaceShadowService()
