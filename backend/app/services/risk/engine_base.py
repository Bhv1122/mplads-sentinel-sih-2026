"""
backend/app/services/risk/engine_base.py
=============================================================================
Abstract Base Class & Shared Interface Contract for the Six Risk Engines.
=============================================================================

Establishes the common architecture that every one of the six risk engines
must implement:
1. Cost Anomaly Engine (`cost_anomaly`)
2. Duplicate Detection Engine (`duplicate_detection`)
3. Delay Detection Engine (`delay_detection`)
4. Progress Mismatch Engine (`progress_mismatch`)
5. Agency Pattern Engine (`agency_pattern`)
6. Fund Utilization Engine (`fund_utilization`)

Every engine must inherit from BaseRiskEngine and implement `evaluate()`,
returning an `EngineResult` conforming to the contract:
{
    "engine": "engine_name",
    "score": 0-100,
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "reason": "...",
    "details": {},
    "confidence": 0-1
}
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session

try:
    from app.config import settings
    from app.schemas.risk_engine import RiskLevel, EngineResult
except ImportError:
    from backend.app.config import settings
    from backend.app.schemas.risk_engine import RiskLevel, EngineResult

logger = logging.getLogger(__name__)

# Canonical registry of all six risk engines in the common architecture
SIX_RISK_ENGINES: List[str] = [
    "cost_anomaly",
    "duplicate_detection",
    "delay_detection",
    "progress_mismatch",
    "agency_pattern",
    "fund_utilization",
]


class BaseRiskEngine(ABC):
    """
    Abstract base class for the six independent risk engines.
    Provides shared threshold evaluation, validation, and explainability helpers.
    """
    engine_name: str = "base_engine"
    version: str = "1.0.0"

    @abstractmethod
    def evaluate(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> EngineResult:
        """
        Executes risk evaluation for a single project.

        Args:
            project_id: Unique project identifier.
            db: Active SQLAlchemy database session.
            context: Optional runtime parameters (e.g. as_of_date, thresholds).

        Returns:
            Standardized EngineResult containing score (0-100), risk_level (LOW|MEDIUM|HIGH|CRITICAL),
            reason, details, and confidence (0-1).
        """
        raise NotImplementedError("Subclasses must implement evaluate()")

    def calculate_risk_level(self, score: float) -> RiskLevel:
        """
        Maps a 0-100 score to the standard risk level using centralized configuration:
        0–29  = LOW
        30–59 = MEDIUM
        60–79 = HIGH
        80–100 = CRITICAL
        """
        level_str = settings.score_to_risk_level(score)
        return RiskLevel(level_str)

    def get_engine_thresholds(self) -> Dict[str, Any]:
        """Retrieves centralized engine-specific thresholds for this engine."""
        return settings.engine_thresholds.get(self.engine_name, {})

    def evaluate_confidence(self, available_signals: int, total_signals: int) -> float:
        """
        Computes a bounded confidence score based on the proportion of
        valid diagnostic signals available.
        """
        if total_signals <= 0:
            return settings.CONFIDENCE_DEFAULT_FALLBACK
        ratio = max(0.0, min(1.0, available_signals / total_signals))
        return round(ratio, 3)

    def build_result(
        self,
        score: float,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
        risk_level: Optional[RiskLevel] = None,
        # Standardized common detector result fields
        detector_name: Optional[str] = None,
        triggered: Optional[bool] = None,
        severity: Optional[str] = None,
        threshold: Optional[str] = None,
        actual_value: Optional[str] = None,
        expected_value: Optional[str] = None,
        reference_value: Optional[str] = None,
        evidence: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        weight: Optional[float] = None,
        contribution: Optional[float] = None,
    ) -> EngineResult:
        """Helper to construct a validated EngineResult with standardized detector result fields."""
        computed_score = max(0, min(100, int(round(score))))
        computed_level = risk_level or self.calculate_risk_level(computed_score)
        computed_conf = confidence if confidence is not None else settings.CONFIDENCE_DEFAULT_FALLBACK
        det_name = detector_name or self.engine_name
        is_triggered = triggered if triggered is not None else (computed_score >= 30)
        sev = (severity or (computed_level if isinstance(computed_level, str) else computed_level.value)).lower()
        meta = metadata if metadata is not None else dict(details or {})
        evid = list(evidence) if evidence is not None else []

        return EngineResult(
            engine=det_name,
            score=computed_score,
            risk_level=computed_level,
            reason=reason,
            details=details or {},
            confidence=computed_conf,
            detector_name=det_name,
            triggered=is_triggered,
            severity=sev,
            weight=weight,
            contribution=contribution,
            threshold=threshold,
            actual_value=actual_value,
            expected_value=expected_value,
            reference_value=reference_value,
            evidence=evid,
            metadata=meta,
        )
