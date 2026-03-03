from __future__ import annotations

from fastapi import APIRouter

from .. import repositories as repo
from ..schemas import ListingIn, SaleIn

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/sales")
def ingest_sales(rows: list[SaleIn]) -> dict[str, int]:
    count = repo.insert_sales(rows)
    return {"inserted": count}


@router.post("/listings")
def ingest_listings(rows: list[ListingIn]) -> dict[str, int]:
    count = repo.insert_listings(rows)
    return {"inserted": count}

