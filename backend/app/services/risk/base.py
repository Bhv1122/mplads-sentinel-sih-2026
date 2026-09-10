"""
backend/app/services/risk/base.py
=============================================================================
Abstract Base Class and Common Schema Contract for MPLADS Risk Detectors.
=============================================================================

Every risk detector in Phase 6 must adhere to this interface:
- Independent calculation logic
- Standardized output structure: score (0-100), reason, severity, details
- Resilient exception handling and explainable diagnostics
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session


class RiskDetectorResult(BaseModel):
    """
    Standardized result contract returned by every independent risk detector.
    """
    score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Risk score between 0 (no risk) and 100 (extreme risk)."
    )
    reason: str = Field(
        ...,
        description="Human-readable explanation of why the score was assigned."
    )
    severity: Literal["low", "medium", "high"] = Field(
        ...,
        description="Categorical severity rating."
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Granular diagnostic and statistical metrics supporting the score."
    )

    @field_validator("score")
    @classmethod
    def clamp_score(cls, v: int) -> int:
        return max(0, min(100, int(round(v))))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to standard dictionary representation."""
        return {
            "score": self.score,
            "reason": self.reason,
            "severity": self.severity,
            "details": self.details,
        }


def score_to_severity(score: float) -> Literal["low", "medium", "high"]:
    """
    Maps a 0-100 risk score to standard severity level.
    0-29: low
    30-69: medium
    70-100: high
    """
    if score >= 70:
        return "high"
    elif score >= 30:
        return "medium"
    return "low"


class BaseRiskDetector(ABC):
    """
    Abstract base detector class. Every risk detector subclass must implement
    the detect() method independently.
    """
    name: str = "base_detector"
    version: str = "1.0.0"

    @abstractmethod
    def detect(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> RiskDetectorResult:
        """
        Execute risk detection for a single project.

        Args:
            project_id: Unique identifier for the project.
            db: Active SQLAlchemy database session.
            context: Optional pre-loaded context or parameter overrides.

        Returns:
            RiskDetectorResult with score, reason, severity, and details.
        """
        raise NotImplementedError("Subclasses must implement detect()")
