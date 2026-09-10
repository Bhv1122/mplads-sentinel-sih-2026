"""
backend/app/schemas/explainability.py
=============================================================================
Phase 8: Pydantic Schemas for the Explainability Layer.
=============================================================================

Defines strongly-typed, serialization-safe contracts for translating raw
detector calculations and central risk aggregation results into human-readable,
evidence-grounded, and UI-friendly explanations.

Architecture:
Detector Engines -> Detector Results -> Risk Engine -> Explainability Service -> Structured Explanation -> Frontend
"""

from enum import Enum
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict


class SeverityLevel(str, Enum):
    """Standardized severity levels for explanation factors."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionPriority(str, Enum):
    """Priority level for recommended administrative actions."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ActionCategory(str, Enum):
    """Categorical domain for recommended administrative actions."""
    ENGINEERING = "Engineering"
    FINANCIAL = "Financial"
    ADMINISTRATIVE = "Administrative"
    FIELD_VERIFICATION = "Field Verification"
    COMPLIANCE = "Compliance"


class EvidenceItem(BaseModel):
    """
    Granular numerical or diagnostic evidence supporting an explanation factor.
    """
    model_config = ConfigDict(use_enum_values=True)

    metric_key: str = Field(
        ...,
        description="Machine-readable key identifying the metric (e.g. 'overdue_days', 'peer_median')."
    )
    label: str = Field(
        ...,
        description="Human-readable title of the metric (e.g. 'Days Overdue', 'Category Peer Median')."
    )
    actual_value: Any = Field(
        ...,
        description="Raw observed value for this project."
    )
    formatted_value: str = Field(
        ...,
        description="UI-ready formatted string of the observed value (e.g. '₹2,100,000', '527 days')."
    )
    reference_value: Optional[Any] = Field(
        None,
        description="Expected, benchmark, or threshold reference value."
    )
    formatted_reference: Optional[str] = Field(
        None,
        description="UI-ready formatted string of the reference value (e.g. 'Peer Median: ₹1,290,000')."
    )
    unit: Optional[str] = Field(
        None,
        description="Unit of measurement (e.g. 'INR', 'days', '%', 'ratio')."
    )
    context: Optional[str] = Field(
        None,
        description="Contextual commentary on the significance of this metric."
    )


class EvidenceStatement(BaseModel):
    """
    Concise factual evidence statement retaining raw underlying numerical metrics.
    Strictly never invents numbers or explanations.
    """
    model_config = ConfigDict(use_enum_values=True)

    statement: str = Field(
        ...,
        description="Concise factual statement derived directly from calculated detector outputs."
    )
    raw_values: Dict[str, Any] = Field(
        default_factory=dict,
        description="Underlying raw numerical metrics and parameters."
    )
    metric_key: str = Field(
        ...,
        description="Machine-readable identifier for the metric (e.g. 'cost_multiplier', 'delay_days', 'progress_gap')."
    )
    detector_name: str = Field(
        ...,
        description="Canonical identifier of the detector."
    )
    formatted_evidence: Optional[str] = Field(
        None,
        description="Optional formatted representation of supporting evidence."
    )


class DetectorContribution(BaseModel):
    """
    Breakdown of how an individual detector contributes to the central risk score.
    """
    model_config = ConfigDict(use_enum_values=True)

    detector_name: str = Field(
        ...,
        description="Canonical detector key (e.g. 'cost_anomaly', 'delay_detection')."
    )
    display_name: str = Field(
        ...,
        description="Human-readable display name (e.g. 'Cost Anomaly Detection')."
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Raw detector score (0-100)."
    )
    weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Active weight assigned in central risk aggregation."
    )
    contribution_points: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Points contributed to overall score (score * weight)."
    )
    percentage_of_total: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of the total composite score accounted for by this detector."
    )


class RiskScoreDecompositionItem(BaseModel):
    """
    Individual detector component in transparent risk-score decomposition.
    Exposes raw detector score, configured weight, effective weight, and weighted contribution.
    """
    model_config = ConfigDict(use_enum_values=True)

    detector_key: str = Field(
        ...,
        description="Canonical identifier of the detector (e.g. 'cost_anomaly', 'delay_detection', 'explained_risk')."
    )
    detector_name: str = Field(
        ...,
        description="Human-readable title (e.g. 'Cost Anomaly', 'Delay', 'Progress Mismatch', 'Agency Pattern', 'Duplicate', 'Explained')."
    )
    detector_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Raw detector score from the existing Risk Engine (0-100)."
    )
    configured_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Configured weight assigned in the central Risk Engine (e.g. 0.20)."
    )
    effective_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Effective weight used during aggregation after renormalization if applicable."
    )
    weighted_contribution: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Calculated weighted contribution points (detector_score * effective_weight)."
    )
    percentage_of_total: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Percentage share of the total composite risk score accounted for by this detector."
    )


class RiskScoreDecomposition(BaseModel):
    """
    Transparent mathematical decomposition of the central composite risk score
    into detector contributions, verifying reconciliation within rounding tolerance.
    """
    model_config = ConfigDict(use_enum_values=True)

    final_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Final composite risk score from the central Risk Engine."
    )
    risk_level: str = Field(
        ...,
        description="Categorical risk tier (LOW, MEDIUM, HIGH, CRITICAL)."
    )
    components: List[RiskScoreDecompositionItem] = Field(
        default_factory=list,
        description="Itemized decomposition across all evaluated detectors."
    )
    total_contributions: float = Field(
        ...,
        description="Sum of the individual detector weighted contributions."
    )
    rounding_tolerance: float = Field(
        default=0.2,
        description="Configured rounding tolerance for mathematical reconciliation."
    )
    reconciled: bool = Field(
        ...,
        description="True if |total_contributions - final_score| <= rounding_tolerance."
    )
    formatted_breakdown: str = Field(
        ...,
        description="Formatted text table representing the exact additive decomposition matching governance standards."
    )


class ExplanationFactor(BaseModel):
    """
    Comprehensive explanation factor for an individual risk detector.
    Captures factual values, reference baselines, thresholds, and evidence.
    """
    model_config = ConfigDict(use_enum_values=True)

    factor_name: str = Field(
        ...,
        description="Human-readable factor title (e.g. 'Schedule Delay Overrun', 'Cost Peer Deviation')."
    )
    detector_name: str = Field(
        ...,
        description="Canonical identifier of the detector (e.g. 'delay_detection')."
    )
    severity: SeverityLevel = Field(
        ...,
        description="Severity level of this factor: LOW, MEDIUM, HIGH, or CRITICAL."
    )
    triggered_status: bool = Field(
        ...,
        description="Whether this factor triggered an anomaly or elevated risk condition."
    )
    contribution_to_risk_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Weighted points contributed by this factor to the overall risk score."
    )
    threshold_used: Optional[str] = Field(
        None,
        description="Description and numerical boundary of the threshold evaluated."
    )
    actual_value: Optional[str] = Field(
        None,
        description="Summary of the actual observed value or status."
    )
    expected_reference_value: Optional[str] = Field(
        None,
        description="Summary of the expected baseline, peer median, or planned schedule."
    )
    evidence: List[EvidenceItem] = Field(
        default_factory=list,
        description="List of granular empirical evidence metrics supporting this factor."
    )
    raw_evidence_dict: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw key-value evidence dictionary for backward compatibility."
    )
    explanation_text: str = Field(
        ...,
        description="Detailed, evidence-grounded, non-accusatory explanation narrative."
    )
    evidence_statements: List[EvidenceStatement] = Field(
        default_factory=list,
        description="Concise, factual evidence statements retaining underlying raw values."
    )


class RecommendationAction(BaseModel):
    """
    Specific, actionable administrative review recommendation.
    """
    model_config = ConfigDict(use_enum_values=True)

    action_id: str = Field(
        ...,
        description="Unique identifier for the recommendation (e.g. 'REC-DELAY-01')."
    )
    priority: ActionPriority = Field(
        ...,
        description="Priority of action: HIGH, MEDIUM, or LOW."
    )
    category: ActionCategory = Field(
        ...,
        description="Category: Engineering, Financial, Administrative, Field Verification, or Compliance."
    )
    recommendation: str = Field(
        ...,
        description="Concrete, actionable administrative step to verify or resolve the risk."
    )
    target_detector: Optional[str] = Field(
        None,
        description="Canonical detector key triggering this recommendation."
    )


class UIDisplayCard(BaseModel):
    """
    Helper structure tailored for rapid rendering in web dashboards and UI cards.
    """
    id: str
    title: str
    badge_label: str
    badge_color: str  # green, yellow, orange, red
    primary_metric: str
    secondary_metric: Optional[str] = None
    icon: str  # clock, currency, copy, bar-chart, users
    is_alert: bool = False


class RiskContributionItem(BaseModel):
    """
    Specific point contribution of a triggered detector to the overall risk score.
    """
    model_config = ConfigDict(use_enum_values=True)

    factor: str = Field(
        ...,
        description="Human-readable factor title (e.g. 'Cost anomaly', 'Delay')."
    )
    detector_name: str = Field(
        ...,
        description="Canonical identifier of the detector (e.g. 'cost_anomaly')."
    )
    points: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Points contributed by this factor to the overall risk score."
    )
    formatted_points: str = Field(
        ...,
        description="Formatted text representation (e.g. '17.2 points')."
    )


class WhyFlaggedExplanation(BaseModel):
    """
    Concise 'Why Was This Flagged?' structured explanation based ONLY on triggered detectors.
    Segregates detected anomaly, supporting evidence, and risk contribution.
    """
    model_config = ConfigDict(use_enum_values=True)

    project_id: str = Field(
        ...,
        description="Unique project identifier."
    )
    project_title: Optional[str] = Field(
        None,
        description="Official title of the project."
    )
    overall_risk: str = Field(
        ...,
        description="Overall categorical risk level (LOW, MEDIUM, HIGH, CRITICAL)."
    )
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Central composite risk score (0-100)."
    )
    is_flagged: bool = Field(
        ...,
        description="Whether any detectors triggered an anomaly or elevated risk condition."
    )
    header: str = Field(
        default="WHY WAS THIS FLAGGED?",
        description="Display header for the explanation block."
    )
    message: Optional[str] = Field(
        None,
        description="Factual summary or reassurance if no detectors triggered."
    )
    triggered_factors: List[str] = Field(
        default_factory=list,
        description="List of triggered anomaly factor names (e.g. ['Cost anomaly', 'Delay', 'Progress mismatch'])."
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="List of concise, measurable factual evidence statements."
    )
    risk_contributions: List[RiskContributionItem] = Field(
        default_factory=list,
        description="Breakdown of exact risk point contributions from triggered detectors."
    )
    formatted_text: str = Field(
        ...,
        description="Pre-formatted human-readable text representation matching the conceptual layout."
    )
    raw_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Underlying raw metrics and parameters for triggered detectors."
    )


class StructuredExplanation(BaseModel):
    """
    Top-level response payload from the Explainability Service.
    Combines machine-readable diagnostic details with UI-friendly presentation structures.
    """
    model_config = ConfigDict(use_enum_values=True)

    project_id: str = Field(
        ...,
        description="Unique project identifier."
    )
    project_title: Optional[str] = Field(
        None,
        description="Official title of the project."
    )
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Central composite risk score (0-100)."
    )
    risk_level: str = Field(
        ...,
        description="Categorical risk tier: LOW, MEDIUM, HIGH, or CRITICAL."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Aggregate confidence rating (0.0 - 1.0)."
    )
    summary: str = Field(
        ...,
        description="Executive summary synthesizing the primary risk drivers without accusatory terms."
    )
    triggered_detectors_count: int = Field(
        ...,
        description="Number of detectors that exceeded their baseline anomaly threshold."
    )
    total_detectors_count: int = Field(
        ...,
        description="Total number of detectors evaluated (normally 5)."
    )
    explanation_factors: List[ExplanationFactor] = Field(
        default_factory=list,
        description="Contributing risk factors ranked descending by point contribution."
    )
    detector_contributions: List[DetectorContribution] = Field(
        default_factory=list,
        description="Decomposition of points and percentage share across all detectors."
    )
    recommendations: List[RecommendationAction] = Field(
        default_factory=list,
        description="Ranked list of concrete administrative review actions."
    )
    concise_statements: List[str] = Field(
        default_factory=list,
        description="Concise factual evidence statements across all triggered factors."
    )
    why_flagged: Optional[WhyFlaggedExplanation] = Field(
        None,
        description="Concise 'Why Was This Flagged?' explanation containing only triggered factors."
    )
    ui_display: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pre-computed UI helpers: display cards, badge classes, color tokens, and warning chips."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="System metadata: calculation timestamp, model version, and governance disclaimer."
    )
    score_decomposition: Optional[RiskScoreDecomposition] = Field(
        None,
        description="Mathematical risk-score decomposition into detector contributions."
    )


class ProjectExplanationEvidence(BaseModel):
    """
    Granular factual evidence item supporting a project explanation factor.
    """
    model_config = ConfigDict(use_enum_values=True)

    text: str = Field(
        ...,
        description="Concise factual evidence statement (e.g. 'Cost is 2.56× peer median.')."
    )
    actual_value: Optional[Any] = Field(
        None,
        description="Observed empirical metric value for this project."
    )
    reference_value: Optional[Any] = Field(
        None,
        description="Baseline, peer median, or threshold benchmark value."
    )
    unit: Optional[str] = Field(
        None,
        description="Measurement unit (e.g. 'crore', 'days', '%', 'percentage points')."
    )


class ProjectExplanationFactor(BaseModel):
    """
    Evaluated detector factor with triggered state, severity, contribution, and evidence.
    """
    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(
        ...,
        description="Human-readable factor title (e.g. 'Cost Anomaly', 'Delay Detection')."
    )
    detector: str = Field(
        ...,
        description="Canonical identifier of the detector (e.g. 'cost_anomaly', 'delay_detection')."
    )
    triggered: bool = Field(
        ...,
        description="Whether this detector triggered an elevated anomaly/risk condition."
    )
    severity: str = Field(
        ...,
        description="Risk severity level: 'low', 'medium', 'high', or 'critical'."
    )
    contribution: float = Field(
        ...,
        description="Points contributed by this factor to the overall risk score."
    )
    detector_score: Optional[float] = Field(
        None,
        description="Raw score of the detector from central risk engine (0-100)."
    )
    weight: Optional[float] = Field(
        None,
        description="Configured weight assigned to this detector."
    )
    evidence: List[ProjectExplanationEvidence] = Field(
        default_factory=list,
        description="Empirical evidence items supporting this factor."
    )
    threshold: Optional[str] = Field(
        None,
        description="Detection threshold condition that triggers this factor."
    )
    reference_comparison: Optional[str] = Field(
        None,
        description="Peer or baseline benchmark comparison."
    )
    recommendation: Optional[str] = Field(
        None,
        description="Actionable administrative review recommendation."
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed evidence payload and granular detector metrics directly from the backend."
    )


class ProjectExplanationResponse(BaseModel):
    """
    Complete structured explanation response for GET /projects/{id}/explanation.
    Synthesizes existing detector and risk-engine results without independent re-calculation.
    """
    model_config = ConfigDict(use_enum_values=True)

    project_id: str = Field(
        ...,
        description="Unique project identifier."
    )
    risk_level: str = Field(
        ...,
        description="Categorical risk tier: LOW, MEDIUM, HIGH, or CRITICAL."
    )
    risk_score: float = Field(
        ...,
        description="Central composite risk score (0-100)."
    )
    summary: str = Field(
        ...,
        description="Factual, non-accusatory summary explaining why this project received its risk assessment."
    )
    factors: List[ProjectExplanationFactor] = Field(
        default_factory=list,
        description="List of evaluated detector factors and supporting empirical evidence."
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Prioritized administrative review recommendations."
    )
    score_decomposition: Optional[RiskScoreDecomposition] = Field(
        None,
        description="Transparent mathematical risk-score decomposition into individual detector contributions."
    )
