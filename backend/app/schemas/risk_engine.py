"""
backend/app/schemas/risk_engine.py
=============================================================================
Shared Pydantic Models & Interface Contracts for the Six Risk Engines.
=============================================================================

Defines the standardized return structure returned by every risk engine:
{
    "engine": "engine_name",
    "score": 0-100,
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "reason": "...",
    "details": {},
    "confidence": 0-1
}

Adheres strictly to the common architecture for the six risk engines:
1. cost_anomaly
2. duplicate_detection
3. delay_detection
4. progress_mismatch
5. agency_pattern
6. fund_utilization
"""

from enum import Enum
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict


class RiskLevel(str, Enum):
    """Standard categorical risk levels across all risk engines."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DetectorResult(BaseModel):
    """
    Standardized common detector result structure for all detection engines:
    {
        "detector_name": "...",
        "triggered": true,
        "severity": "high",
        "score": 0-100,
        "weight": 0-1,
        "contribution": 0-100,
        "threshold": "...",
        "actual_value": "...",
        "expected_value": "...",
        "reference_value": "...",
        "evidence": [],
        "metadata": {}
    }
    """
    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    detector_name: str = Field(
        ...,
        description="Canonical identifier of the detector (e.g. 'cost_anomaly', 'delay_detection')."
    )
    triggered: bool = Field(
        ...,
        description="Whether this detector triggered an anomaly/risk threshold condition."
    )
    severity: str = Field(
        ...,
        description="Severity level in standard lowercase ('low', 'medium', 'high', 'critical')."
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Normalized detector risk score between 0 and 100."
    )
    weight: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Effective weighting in central risk aggregation (0.0 to 1.0)."
    )
    contribution: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Weighted points contributed to the overall risk score (score * weight)."
    )
    threshold: Optional[str] = Field(
        None,
        description="Threshold criteria and boundary used for evaluation."
    )
    actual_value: Optional[str] = Field(
        None,
        description="Observed value summary (e.g. '₹2,850,000.00 (1.73x peer median)')."
    )
    expected_value: Optional[str] = Field(
        None,
        description="Expected value or baseline benchmark (e.g. 'Peer Median: ₹1,650,000.00')."
    )
    reference_value: Optional[str] = Field(
        None,
        description="Reference context or peer distribution summary."
    )
    evidence: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of concrete numerical evidence items supporting the evaluation."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional contextual metadata."
    )

    def to_dict(self) -> Dict[str, Any]:
        """Returns standard serialized dictionary conforming to the exact specification."""
        sev = self.severity.lower() if isinstance(self.severity, str) else str(self.severity).lower()
        return {
            "detector_name": self.detector_name,
            "triggered": bool(self.triggered),
            "severity": sev,
            "score": round(self.score, 1) if isinstance(self.score, float) else self.score,
            "weight": round(self.weight, 2) if self.weight is not None else None,
            "contribution": round(self.contribution, 2) if self.contribution is not None else None,
            "threshold": self.threshold,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "reference_value": self.reference_value,
            "evidence": self.evidence,
            "metadata": self.metadata,
        }


class EngineResult(BaseModel):
    """
    Standardized result contract returned by every independent risk engine.
    Supports both legacy engine fields and the enhanced common DetectorResult fields.
    """
    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    # Legacy fields
    engine: str = Field(
        ...,
        min_length=1,
        description="Unique identifier of the risk engine (e.g. 'cost_anomaly', 'delay_detection')."
    )
    score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Risk score between 0 (no risk) and 100 (extreme risk)."
    )
    risk_level: RiskLevel = Field(
        ...,
        description="Categorical risk tier: LOW, MEDIUM, HIGH, or CRITICAL."
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="Human-readable explanation of why the score was assigned."
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Granular diagnostic and statistical metrics supporting the score."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence level in the assessment from 0.0 (unreliable) to 1.0 (certain)."
    )

    # Standardized Common Detector Result fields
    detector_name: Optional[str] = Field(
        None,
        description="Canonical identifier of the detector (defaults to engine name)."
    )
    triggered: bool = Field(
        False,
        description="Whether this detector triggered an anomaly/risk threshold condition."
    )
    severity: Optional[str] = Field(
        None,
        description="Severity level in standard lowercase ('low', 'medium', 'high', 'critical')."
    )
    weight: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Effective weighting in central risk aggregation (0.0 to 1.0)."
    )
    contribution: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Weighted points contributed to the overall risk score (score * weight)."
    )
    threshold: Optional[str] = Field(
        None,
        description="Threshold criteria and boundary evaluated."
    )
    actual_value: Optional[str] = Field(
        None,
        description="Observed value summary."
    )
    expected_value: Optional[str] = Field(
        None,
        description="Expected value or baseline benchmark."
    )
    reference_value: Optional[str] = Field(
        None,
        description="Reference context or peer distribution summary."
    )
    evidence: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of concrete numerical evidence items supporting the evaluation."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional contextual metadata."
    )

    @field_validator("score", mode="before")
    @classmethod
    def clamp_and_round_score(cls, v: Any) -> int:
        """Ensures score is an integer strictly bounded within [0, 100]."""
        if v is None:
            return 0
        try:
            num = float(v)
            return max(0, min(100, int(round(num))))
        except (ValueError, TypeError):
            return 0

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: Any) -> float:
        """Ensures confidence is a float strictly bounded within [0.0, 1.0]."""
        if v is None:
            return 0.0
        try:
            num = float(v)
            return max(0.0, min(1.0, round(num, 4)))
        except (ValueError, TypeError):
            return 0.0

    @field_validator("risk_level", mode="before")
    @classmethod
    def normalize_risk_level(cls, v: Any) -> str:
        """Normalizes risk level strings (e.g. 'Low' -> 'LOW')."""
        if isinstance(v, str):
            clean = v.strip().upper()
            if clean in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                return clean
            # Map legacy 'Moderate' -> 'MEDIUM'
            if clean == "MODERATE":
                return "MEDIUM"
        return "LOW"

    def model_post_init(self, __context: Any) -> None:
        """Auto-populates standardized fields if they were not explicitly supplied."""
        if not self.detector_name:
            self.detector_name = self.engine
        if not self.severity:
            rl = self.risk_level if isinstance(self.risk_level, str) else self.risk_level.value
            self.severity = rl.lower()
        if not self.metadata and self.details:
            self.metadata = dict(self.details)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to standard legacy dictionary matching exact requested JSON format."""
        rl = self.risk_level if isinstance(self.risk_level, str) else self.risk_level.value
        return {
            "engine": self.engine,
            "score": self.score,
            "risk_level": rl,
            "reason": self.reason,
            "details": self.details,
            "confidence": self.confidence,
        }

    def to_standardized_dict(self) -> Dict[str, Any]:
        """Convert to the standardized common detector result structure."""
        sev = (self.severity or (self.risk_level if isinstance(self.risk_level, str) else self.risk_level.value)).lower()
        return {
            "detector_name": self.detector_name or self.engine,
            "triggered": bool(self.triggered),
            "severity": sev,
            "score": self.score,
            "weight": round(self.weight, 2) if self.weight is not None else None,
            "contribution": round(self.contribution, 2) if self.contribution is not None else None,
            "threshold": self.threshold,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "reference_value": self.reference_value,
            "evidence": self.evidence,
            "metadata": self.metadata or self.details,
        }

    def to_detector_result(self) -> DetectorResult:
        """Converts to a strongly-typed DetectorResult instance."""
        return DetectorResult(**self.to_standardized_dict())


class RiskFactorExplanation(BaseModel):
    """
    Individual risk factor explanation ranked by contribution to the aggregate score.
    """
    model_config = ConfigDict(use_enum_values=True)

    engine: str = Field(
        ...,
        description="Name of the contributing risk engine (e.g. 'cost_anomaly', 'delay_detection')."
    )
    score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Raw risk score assigned by the engine (0-100)."
    )
    contribution: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Weighted contribution in points to the overall risk score."
    )
    reason: str = Field(
        ...,
        description="Cautious, evidence-grounded explanation of the risk signal."
    )
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Actual diagnostic metrics and factual data points from engine output."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "score": self.score,
            "contribution": round(self.contribution, 2),
            "reason": self.reason,
            "evidence": self.evidence,
        }


class ExplainedRiskResult(BaseModel):
    """
    Standardized payload for Engine 6 — Explained Risk Engine.
    Deconstructs why a project received its score, ranking contributing factors and recommendations.
    """
    model_config = ConfigDict(use_enum_values=True)

    project_id: Union[str, int] = Field(
        ...,
        description="Unique identifier of the project being explained."
    )
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Central aggregate risk score (0-100)."
    )
    risk_level: str = Field(
        ...,
        description="Overall categorical risk tier: LOW, MEDIUM, HIGH, or CRITICAL."
    )
    summary: str = Field(
        ...,
        description="Deterministic, non-accusatory narrative summary of project risk posture."
    )
    engine_scores: Dict[str, int] = Field(
        default_factory=dict,
        description="Mapping of all individual engine scores (0-100)."
    )
    risk_factors: List[RiskFactorExplanation] = Field(
        default_factory=list,
        description="Contributing risk factors ranked descending by point contribution."
    )
    recommended_review: List[str] = Field(
        default_factory=list,
        description="Specific, actionable, cautious governance review recommendations."
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to standard dictionary matching exact requested JSON format."""
        return {
            "project_id": self.project_id,
            "overall_score": round(self.overall_score, 2),
            "risk_level": self.risk_level,
            "summary": self.summary,
            "engine_scores": self.engine_scores,
            "risk_factors": [rf.to_dict() for rf in self.risk_factors],
            "recommended_review": self.recommended_review,
        }


# =============================================================================
# FastAPI Response Models
# =============================================================================

class RiskFactorDetailItem(BaseModel):
    """Granular factor detail returned by GET /projects/{id}/risk/factors."""
    model_config = ConfigDict(from_attributes=True)

    engine_name: str = Field(..., description="Canonical engine key (e.g. 'delay_detection')")
    score: float = Field(..., ge=0, le=100, description="Risk score 0-100")
    risk_level: str = Field(..., description="Risk tier: LOW, MEDIUM, HIGH, CRITICAL")
    reason: str = Field(..., description="Evidence-grounded explanation")
    confidence: float = Field(..., ge=0, le=1, description="Engine confidence level 0.0-1.0")
    weight: Optional[float] = Field(None, description="Active weight in central aggregation")
    contribution: Optional[float] = Field(None, description="Points contributed to overall score")
    details: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic evidence and metrics")
    created_at: Optional[str] = Field(None, description="Timestamp of factor calculation")


class ProjectRiskFactorsResponse(BaseModel):
    """Response model for GET /projects/{id}/risk/factors."""
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    overall_score: float = Field(..., ge=0, le=100)
    risk_level: str
    confidence: float = Field(..., ge=0, le=1)
    factors: List[RiskFactorDetailItem] = Field(default_factory=list)


class ProjectRiskDetailResponse(BaseModel):
    """Complete response model for GET /projects/{id}/risk and POST /projects/{id}/risk/recalculate."""
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    overall_score: float = Field(..., ge=0, le=100, description="Central weighted risk score")
    overall_risk_score: float = Field(..., ge=0, le=100, description="Alias for backwards compatibility")
    risk_level: str = Field(..., description="Categorical risk tier")
    confidence: float = Field(..., ge=0, le=1, description="Assessment confidence")
    assessment_date: str
    model_version: str = "v1.0"
    engine_version: Optional[str] = "risk_engine_v2.0"
    config_version: Optional[str] = "v1.0"
    weights_used: Optional[Dict[str, float]] = None
    calculated_at: Optional[str] = None
    engine_scores: Dict[str, float] = Field(default_factory=dict, description="Individual engine scores (0-100)")
    reasons: Dict[str, str] = Field(default_factory=dict, description="Explanations per engine")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic evidence per engine")
    summary: Optional[str] = Field(None, description="Engine 6 narrative summary")
    recommended_review: List[str] = Field(default_factory=list, description="Recommended governance review areas")
    sub_scores: Dict[str, float] = Field(default_factory=dict, description="Backwards-compatible sub-scores")
    detector_breakdown: List[Dict[str, Any]] = Field(default_factory=list, description="Backwards-compatible breakdown")


class RiskDistributionResponse(BaseModel):
    """Response model for GET /analytics/risk-distribution."""
    model_config = ConfigDict(from_attributes=True)

    total_projects: int = Field(..., description="Total evaluated projects in portfolio")
    distribution: Dict[str, int] = Field(..., description="Project count per risk tier (LOW, MEDIUM, HIGH, CRITICAL)")
    percentages: Dict[str, float] = Field(..., description="Percentage of portfolio per risk tier")
    average_overall_score: float = Field(..., description="Average overall risk score across all projects")
    engine_averages: Dict[str, float] = Field(..., description="Average scores for each independent engine")


class EngineFlaggedProject(BaseModel):
    """Project flagged with high risk by an individual engine."""
    project_id: str
    project_title: str
    score: float
    risk_level: str
    reason: str
    confidence: float
    details: Dict[str, Any] = Field(default_factory=dict)


class EngineAnalyticsResponse(BaseModel):
    """Response model for GET /analytics/engine/{engine_name}."""
    model_config = ConfigDict(from_attributes=True)

    engine_name: str
    display_name: str
    description: str
    total_projects: int
    average_score: float
    min_score: float
    max_score: float
    average_confidence: float
    risk_tier_distribution: Dict[str, int]
    top_flagged_projects: List[EngineFlaggedProject] = Field(default_factory=list)


class AgencyProjectSummary(BaseModel):
    """Summary of a project associated with an agency."""
    project_id: str
    project_title: str
    current_status: str
    sanctioned_amount: Optional[float] = None
    expenditure_amount: Optional[float] = None
    overall_risk_score: Optional[float] = None
    risk_level: Optional[str] = None


class AgencyRiskPatternResponse(BaseModel):
    """Response model for GET /agencies/{agency_id}/risk-pattern."""
    model_config = ConfigDict(from_attributes=True)

    agency_id: str
    agency_name: str
    projects_analyzed: int
    agency_risk_score: float
    agency_risk_level: str
    confidence: float
    reason: str
    details: Dict[str, Any] = Field(default_factory=dict)
    projects: List[AgencyProjectSummary] = Field(default_factory=list)

