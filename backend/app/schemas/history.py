"""
backend/app/schemas/history.py
=============================================================================
Pydantic v2 schemas for Phase 11 Historical Tracking and Risk Evolution.
=============================================================================

Defines validation and serialization models for immutable project snapshots
and associated historical risk calculations.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# 1. Project Snapshot Schemas
# =============================================================================

class ProjectSnapshotBase(BaseModel):
    project_id: str = Field(..., max_length=64, description="Project identifier")
    project_status: str = Field(..., max_length=30, description="Project implementation status")
    
    # Financial metrics
    recommended_amount: Decimal = Field(default=Decimal("0.00"), description="Amount recommended by MP")
    sanctioned_amount: Optional[Decimal] = Field(default=None, description="Administratively sanctioned amount")
    released_amount: Decimal = Field(default=Decimal("0.00"), description="Amount released to implementing agency")
    expenditure_amount: Decimal = Field(default=Decimal("0.00"), description="Actual utilized expenditure")
    unspent_balance: Decimal = Field(default=Decimal("0.00"), description="Unspent balance available")
    utilization_rate_pct: Optional[Decimal] = Field(default=None, description="Expenditure vs Released %")
    cost_overrun_amount: Decimal = Field(default=Decimal("0.00"), description="Cost overrun in INR")
    
    # Physical & financial progress
    physical_progress_pct: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, description="Physical progress percentage")
    financial_progress_pct: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, description="Financial progress percentage")
    
    # Completion tracking
    expected_completion_date: Optional[date] = None
    actual_completion_date: Optional[date] = None
    days_delayed: int = Field(default=0, description="Days delayed beyond expected completion")
    milestone_status: str = Field(default="On Track", max_length=30)
    
    # Derived metrics & telemetry
    cost_deviation: Decimal = Field(default=Decimal("0.00"), description="Cost deviation vs peer median")
    progress_gap: Decimal = Field(default=Decimal("0.00"), description="Physical vs financial progress gap")
    derived_metrics: Optional[Dict[str, Any]] = None
    
    # Point-in-time risk evaluation
    overall_risk_score: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, description="Overall risk score (0-100)")
    risk_level: str = Field(default="Low", max_length=20, description="Categorical risk level")
    
    change_summary: Optional[str] = Field(default=None, description="Summary of changes from prior snapshot")


class ProjectSnapshotCreate(ProjectSnapshotBase):
    """Payload to create a new project snapshot."""
    snapshot_datetime: Optional[datetime] = None
    snapshot_date: Optional[date] = None


class ProjectSnapshotRead(ProjectSnapshotBase):
    """Output schema for a project snapshot."""
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: int
    snapshot_datetime: datetime
    snapshot_date: date
    created_at: datetime


# =============================================================================
# 2. Risk History Schemas
# =============================================================================

class RiskHistoryBase(BaseModel):
    project_id: str = Field(..., max_length=64)
    snapshot_id: Optional[int] = None
    overall_risk_score: Decimal = Field(..., ge=0, le=100)
    risk_level: str = Field(..., max_length=20)
    
    # Individual detector breakdown
    delay_risk_score: Optional[Decimal] = None
    cost_overrun_risk_score: Optional[Decimal] = None
    non_completion_risk_score: Optional[Decimal] = None
    leakage_risk_score: Optional[Decimal] = None
    
    detector_scores: Optional[Dict[str, Any]] = None
    weights_used: Optional[Dict[str, Any]] = None
    primary_factors: Optional[List[Dict[str, Any]]] = None
    
    engine_version: Optional[str] = "1.0.0"
    model_version: Optional[str] = "v1.0"


class RiskHistoryCreate(RiskHistoryBase):
    """Payload to insert a historical risk evaluation."""
    calculated_at: Optional[datetime] = None


class RiskHistoryRead(RiskHistoryBase):
    """Output schema for historical risk calculation."""
    model_config = ConfigDict(from_attributes=True)

    history_id: int
    calculated_at: datetime
    created_at: datetime


# =============================================================================
# 3. Composite Timeline Item
# =============================================================================

class ProjectTimelineItem(BaseModel):
    """Unified timeline entry combining snapshots and risk evaluations."""
    timestamp: datetime
    event_type: str = "snapshot"
    project_status: str
    physical_progress_pct: Decimal
    financial_progress_pct: Decimal
    overall_risk_score: Decimal
    risk_level: str
    change_summary: Optional[str] = None
    snapshot: Optional[ProjectSnapshotRead] = None
    risk_evaluation: Optional[RiskHistoryRead] = None


# =============================================================================
# 4. Idempotent Historical Ingestion Response Schema
# =============================================================================

class HistoricalUpdateResponse(BaseModel):
    """Response schema for idempotent project updates and historical tracking."""
    project_id: str
    updated: bool = Field(..., description="Whether any master project attribute was updated")
    historical_update_required: bool = Field(..., description="Whether a new snapshot & risk calculation were required")
    is_initial: bool = Field(default=False, description="Whether this update created the initial baseline snapshot")
    message: str = Field(default="", description="Descriptive status of the idempotency evaluation")
    snapshot_id: Optional[int] = Field(default=None, description="Active snapshot ID (new or existing)")
    history_id: Optional[int] = Field(default=None, description="Active risk history ID (new or existing)")
    overall_risk_score: Optional[float] = Field(default=None, description="Active overall risk score")
    risk_level: Optional[str] = Field(default=None, description="Active categorical risk level")
    change_summary: str = Field(default="", description="Summary of detected deltas or no-op notice")
    changes_count: int = Field(default=0, description="Count of monitored fields that changed")
    detector_scores: Optional[Dict[str, Any]] = Field(default=None, description="Active detector decomposition")


# =============================================================================
# 5. Meaningful Project Changes Schemas
# =============================================================================

class FieldChangeItem(BaseModel):
    """Detailed representation of an individual field change between updates."""
    field_name: str = Field(..., description="Machine-readable field name")
    display_name: str = Field(..., description="Human-readable label")
    category: str = Field(..., description="Category (status, financial, progress, timeline, risk, derived)")
    previous_value: Any = Field(default=None, description="Value in preceding snapshot")
    new_value: Any = Field(default=None, description="Value in current snapshot")
    delta: Optional[float] = Field(default=None, description="Absolute numeric delta if applicable")
    delta_pct: Optional[float] = Field(default=None, description="Percentage change if applicable")
    summary: str = Field(default="", description="Human-readable summary of this field change")


class ProjectChangeRecord(BaseModel):
    """Structured record of meaningful changes introduced in a snapshot."""
    snapshot_id: int = Field(..., description="Snapshot ID introducing these changes")
    previous_snapshot_id: Optional[int] = Field(default=None, description="Preceding snapshot ID")
    snapshot_datetime: datetime = Field(..., description="Timestamp when changes were recorded")
    project_status: str = Field(..., description="Project status at this snapshot")
    overall_risk_score: Decimal = Field(..., description="Composite risk score at this snapshot")
    risk_level: str = Field(..., description="Categorical risk level at this snapshot")
    change_summary: str = Field(..., description="Composite change summary narrative")
    changes_count: int = Field(default=0, description="Total number of monitored fields altered")
    modified_fields: List[str] = Field(default_factory=list, description="List of modified field names")
    field_changes: List[FieldChangeItem] = Field(default_factory=list, description="Granular breakdown per field")


