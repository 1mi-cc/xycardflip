from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from .. import repositories as repo
from .autotrade import auto_trade_service
from .ragflow_client import ragflow_client


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return str(value)


def build_market_snapshot_documents(
    *,
    limit: int = 20,
    listing_hours: int = 24,
    sales_days: int = 7,
) -> list[dict[str, Any]]:
    snapshots = repo.get_normalized_market_snapshots(
        limit=limit,
        listing_hours=listing_hours,
        sales_days=sales_days,
    )
    documents: list[dict[str, Any]] = []
    for index, snapshot in enumerate(snapshots, start=1):
        normalized_key = str(snapshot.get("normalized_key") or f"snapshot-{index}")
        safe_name = re.sub(r"[^0-9A-Za-z_-]+", "-", normalized_key)[:72].strip("-") or f"snapshot-{index}"
        content = "\n".join(
            [
                f"# Market Snapshot: {snapshot.get('normalized_title') or normalized_key}",
                "",
                f"- normalized_key: {normalized_key}",
                f"- item_type: {snapshot.get('item_type')}",
                f"- regime_tag: {snapshot.get('regime_tag')}",
                f"- sample_confidence: {snapshot.get('sample_confidence')}",
                f"- open_listing_count: {snapshot.get('open_listing_count')}",
                f"- recent_listing_count_24h: {snapshot.get('recent_listing_count_24h')}",
                f"- recent_sales_count_7d: {snapshot.get('recent_sales_count_7d')}",
                f"- seller_count: {snapshot.get('seller_count')}",
                f"- noise_listing_count: {snapshot.get('noise_listing_count')}",
                f"- min_list_price: {snapshot.get('min_list_price')}",
                f"- p25_list_price: {snapshot.get('p25_list_price')}",
                f"- median_list_price: {snapshot.get('median_list_price')}",
                f"- max_list_price: {snapshot.get('max_list_price')}",
                f"- latest_list_price: {snapshot.get('latest_list_price')}",
                f"- median_sold_price_7d: {snapshot.get('median_sold_price_7d')}",
                f"- price_gap_vs_sales: {snapshot.get('price_gap_vs_sales')}",
                f"- spread_ratio: {snapshot.get('spread_ratio')}",
                "",
                "## Summary",
                str(snapshot.get("summary_text") or ""),
                "",
                "## Raw JSON",
                "```json",
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                "```",
            ]
        )
        documents.append(
            {
                "normalized_key": normalized_key,
                "title": str(snapshot.get("normalized_title") or normalized_key),
                "filename": f"{index:02d}-{safe_name}.md",
                "content": content,
                "snapshot": snapshot,
            }
        )
    return documents


def write_market_snapshot_docs(
    *,
    limit: int = 20,
    listing_hours: int = 24,
    sales_days: int = 7,
) -> tuple[tempfile.TemporaryDirectory[str], list[str], list[dict[str, Any]]]:
    temp_dir = tempfile.TemporaryDirectory(prefix="market-snapshots-")
    docs = build_market_snapshot_documents(
        limit=limit,
        listing_hours=listing_hours,
        sales_days=sales_days,
    )
    paths: list[str] = []
    for item in docs:
        path = Path(temp_dir.name) / str(item["filename"])
        path.write_text(str(item["content"]), encoding="utf-8")
        paths.append(str(path))
    return temp_dir, paths, docs


def _parse_json_answer(answer: str) -> dict[str, Any] | None:
    text = str(answer or "").strip()
    if not text:
        return None
    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidates.extend(fenced)
    inline = re.findall(r"(\{.*\})", text, flags=re.S)
    candidates.extend(inline)
    for candidate in candidates:
        snippet = str(candidate or "").strip()
        if not snippet.startswith("{"):
            continue
        try:
            payload = json.loads(snippet)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def get_strategy_proposal(
    *,
    limit: int = 12,
    listing_hours: int = 24,
    sales_days: int = 7,
    include_reference: bool = True,
) -> dict[str, Any]:
    snapshots = repo.get_normalized_market_snapshots(
        limit=limit,
        listing_hours=listing_hours,
        sales_days=sales_days,
    )
    thresholds = auto_trade_service.tuning_snapshot()
    policy = auto_trade_service.tuning_policy()
    prompt = "\n".join(
        [
            "You are a market strategy analyst for a card flipping system.",
            "Use the normalized market snapshots below to recommend threshold changes.",
            "Return strict JSON with keys: direction, min_score_delta, min_roi_delta, max_risk_score_delta, confidence, reasons, summary.",
            "Only recommend small threshold adjustments. If evidence is weak, return direction=hold with zero deltas.",
            "",
            "Current thresholds:",
            json.dumps(_json_safe(thresholds), ensure_ascii=False),
            "",
            "Auto-tune policy:",
            json.dumps(_json_safe(policy), ensure_ascii=False),
            "",
            "Normalized market snapshots:",
            json.dumps([_json_safe(item) for item in snapshots], ensure_ascii=False),
        ]
    )

    ragflow_status = ragflow_client.status()
    if not ragflow_client.enabled or not ragflow_client.configured or not bool(ragflow_status.get("chat_id_configured")):
        return {
            "available": False,
            "reason": ragflow_status.get("message") or "RAGFlow not configured",
            "current_thresholds": thresholds,
            "policy": policy,
            "snapshots": snapshots,
            "prompt": prompt,
            "proposal": None,
        }

    response = ragflow_client.create_chat_completion(
        question=prompt,
        include_reference=include_reference,
    )
    answer = str(response.get("answer") or "").strip()
    proposal = _parse_json_answer(answer)
    return {
        "available": True,
        "reason": "",
        "current_thresholds": thresholds,
        "policy": policy,
        "snapshots": snapshots,
        "prompt": prompt,
        "proposal": proposal,
        "raw_answer": answer,
        "reference": response.get("reference"),
    }
