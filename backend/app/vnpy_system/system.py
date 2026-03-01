from __future__ import annotations

import logging

from ..config import get_strategy_thresholds, normalize_strategy_profile, settings
from .analysis_engine import AnalysisEngine
from .data_collection_engine import DataCollectionEngine
from .execution_engine import ExecutionEngine, PortfolioManager
from .main_engine import main_engine
from .strategy_engine import StrategyEngine
from .strategies.bargain_hunter_strategy import BargainHunterStrategy

logger = logging.getLogger(__name__)


class VnpySystem:
    """Coordinator for vnpy-style engines."""

    def __init__(self) -> None:
        self.main_engine = main_engine
        self.strategy_profile = settings.strategy_profile
        self.strategy_thresholds = settings.strategy_thresholds
        self.strategy_engine = StrategyEngine(self.main_engine)
        self.data_engine = DataCollectionEngine(
            self.main_engine,
            scan_interval=settings.vnpy_scan_interval_sec,
            pages=settings.vnpy_scan_pages,
        )
        self.analysis_engine = AnalysisEngine(self.main_engine)
        self.execution_engine = ExecutionEngine(self.main_engine)
        self.portfolio = PortfolioManager()
        self._started = False

        self.main_engine.register_engine("strategy_engine", self.strategy_engine)
        self.main_engine.register_engine("data_engine", self.data_engine)
        self.main_engine.register_engine("analysis_engine", self.analysis_engine)
        self.main_engine.register_engine("execution_engine", self.execution_engine)
        self.main_engine.register_engine("portfolio", self.portfolio)

        self.strategy_engine.add_strategy(
            BargainHunterStrategy(self.main_engine, thresholds=self.strategy_thresholds)
        )

    def start(self) -> dict[str, str | bool]:
        if self._started:
            return {"started": False, "reason": "already running"}
        if not self.data_engine.keywords:
            default_keyword = settings.monitor_keyword.strip()
            if default_keyword:
                self.data_engine.set_keywords([default_keyword])
        self.main_engine.start()
        self.data_engine.start()
        self.strategy_engine.start_all()
        self._started = True
        logger.info("vnpy system started")
        return {"started": True}

    def stop(self) -> dict[str, str | bool]:
        if not self._started:
            return {"stopped": False, "reason": "not running"}
        self.data_engine.stop()
        self.strategy_engine.stop_all()
        self.main_engine.stop()
        self._started = False
        logger.info("vnpy system stopped")
        return {"stopped": True}

    def status(self) -> dict:
        return {
            "started": self._started,
            "keywords": list(self.data_engine.keywords),
            "data_engine": self.data_engine.status(),
            "event_engine_active": self.main_engine.event_engine.active,
            "strategy_profile": self.strategy_profile,
            "strategy_thresholds": {
                "min_score": self.strategy_thresholds.min_score,
                "min_roi": self.strategy_thresholds.min_roi,
                "max_risk_score": self.strategy_thresholds.max_risk_score,
                "allow_blocked_review": self.strategy_thresholds.allow_blocked_review,
                "auto_reject_unqualified": self.strategy_thresholds.auto_reject_unqualified,
            },
        }

    def set_keywords(self, keywords: list[str]) -> None:
        self.data_engine.set_keywords(keywords)

    def add_keyword(self, keyword: str) -> None:
        self.data_engine.add_keyword(keyword)

    def scan_once(self) -> dict[str, int]:
        return self.data_engine.scan_once()

    def set_strategy_profile(self, profile: str) -> dict[str, str | bool]:
        normalized = normalize_strategy_profile(profile)
        thresholds = get_strategy_thresholds(normalized)
        self.strategy_profile = normalized
        self.strategy_thresholds = thresholds
        for strategy in self.strategy_engine.strategies.values():
            apply_fn = getattr(strategy, "apply_thresholds", None)
            if callable(apply_fn):
                apply_fn(thresholds, normalized)
        return {
            "strategy_profile": self.strategy_profile,
            "strategy_thresholds": {
                "min_score": thresholds.min_score,
                "min_roi": thresholds.min_roi,
                "max_risk_score": thresholds.max_risk_score,
                "allow_blocked_review": thresholds.allow_blocked_review,
                "auto_reject_unqualified": thresholds.auto_reject_unqualified,
            },
        }


system = VnpySystem()
