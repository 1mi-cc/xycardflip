from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from .. import repositories as repo

router = APIRouter(prefix="/listings", tags=["listings"])


def _build_listing_url(source: str | None, listing_id: str | None) -> str | None:
    if not listing_id:
        return None
    source_norm = (source or "").lower()
    if source_norm in {"xianyu", "goofish", "idle"}:
        return f"https://www.goofish.com/item?id={listing_id}"
    return None


@router.get("/{listing_row_id}")
def get_listing(listing_row_id: int) -> dict:
    row = repo.get_listing(listing_row_id)
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")

    raw_json = row["raw_json"]
    raw_obj: object | None
    if raw_json:
        try:
            raw_obj = json.loads(raw_json)
        except json.JSONDecodeError:
            raw_obj = raw_json
    else:
        raw_obj = None

    listing_id = row["listing_id"]
    source = row["source"]
    return {
        "listing_row_id": row["id"],
        "listing_id": listing_id,
        "source": source,
        "seller_id": row["seller_id"],
        "title": row["title"],
        "description": row["description"],
        "list_price": row["list_price"],
        "listed_at": row["listed_at"],
        "status": row["status"],
        "listing_url": _build_listing_url(source, listing_id),
        "raw_json": raw_obj,
    }
