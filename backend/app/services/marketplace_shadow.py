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

    def _parse_timestamp(self, value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _manual_virtual_freshness(self, candidate: dict[str, Any]) -> dict[str, Any]:
        max_age_hours = max(1, int(settings.marketplace_shadow_manual_virtual_max_age_hours))
        now = datetime.now(timezone.utc)
        manual_legs: list[dict[str, Any]] = []
        for leg_name in ("buy", "sell"):
            leg = candidate.get(leg_name)
            if not isinstance(leg, dict):
                continue
            if str(leg.get("source") or "").strip() != "manual_virtual":
                continue
            parsed = self._parse_timestamp(leg.get("listed_at"))
            age_hours = None
            stale = True
            reason = "manual_virtual_listed_at_missing"
            if parsed is not None:
                age_hours = max(0.0, (now - parsed).total_seconds() / 3600.0)
                stale = age_hours > max_age_hours
                reason = "manual_virtual_baseline_stale" if stale else ""
            manual_legs.append(
                {
                    "leg": leg_name,
                    "listed_at": str(leg.get("listed_at") or ""),
                    "age_hours": round(age_hours, 2) if age_hours is not None else None,
                    "max_age_hours": max_age_hours,
                    "stale": stale,
                    "reason": reason,
                }
            )
        return {
            "applied": bool(manual_legs),
            "max_age_hours": max_age_hours,
            "stale": any(bool(item["stale"]) for item in manual_legs),
            "legs": manual_legs,
        }

    def status(self) -> dict[str, Any]:
        snapshot = repo.get_marketplace_shadow_status()
        return {
            "enabled": bool(settings.marketplace_shadow_enabled),
            "dry_run_only": True,
            "virtual_only": True,
            "shipping_cost": 0.0,
            "candidate_limit": int(settings.marketplace_shadow_candidate_limit),
            "min_net_profit": float(settings.marketplace_shadow_virtual_min_net_profit),
            "min_roi": float(settings.marketplace_shadow_virtual_min_roi),
            "min_confidence": float(settings.marketplace_shadow_virtual_min_confidence),
            "fallback_min_net_profit": float(settings.marketplace_shadow_min_net_profit),
            "fallback_min_roi": float(settings.marketplace_shadow_min_roi),
            "fallback_min_confidence": float(settings.marketplace_shadow_min_confidence),
            "threshold_source": "virtual",
            "manual_virtual_max_age_hours": int(settings.marketplace_shadow_manual_virtual_max_age_hours),
            "min_platform_count": int(settings.marketplace_shadow_min_platform_count),
            "cooldown_minutes": int(settings.marketplace_shadow_cooldown_minutes),
            **snapshot,
        }

    def virtual_report(self, *, limit: int = 200, stable_accept_count: int = 2) -> dict[str, Any]:
        items = repo.list_marketplace_shadow_intents(limit=max(1, int(limit)))
        virtual_items = [
            item
            for item in items
            if bool((item.get("decision_pack") or {}).get("virtual_only"))
            and str((item.get("decision_pack") or {}).get("item_type") or "") == "virtual_goods"
        ]
        accepted = [item for item in virtual_items if str(item.get("decision_status") or "") == "accepted"]
        blocked = [item for item in virtual_items if str(item.get("decision_status") or "") == "blocked"]
        reviewed = [item for item in accepted if str(item.get("reviewed_at") or "")]
        valid_profit = [item for item in accepted if str(item.get("review_verdict") or "") == "valid_profit"]
        profitable_outcomes = [item for item in accepted if str(item.get("outcome_status") or "") == "profitable"]
        manual_baseline = [
            item
            for item in accepted
            if str(item.get("buy_platform") or "") == "manual_virtual"
            or str(item.get("sell_platform") or "") == "manual_virtual"
        ]
        live_platform = [item for item in accepted if item not in manual_baseline]
        net_values = [float(item.get("estimated_net_profit") or 0.0) for item in virtual_items]
        roi_values = [float(item.get("estimated_roi") or 0.0) for item in virtual_items]
        grouped: dict[str, dict[str, Any]] = {}
        for item in virtual_items:
            pack = dict(item.get("decision_pack") or {})
            key = "|".join(
                [
                    str(pack.get("arbitrage_key") or item.get("arbitrage_key") or ""),
                    str(item.get("buy_platform") or ""),
                    str(item.get("sell_platform") or ""),
                ]
            )
            bucket = grouped.setdefault(
                key,
                {
                    "stability_key": key,
                    "arbitrage_key": str(pack.get("arbitrage_key") or item.get("arbitrage_key") or ""),
                    "buy_platform": str(item.get("buy_platform") or ""),
                    "sell_platform": str(item.get("sell_platform") or ""),
                    "accepted_count": 0,
                    "blocked_count": 0,
                    "reviewed_count": 0,
                    "valid_profit_count": 0,
                    "profitable_outcome_count": 0,
                    "latest_intent_id": int(item.get("id") or 0),
                    "latest_created_at": str(item.get("created_at") or ""),
                    "latest_net_profit": float(item.get("estimated_net_profit") or 0.0),
                    "latest_roi": float(item.get("estimated_roi") or 0.0),
                },
            )
            if int(item.get("id") or 0) > int(bucket.get("latest_intent_id") or 0):
                bucket["latest_intent_id"] = int(item.get("id") or 0)
                bucket["latest_created_at"] = str(item.get("created_at") or "")
                bucket["latest_net_profit"] = float(item.get("estimated_net_profit") or 0.0)
                bucket["latest_roi"] = float(item.get("estimated_roi") or 0.0)
            if str(item.get("decision_status") or "") == "accepted":
                bucket["accepted_count"] += 1
            if str(item.get("decision_status") or "") == "blocked":
                bucket["blocked_count"] += 1
            if str(item.get("reviewed_at") or ""):
                bucket["reviewed_count"] += 1
            if str(item.get("review_verdict") or "") == "valid_profit":
                bucket["valid_profit_count"] += 1
            if str(item.get("outcome_status") or "") == "profitable":
                bucket["profitable_outcome_count"] += 1

        stability_items = []
        for bucket in grouped.values():
            bucket["stable"] = int(bucket["accepted_count"]) >= max(2, int(stable_accept_count))
            stability_items.append(bucket)
        stability_items.sort(
            key=lambda item: (
                bool(item["stable"]),
                int(item["accepted_count"]),
                float(item["latest_net_profit"]),
                int(item["latest_intent_id"]),
            ),
            reverse=True,
        )
        stable_group_count = sum(1 for item in stability_items if item["stable"])
        baseline_blockers: list[str] = []
        if not accepted:
            baseline_blockers.append("no_accepted_virtual_shadow_intents")
        if accepted and not valid_profit:
            baseline_blockers.append("accepted_intents_need_valid_profit_review")
        if sum(float(item.get("estimated_net_profit") or 0.0) for item in accepted) <= 0:
            baseline_blockers.append("non_positive_accepted_net_profit")

        profitability_blockers = list(baseline_blockers)
        if stable_group_count <= 0:
            profitability_blockers.append("needs_stable_repeated_acceptance")
        if not profitable_outcomes:
            profitability_blockers.append("needs_observed_profitable_outcome")
        if manual_baseline and not live_platform:
            profitability_blockers.append("manual_virtual_baseline_only")
        if not live_platform:
            profitability_blockers.append("needs_non_manual_second_virtual_source")
        return {
            "virtual_only": True,
            "item_type": "virtual_goods",
            "sample_size": len(virtual_items),
            "accepted_count": len(accepted),
            "blocked_count": len(blocked),
            "reviewed_count": len(reviewed),
            "valid_profit_count": len(valid_profit),
            "profitable_outcome_count": len(profitable_outcomes),
            "manual_baseline_accepted_count": len(manual_baseline),
            "live_platform_accepted_count": len(live_platform),
            "stable_group_count": stable_group_count,
            "stable_accept_count": max(2, int(stable_accept_count)),
            "baseline_gate": {
                "ready": bool(accepted),
                "passed": not baseline_blockers,
                "blockers": baseline_blockers,
            },
            "profitability_gate": {
                "ready": bool(accepted),
                "passed": not profitability_blockers,
                "blockers": profitability_blockers,
            },
            "net_profit_min": round(min(net_values), 2) if net_values else 0.0,
            "net_profit_max": round(max(net_values), 2) if net_values else 0.0,
            "net_profit_avg": round(sum(net_values) / len(net_values), 2) if net_values else 0.0,
            "roi_min": round(min(roi_values), 4) if roi_values else 0.0,
            "roi_max": round(max(roi_values), 4) if roi_values else 0.0,
            "roi_avg": round(sum(roi_values) / len(roi_values), 4) if roi_values else 0.0,
            "threshold_source": "virtual",
            "manual_virtual_max_age_hours": int(settings.marketplace_shadow_manual_virtual_max_age_hours),
            "stability_items": stability_items[:20],
            "recent_items": [
                {
                    "id": int(item.get("id") or 0),
                    "decision_status": str(item.get("decision_status") or ""),
                    "blocked_reason": str(item.get("blocked_reason") or ""),
                    "review_verdict": str(item.get("review_verdict") or ""),
                    "outcome_status": str(item.get("outcome_status") or ""),
                    "observed_net_profit": float(item.get("observed_net_profit") or 0.0),
                    "buy_platform": str(item.get("buy_platform") or ""),
                    "sell_platform": str(item.get("sell_platform") or ""),
                    "estimated_net_profit": float(item.get("estimated_net_profit") or 0.0),
                    "estimated_roi": float(item.get("estimated_roi") or 0.0),
                    "created_at": str(item.get("created_at") or ""),
                }
                for item in virtual_items[:20]
            ],
        }

    def run_once(
        self,
        *,
        limit: int | None = None,
        trigger_source: str = "operator",
        force: bool = False,
        virtual_only: bool = True,
    ) -> dict[str, Any]:
        candidate_limit = max(
            1,
            min(100, int(limit or settings.marketplace_shadow_candidate_limit)),
        )
        min_platform_count = max(2, int(settings.marketplace_shadow_min_platform_count))
        cooldown_minutes = max(1, int(settings.marketplace_shadow_cooldown_minutes))
        effective_virtual_only = bool(virtual_only)
        if not effective_virtual_only:
            raise ValueError("marketplace shadow runs are virtual-only; virtual_only=false is disabled")
        threshold_source = "virtual" if effective_virtual_only else "global"
        shipping_cost = 0.0 if effective_virtual_only else float(settings.default_shipping_cost)
        min_net_profit = float(
            settings.marketplace_shadow_virtual_min_net_profit
            if effective_virtual_only
            else settings.marketplace_shadow_min_net_profit
        )
        min_roi = float(
            settings.marketplace_shadow_virtual_min_roi
            if effective_virtual_only
            else settings.marketplace_shadow_min_roi
        )
        min_confidence = float(
            settings.marketplace_shadow_virtual_min_confidence
            if effective_virtual_only
            else settings.marketplace_shadow_min_confidence
        )
        manual_virtual_max_age_hours = max(1, int(settings.marketplace_shadow_manual_virtual_max_age_hours))

        opportunity_payload = build_arbitrage_opportunities(
            limit=candidate_limit,
            window_hours=72,
            virtual_only=effective_virtual_only,
            min_platforms=2,
            min_net_profit=0.0,
            min_roi=0.0,
            buy_fee_rate=0.0,
            sell_fee_rate=float(settings.platform_fee_rate or 0.0),
            shipping_cost=shipping_cost,
        )
        candidates = list(opportunity_payload.get("items") or [])
        if effective_virtual_only:
            candidates = [
                candidate
                for candidate in candidates
                if str(candidate.get("item_type") or "").strip() == "virtual_goods"
            ]
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
                "virtual_only": effective_virtual_only,
                "shipping_cost": shipping_cost,
                "threshold_source": threshold_source,
                "manual_virtual_max_age_hours": manual_virtual_max_age_hours,
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
                freshness = self._manual_virtual_freshness(candidate)

                blocked_reason = ""
                if platform_count < min_platform_count:
                    blocked_reason = "platform_count_below_threshold"
                elif freshness.get("stale"):
                    blocked_reason = "manual_virtual_baseline_stale"
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
                            "item_type": str(candidate.get("item_type") or "").strip(),
                            "virtual_only": effective_virtual_only,
                            "threshold_source": threshold_source,
                            "min_net_profit": min_net_profit,
                            "min_roi": min_roi,
                            "min_confidence": min_confidence,
                            "manual_virtual_freshness": freshness,
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
                "virtual_only": effective_virtual_only,
                "shipping_cost": shipping_cost,
                "threshold_source": threshold_source,
                "manual_virtual_max_age_hours": manual_virtual_max_age_hours,
                "force": bool(force),
            },
            summary={
                "run_ref_id": run_id,
                "arbitrage_summary": opportunity_payload.get("summary") or {},
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
