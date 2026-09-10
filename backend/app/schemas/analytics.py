"""
backend/app/schemas/analytics.py
=============================================================================
Pydantic schemas for Phase 10 Visualizations & Analytics.
Supports server-side filtering, state/district rankings, delay buckets,
cost anomaly peer statistics, temporal trends, and geospatial map data.
=============================================================================
"""

from decimal import Decimal
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Overview & KPIs
# ---------------------------------------------------------------------------

class AnalyticsOverviewResponse(BaseModel):
    total_projects: int = Field(..., description="Total count of projects matching filters")
    high_risk_projects: int = Field(..., description="Projects in High risk tier (score 60-79)")
    critical_risk_projects: int = Field(..., description="Projects in Critical risk tier (score >= 80)")
    moderate_risk_projects: int = Field(..., description="Projects in Moderate/Medium risk tier (score 30-59)")
    low_risk_projects: int = Field(..., description="Projects in Low risk tier (score < 30)")
    average_risk_score: float = Field(..., description="Portfolio average overall risk score (0-100)")
    flagged_projects_count: int = Field(..., description="Count of projects with risk score >= 40 or active flags")
    flagged_percentage: float = Field(..., description="Percentage of evaluated projects flagged")
    total_sanctioned_amount: Decimal = Field(..., description="Total sanctioned amount in INR")
    total_expenditure_amount: Decimal = Field(..., description="Total expenditure amount in INR")
    overall_utilization_pct: float = Field(..., description="Expenditure vs Released/Sanctioned utilization %")
    delayed_projects_count: int = Field(..., description="Count of projects past scheduled completion date")
    average_delay_days: float = Field(..., description="Average days overdue across delayed projects")


# ---------------------------------------------------------------------------
# 2. State-Wise Analysis
# ---------------------------------------------------------------------------

class StateAnalyticsItem(BaseModel):
    state_id: int
    state_name: str
    total_projects: int
    high_risk_projects: int
    critical_risk_projects: int
    average_risk_score: float
    average_delay_days: float
    cost_anomaly_count: int
    total_sanctioned: Decimal
    total_expenditure: Decimal
    utilization_pct: float

class StateAnalyticsResponse(BaseModel):
    states: List[StateAnalyticsItem]
    total_states: int


# ---------------------------------------------------------------------------
# 3. District-Wise Analysis
# ---------------------------------------------------------------------------

class DistrictAnalyticsItem(BaseModel):
    district_name: str
    state_name: str
    total_projects: int
    high_risk_projects: int
    critical_risk_projects: int
    average_risk_score: float
    average_delay_days: float
    total_sanctioned: Decimal
    total_expenditure: Decimal

class DistrictAnalyticsResponse(BaseModel):
    districts: List[DistrictAnalyticsItem]
    total_districts: int


# ---------------------------------------------------------------------------
# 4. Delay Statistics
# ---------------------------------------------------------------------------

class TopDelayedProjectItem(BaseModel):
    project_id: str
    project_title: str
    state_name: str
    district_name: str
    sector: str
    days_delayed: int
    expected_completion_date: Optional[str]
    current_status: str
    risk_score: float

class DelayAnalyticsResponse(BaseModel):
    total_projects_assessed: int
    on_time_count: int
    delayed_count: int
    severely_delayed_count: int
    average_delay_days: float
    max_delay_days: int
    delay_buckets: Dict[str, int] = Field(
        ...,
        description="Histogram counts for 0 days, 1-30 days, 31-90 days, 91-180 days, 181-365 days, 365+ days"
    )
    top_delayed_projects: List[TopDelayedProjectItem]


# ---------------------------------------------------------------------------
# 5. Cost Anomaly Statistics
# ---------------------------------------------------------------------------

class TopCostAnomalyItem(BaseModel):
    project_id: str
    project_title: str
    state_name: str
    district_name: str
    sector: str
    evaluated_cost: Decimal
    peer_median: Decimal
    deviation_percentage: float
    robust_z_score: float
    anomaly_type: str
    reason: str
    risk_score: float

class CostAnomalyAnalyticsResponse(BaseModel):
    total_projects_assessed: int
    normal_cost_count: int
    cost_anomalous_count: int
    cost_anomaly_rate_pct: float
    average_deviation_pct: float
    deviation_distribution: Dict[str, int] = Field(
        ...,
        description="Histogram counts for <= 0%, 1-25%, 26-50%, 51-100%, > 100%"
    )
    largest_deviations: List[TopCostAnomalyItem]


# ---------------------------------------------------------------------------
# 6. Temporal Trends
# ---------------------------------------------------------------------------

class TrendPointItem(BaseModel):
    period: str = Field(..., description="Time interval e.g. YYYY-MM")
    project_count: int
    cumulative_projects: int
    average_risk_score: float
    high_risk_count: int
    delayed_count: int
    cost_anomalies_count: int = Field(default=0, description="Count of cost anomalous works in this period")
    sanctioned_amount_cr: float
    expenditure_amount_cr: float
    utilization_rate_pct: float

class TrendAnalyticsResponse(BaseModel):
    granularity: str = "month"
    trend_points: List[TrendPointItem]


# ---------------------------------------------------------------------------
# 7. Geospatial & Map Analytics
# ---------------------------------------------------------------------------

class MapStateItem(BaseModel):
    state_name: str
    state_code: str
    total_projects: int
    high_risk_projects: int
    critical_risk_projects: int
    average_risk_score: float
    average_delay_days: float
    sanctioned_amount_cr: float
    expenditure_amount_cr: float
    density_score: float = Field(..., description="Normalized 0-100 score for choropleth shading")

class MapAnalyticsResponse(BaseModel):
    states: List[MapStateItem]
    active_metric: str
    max_value: float
