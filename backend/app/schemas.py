from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SaleIn(BaseModel):
    source: str = Field(default="manual_import")
    item_id: str | None = None
    title: str
    description: str = ""
    sold_price: float = Field(gt=0)
    sold_at: datetime
    raw: dict[str, Any] = Field(default_factory=dict)


class ListingIn(BaseModel):
    source: str = Field(default="manual_import")
    listing_id: str | None = None
    seller_id: str | None = None
    title: str
    description: str = ""
    list_price: float = Field(gt=0)
    listed_at: datetime
    status: Literal["open", "sold", "closed"] = "open"
    raw: dict[str, Any] = Field(default_factory=dict)


class FeatureData(BaseModel):
    card_name: str
    rarity: str = "unknown"
    edition: str = "unknown"
    card_condition: str = "unknown"
    extras: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.5


class ValuationOut(BaseModel):
    listing_row_id: int
    expected_sale_price: float
    buy_limit: float
    suggested_list_price: float
    ci_low: float
    ci_high: float
    model_confidence: float
    comparables_count: int
    reasoning: str


class OpportunityOut(BaseModel):
    opportunity_id: int
    listing_row_id: int
    expected_profit: float
    roi: float
    score: float
    status: str


class ApproveTradeIn(BaseModel):
    opportunity_id: int
    approved_buy_price: float = Field(gt=0)
    approved_by: str = "owner"
    note: str = ""


class MarkListedIn(BaseModel):
    listing_url: str
    note: str = ""


class MarkSoldIn(BaseModel):
    sold_price: float = Field(gt=0)
    note: str = ""

