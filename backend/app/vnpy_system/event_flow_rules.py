from __future__ import annotations

from enum import Enum


class EventFlowStage(Enum):
    DISCOVERY = "discovery"
    ANALYSIS = "analysis"
    DECISION = "decision"
    EXECUTION = "execution"
    SETTLEMENT = "settlement"


EVENT_FLOW_MAP = {
    "ITEM_FOUND": {
        "stage": EventFlowStage.DISCOVERY,
        "producer": "DataCollectionEngine",
        "primary_consumer": "AnalysisEngine",
        "handler_method": "on_item_found",
        "next_event": "ITEM_ANALYZED",
    },
    "ITEM_ANALYZED": {
        "stage": EventFlowStage.ANALYSIS,
        "producer": "AnalysisEngine",
        "primary_consumer": "Strategy (via StrategyEngine)",
        "handler_method": "on_item_analyzed",
        "next_event": "SIGNAL_GENERATED or ORDER_SUBMITTED",
    },
    "SIGNAL_GENERATED": {
        "stage": EventFlowStage.DECISION,
        "producer": "Strategy",
        "primary_consumer": "ExecutionEngine",
        "handler_method": "on_signal",
        "next_event": "ORDER_SUBMITTED",
    },
    "ORDER_SUBMITTED": {
        "stage": EventFlowStage.EXECUTION,
        "producer": "Strategy or ExecutionEngine",
        "primary_consumer": "ExecutionEngine",
        "handler_method": "on_order_submitted",
        "next_event": "ORDER_TRADED or ORDER_CANCELLED",
    },
    "ORDER_TRADED": {
        "stage": EventFlowStage.SETTLEMENT,
        "producer": "ExecutionEngine",
        "primary_consumer": ["Strategy", "PortfolioManager"],
        "handler_method": "on_order_traded",
        "next_event": None,
    },
}
