"""
backend/app/schemas/project.py
=============================================================================
Pydantic v2 schemas for request validation and response serialization.
=============================================================================

Faithfully mirrors the PostgreSQL mplads_db schema with proper typing,
defaults, enum validations, and rich response models.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict, model_validator


T = TypeVar("T")


# =============================================================================
# 1. Enums
# =============================================================================

class HouseOfParliamentEnum(str, Enum):
    LOK_SABHA = "Lok Sabha"
    RAJYA_SABHA = "Rajya Sabha"


class ProjectStatusEnum(str, Enum):
    RECOMMENDED = "Recommended"
    SANCTIONED = "Sanctioned"
    WORK_ORDER_ISSUED = "Work Order Issued"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    STALLED = "Stalled"


class MilestoneStatusEnum(str, Enum):
    ON_TRACK = "On Track"
    DELAYED = "Delayed"
    CRITICAL = "Critical"
    COMPLETED = "Completed"


class ProjectStageEnum(str, Enum):
    FEASIBILITY = "Feasibility"
    TENDERING = "Tendering"
    CONTRACT_AWARDED = "Contract Awarded"
    FOUNDATION = "Foundation"
    STRUCTURE = "Structure"
    FINISHING = "Finishing"
    INSPECTION = "Inspection"
    COMMISSIONED = "Commissioned"
    COMPLETED = "Completed"


class RiskLevelEnum(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    CRITICAL = "Critical"


class FactorImpactEnum(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


# =============================================================================
# 2. Dimension Summaries
# =============================================================================

class StateSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state_id: int
    state_name: str
    category: str
    canonical_state_key: str


class ConstituencySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    constituency_id: int
    state_id: int
    state_name: str
    constituency_name: str
    raw_caption: str
    reservation_category: str
    canonical_state_key: str


# =============================================================================
# 3. Operational & Child Table Schemas
# =============================================================================

class FinancialBase(BaseModel):
    currency: str = "INR"
    recommended_amount: Decimal = Field(ge=0)
    sanctioned_amount: Optional[Decimal] = Field(default=None, ge=0)
    released_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    expenditure_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    cost_overrun_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    cost_overrun_pct: Decimal = Field(default=Decimal("0.00"), ge=0)
    last_disbursement_date: Optional[date] = None


class FinancialCreate(FinancialBase):
    pass


class FinancialUpdate(BaseModel):
    sanctioned_amount: Optional[Decimal] = Field(default=None, ge=0)
    released_amount: Optional[Decimal] = Field(default=None, ge=0)
    expenditure_amount: Optional[Decimal] = Field(default=None, ge=0)
    cost_overrun_amount: Optional[Decimal] = Field(default=None, ge=0)
    last_disbursement_date: Optional[date] = None


class FinancialRead(FinancialBase):
    model_config = ConfigDict(from_attributes=True)

    financial_id: int
    project_id: str
    unspent_balance: Optional[Decimal] = None
    utilization_rate_pct: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProgressBase(BaseModel):
    reported_date: date
    physical_progress_pct: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    financial_progress_pct: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    current_stage: str
    days_delayed: int = Field(default=0, ge=0)
    milestone_status: str = "On Track"
    inspected_by: Optional[str] = None
    inspection_date: Optional[date] = None
    inspection_remarks: Optional[str] = None
    geo_latitude: Optional[Decimal] = None
    geo_longitude: Optional[Decimal] = None
    photo_evidence_url: Optional[str] = None


class ProgressCreate(ProgressBase):
    pass


class ProgressRead(ProgressBase):
    model_config = ConfigDict(from_attributes=True)

    progress_id: int
    project_id: str
    created_at: Optional[datetime] = None


class RiskFactorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    factor_id: int
    risk_score_id: int
    project_id: str
    factor_category: str
    factor_name: str
    factor_weight: Decimal
    factor_impact: str
    mitigation_recommendation: str
    is_mitigated: bool
    created_at: Optional[datetime] = None


class RiskScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    risk_score_id: int
    project_id: str
    overall_risk_score: Decimal
    delay_risk_score: Decimal
    cost_overrun_risk_score: Decimal
    non_completion_risk_score: Decimal
    leakage_risk_score: Decimal
    risk_level: str
    confidence_score: Decimal
    assessment_date: date
    model_version: str
    factors: List[RiskFactorRead] = []
    created_at: Optional[datetime] = None


class ProjectHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    history_id: int
    project_id: str
    event_type: str
    previous_status: Optional[str] = None
    new_status: str
    event_timestamp: datetime
    performed_by: str
    event_description: str
    metadata_json: Optional[Dict[str, Any]] = None


# =============================================================================
# 4. Project Master Schemas
# =============================================================================

class ProjectBase(BaseModel):
    project_code: str
    project_title: str
    project_description: Optional[str] = None
    sector: str
    sub_sector: Optional[str] = None
    state_id: int
    constituency_id: int
    district_name: str
    block_name: Optional[str] = None
    implementing_agency: str
    mp_name: str
    house_of_parliament: str = "Lok Sabha"
    financial_year: str
    current_status: str = "Recommended"
    recommendation_date: date
    sanction_date: Optional[date] = None
    work_order_date: Optional[date] = None
    expected_completion_date: Optional[date] = None
    actual_completion_date: Optional[date] = None


class ProjectCreate(ProjectBase):
    project_id: Optional[str] = None
    recommended_amount: Decimal = Field(default=Decimal("1000000.00"), ge=0)


class ProjectUpdate(BaseModel):
    project_title: Optional[str] = None
    project_description: Optional[str] = None
    sector: Optional[str] = None
    sub_sector: Optional[str] = None
    block_name: Optional[str] = None
    implementing_agency: Optional[str] = None
    current_status: Optional[str] = None
    sanction_date: Optional[date] = None
    work_order_date: Optional[date] = None
    expected_completion_date: Optional[date] = None
    actual_completion_date: Optional[date] = None

    # Financial accounting fields
    recommended_amount: Optional[Decimal] = None
    sanctioned_amount: Optional[Decimal] = None
    released_amount: Optional[Decimal] = None
    expenditure_amount: Optional[Decimal] = None

    # Physical and milestone execution fields
    physical_progress_pct: Optional[Decimal] = None
    financial_progress_pct: Optional[Decimal] = None
    days_delayed: Optional[int] = None
    milestone_status: Optional[str] = None



class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    project_code: str
    project_title: str
    sector: str
    state_name: str
    district_name: str
    mp_name: str
    current_status: str
    financial_year: str
    sanctioned_amount: Optional[Decimal] = None
    released_amount: Optional[Decimal] = None
    expenditure_amount: Optional[Decimal] = None
    physical_progress_pct: Optional[Decimal] = None
    days_delayed: Optional[int] = 0
    overall_risk_score: Optional[Decimal] = None
    risk_level: Optional[str] = None
    search_relevance: Optional[float] = None


class ProjectFeatureBase(BaseModel):
    delay_days: int = 0
    is_delayed: bool = False
    utilization_ratio: Decimal = Field(default=Decimal("0.0000"), ge=0)
    utilization_ratio_released: Decimal = Field(default=Decimal("0.0000"), ge=0)
    utilization_ratio_sanctioned: Decimal = Field(default=Decimal("0.0000"), ge=0)
    cost_per_category: Decimal = Field(default=Decimal("0.00"), ge=0)
    cost_relative_to_category: Decimal = Field(default=Decimal("1.0000"), ge=0)
    cost_category_zscore: Decimal = Decimal("0.0000")
    progress_gap: Decimal = Decimal("0.00")
    progress_gap_schedule: Decimal = Decimal("0.00")
    progress_gap_fin_phy: Decimal = Decimal("0.00")
    cost_deviation: Decimal = Decimal("0.00")
    cost_deviation_sanction: Decimal = Decimal("0.00")
    cost_deviation_sanction_pct: Decimal = Decimal("0.00")
    cost_deviation_expenditure: Decimal = Decimal("0.00")
    cost_deviation_expenditure_pct: Decimal = Decimal("0.00")
    project_duration: int = Field(default=0, ge=0)
    project_duration_days: int = Field(default=0, ge=0)
    planned_duration_days: Optional[int] = None
    actual_duration_days: Optional[int] = None
    elapsed_duration_days: int = Field(default=0, ge=0)
    admin_sanction_duration_days: Optional[int] = None
    sanction_sla_delay_days: int = Field(default=0, ge=0)
    unreleased_allocation: Decimal = Field(default=Decimal("0.00"), ge=0)
    is_schedule_lagging: bool = False
    is_disbursement_skewed: bool = False
    has_cost_overrun: bool = False


class ProjectFeatureRead(ProjectFeatureBase):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProjectDetail(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    created_at: datetime
    updated_at: datetime

    # Nested relations
    state: Optional[StateSummary] = None
    constituency: Optional[ConstituencySummary] = None
    financial: Optional[FinancialRead] = None
    progress_records: List[ProgressRead] = []
    risk_score: Optional[RiskScoreRead] = None
    risk_factors: List[RiskFactorRead] = []
    history_records: List[ProjectHistoryRead] = []
    features: Optional[ProjectFeatureRead] = None



# =============================================================================
# 5. Generic Pagination Wrapper
# =============================================================================

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int = 0
    limit: int = 20
    page: Optional[int] = 1
    page_size: Optional[int] = 20
    total_pages: Optional[int] = 1


# =============================================================================
# 6. Analytics & Governance Response Schemas
# =============================================================================

class KPIOverviewResponse(BaseModel):
    total_projects: int
    total_sanctioned_cr: Decimal
    total_released_cr: Decimal
    total_expenditure_cr: Decimal
    overall_utilization_pct: Decimal
    completed_projects_count: int
    in_progress_projects_count: int
    stalled_projects_count: int
    delayed_projects_count: int
    high_risk_projects_count: int


class SectorAnalyticsItem(BaseModel):
    sector: str
    total_projects: int
    completed_projects: int
    in_progress_projects: int
    stalled_projects: int
    avg_physical_progress_pct: Decimal
    total_sanctioned_amount: Decimal
    total_released_amount: Decimal
    total_expenditure_amount: Decimal
    total_unspent_balance: Decimal
    overall_utilization_pct: Decimal
    avg_sector_risk_score: Decimal
    delayed_projects_count: int


class DelayedProjectItem(BaseModel):
    project_id: str
    project_code: str
    project_title: str
    state_name: str
    constituency_name: str
    district_name: str
    mp_name: str
    sector: str
    implementing_agency: str
    current_status: str
    days_delayed: int
    milestone_status: str
    physical_progress_pct: Decimal
    sanctioned_amount: Optional[Decimal] = None
    delay_risk_score: Decimal
    risk_level: str


class RiskDistributionSummary(BaseModel):
    low: int = 0
    moderate: int = 0
    high: int = 0
    critical: int = 0
    total_assessed: int = 0
    distribution_by_level: Dict[str, int] = {}


class FinancialSummaryStats(BaseModel):
    total_allocated_amount: Decimal = Field(default=Decimal("0.00"), description="Total recommended/allocated outlay (INR)")
    total_sanctioned_amount: Decimal = Field(default=Decimal("0.00"), description="Total sanctioned outlay (INR)")
    total_released_amount: Decimal = Field(default=Decimal("0.00"), description="Total released outlay (INR)")
    total_expenditure_amount: Decimal = Field(default=Decimal("0.00"), description="Total expenditure outlay (INR)")
    total_unspent_balance: Decimal = Field(default=Decimal("0.00"), description="Total unspent balance (INR)")
    overall_utilization_pct: Decimal = Field(default=Decimal("0.00"), description="Overall fund utilization rate %")


class StateAggregationItem(BaseModel):
    state_id: int
    state_name: str
    total_projects: int
    completed_projects: int
    ongoing_projects: int
    total_sanctioned: Decimal
    total_released: Decimal
    total_expenditure: Decimal
    avg_progress_pct: Decimal


class DistrictAggregationItem(BaseModel):
    district_name: str
    state_name: str
    total_projects: int
    completed_projects: int
    ongoing_projects: int
    total_sanctioned: Decimal
    total_expenditure: Decimal
    avg_progress_pct: Decimal


class AnalyticsSummaryResponse(BaseModel):
    total_projects: int
    completed_projects: int
    ongoing_projects: int
    delayed_projects: int
    stalled_projects: int
    average_progress: Decimal
    total_allocated_amount: Decimal
    total_sanctioned_amount: Decimal
    total_released_amount: Decimal
    total_expenditure_amount: Decimal
    total_unspent_balance: Decimal
    overall_utilization_pct: Decimal
    financials: FinancialSummaryStats
    risk_distribution: Dict[str, int]
    risk_stats: RiskDistributionSummary
    status_distribution: Dict[str, int]
    state_aggregations: List[StateAggregationItem] = []
    district_aggregations: List[DistrictAggregationItem] = []
    sector_aggregations: List[SectorAnalyticsItem] = []


class HighRiskProjectItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    project_code: str
    project_title: str
    project_name: Optional[str] = None
    state_name: str
    constituency_name: str
    district_name: str
    mp_name: str
    sector: str
    implementing_agency: str
    current_status: str
    risk_score: Optional[Decimal] = None
    overall_risk_score: Decimal
    delay_risk_score: Decimal
    cost_overrun_risk_score: Decimal
    risk_level: str
    confidence_score: Decimal
    sanctioned_amount: Optional[Decimal] = None
    days_delayed: int
    important_risk_factors: Optional[List[Dict[str, Any]]] = None
    risk_factors: Optional[List[Dict[str, Any]]] = None
    primary_risk_factors: Optional[List[Dict[str, Any]]] = None

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            p_name = data.get("project_name") or data.get("project_title")
            data["project_name"] = p_name
            data["project_title"] = data.get("project_title") or p_name

            r_score = data.get("risk_score") or data.get("overall_risk_score")
            data["risk_score"] = r_score
            data["overall_risk_score"] = data.get("overall_risk_score") or r_score

            factors = data.get("important_risk_factors") or data.get("primary_risk_factors") or data.get("risk_factors") or []
            data["important_risk_factors"] = factors
            data["risk_factors"] = factors
            data["primary_risk_factors"] = factors
        return data


class MissingInfoAuditItem(BaseModel):
    project_id: str
    project_code: str
    project_title: str
    state_name: str
    constituency_name: str
    current_status: str
    missing_fields_count: int
    missing_fields: List[str]


class StateEquityItem(BaseModel):
    state_id: int
    state_name: str
    category: str
    total_lok_sabha_seats: int
    sc_reserved_seats: int
    sc_seat_share_pct: Decimal
    statutory_sc_allocation_pct: Decimal
    sc_share_vs_statutory_delta_pct: Decimal
    st_reserved_seats: int
    st_seat_share_pct: Decimal
    statutory_st_allocation_pct: Decimal
    st_share_vs_statutory_delta_pct: Decimal
    cumulative_released_cr: Decimal
    mandated_sc_outlay_target_cr: Optional[Decimal] = None
    mandated_st_outlay_target_cr: Optional[Decimal] = None


class StateEfficiencyItem(BaseModel):
    state_id: int
    state_name: str
    category: str
    released_cr: Decimal
    expenditure_cr: Decimal
    unspent_balance_cr: Decimal
    utilization_rate_pct: Decimal
    rank_utilization: int
    sanction_rate_pct: Decimal
    rank_sanction_rate: int
    completion_rate_pct: Decimal
    rank_completion_rate: int
    works_recommended: int
    works_sanctioned: int
    works_completed: int


class BudgetHistoricalItem(BaseModel):
    financial_year: str
    start_year: int
    scheme_entitlement_per_mp_cr: Decimal
    budget_estimate_cr: Decimal
    revised_estimate_cr: Optional[Decimal] = None
    actual_expenditure_cr: Optional[Decimal] = None
    be_vs_actual_variance_cr: Optional[Decimal] = None
    budget_utilization_pct: Optional[Decimal] = None
    status_notes: str


# =============================================================================
# 8. Risk Engine Response Schemas (Phase 7)
# =============================================================================

class RiskDetectorBreakdown(BaseModel):
    """Individual detector contribution to the overall risk score."""
    detector_key: str = Field(..., description="Internal detector identifier")
    detector_name: str = Field(..., description="Human-readable detector name")
    score: int = Field(..., ge=0, le=100, description="Detector risk score (0-100)")
    weight: float = Field(..., ge=0, le=1, description="Configured weight for this detector")
    effective_weight: float = Field(..., ge=0, le=1, description="Actual weight used (renormalized if peers failed)")
    severity: str = Field(..., description="Detector severity rating (low/medium/high)")
    reason: str = Field(..., description="Human-readable explanation")
    details: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic details")
    # Standardized Common Detector Result fields:
    contribution: Optional[float] = Field(None, description="Weighted contribution points to overall score")
    triggered: bool = Field(False, description="Whether this detector triggered an anomaly/risk threshold condition")
    threshold: Optional[str] = Field(None, description="Threshold evaluated")
    actual_value: Optional[str] = Field(None, description="Observed value summary")
    expected_value: Optional[str] = Field(None, description="Expected value or baseline benchmark")
    reference_value: Optional[str] = Field(None, description="Reference baseline or peer context")
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="List of concrete numerical evidence items")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Contextual metadata")


class RiskEngineSubScores(BaseModel):
    """Sub-scores mapped to risk_scores table columns."""
    delay_risk_score: float = Field(default=0.0, ge=0, le=100)
    cost_overrun_risk_score: float = Field(default=0.0, ge=0, le=100)
    non_completion_risk_score: float = Field(default=0.0, ge=0, le=100)
    leakage_risk_score: float = Field(default=0.0, ge=0, le=100)


class RiskEngineResult(BaseModel):
    """Complete risk engine evaluation result for a single project."""
    project_id: str
    overall_risk_score: float = Field(default=0.0, ge=0, le=100, description="Weighted aggregate risk score")
    overall_score: Optional[float] = Field(None, ge=0, le=100, description="Weighted aggregate risk score")
    risk_level: str = Field(..., description="Risk classification (Low, Moderate, High, Critical)")
    confidence: float = Field(..., ge=0, le=1, description="Fraction of detectors that executed successfully")
    assessment_date: str = Field(..., description="Date of assessment (ISO format)")
    model_version: str = Field(default="v1.0", description="Risk engine version identifier")
    engine_version: Optional[str] = Field("risk_engine_v2.0", description="Risk engine version identifier")
    config_version: Optional[str] = Field("v1.0", description="Configuration version")
    weights_used: Optional[Dict[str, float]] = None
    calculated_at: Optional[str] = None
    engine_scores: Dict[str, float] = Field(default_factory=dict, description="Individual engine scores (0-100)")
    reasons: Dict[str, str] = Field(default_factory=dict, description="Explanations per engine")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic evidence per engine")
    summary: Optional[str] = Field(None, description="Engine 6 narrative summary")
    recommended_review: List[str] = Field(default_factory=list, description="Recommended governance review areas")
    sub_scores: RiskEngineSubScores = Field(default_factory=RiskEngineSubScores)
    detector_breakdown: List[RiskDetectorBreakdown] = Field(default_factory=list)
    evaluated_at: Optional[str] = Field(None, description="UTC timestamp of evaluation")
    error: Optional[str] = Field(None, description="Error message if evaluation failed")

    @model_validator(mode="before")
    @classmethod
    def sync_overall_scores(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "overall_score" in data and ("overall_risk_score" not in data or data.get("overall_risk_score") is None):
                data["overall_risk_score"] = data["overall_score"]
            elif "overall_risk_score" in data and ("overall_score" not in data or data.get("overall_score") is None):
                data["overall_score"] = data["overall_risk_score"]
        return data


class RiskBatchRequest(BaseModel):
    """Request body for batch risk recalculation."""
    project_ids: Optional[List[str]] = Field(None, description="Specific project IDs to evaluate. If null, evaluates all projects.")
    limit: int = Field(default=100, ge=1, le=500, description="Maximum number of projects to evaluate when project_ids is null")

