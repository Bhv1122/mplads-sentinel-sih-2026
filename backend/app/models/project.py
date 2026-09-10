"""
backend/app/models/project.py
=============================================================================
SQLAlchemy ORM models for MPLADS projects, operational tracking, and dimensions.
=============================================================================

Strictly matches the PostgreSQL database schema (schema.sql) finalized in Phase 3.
Zero invented or mismatched columns.
"""

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Date,
    DateTime,
    Numeric,
    Boolean,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    FetchedValue,
    func
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import relationship

try:
    from app.database import Base
except ImportError:
    from backend.app.database import Base



# =============================================================================
# 1. Dimension Models
# =============================================================================

class State(Base):
    """
    Official State / Union Territory master registry (36 States/UTs).
    Maps to table: states
    """
    __tablename__ = "states"

    state_id = Column(Integer, primary_key=True, index=True)
    state_name = Column(String(100), nullable=False)
    category = Column(String(30), nullable=False)
    canonical_state_key = Column(String(50), unique=True, nullable=False, index=True)

    # Relationships
    constituencies = relationship("Constituency", back_populates="state", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="state")

    def __repr__(self) -> str:
        return f"<State(id={self.state_id}, name='{self.state_name}')>"


class Constituency(Base):
    """
    Master registry of all 543 Lok Sabha parliamentary seats.
    Maps to table: constituencies
    """
    __tablename__ = "constituencies"

    constituency_id = Column(Integer, primary_key=True, index=True)
    state_id = Column(Integer, ForeignKey("states.state_id", ondelete="RESTRICT"), nullable=False, index=True)
    state_name = Column(String(100), nullable=False)
    constituency_name = Column(String(150), nullable=False, index=True)
    raw_caption = Column(String(200), nullable=False)
    reservation_category = Column(String(20), nullable=False)
    canonical_state_key = Column(String(50), nullable=False)

    # Relationships
    state = relationship("State", back_populates="constituencies")
    projects = relationship("Project", back_populates="constituency")

    def __repr__(self) -> str:
        return f"<Constituency(id={self.constituency_id}, name='{self.constituency_name}', state='{self.state_name}')>"


# =============================================================================
# 2. Project Microdata Models
# =============================================================================

class Project(Base):
    """
    Core project master table tracking individual developmental works.
    Maps to table: projects
    """
    __tablename__ = "projects"

    project_id = Column(String(64), primary_key=True, index=True)
    project_code = Column(String(64), unique=True, nullable=False, index=True)
    project_title = Column(String(255), nullable=False, index=True)
    project_description = Column(Text, nullable=True)
    sector = Column(String(100), nullable=False, index=True)
    sub_sector = Column(String(100), nullable=True)
    state_id = Column(Integer, ForeignKey("states.state_id", ondelete="RESTRICT"), nullable=False, index=True)
    constituency_id = Column(Integer, ForeignKey("constituencies.constituency_id", ondelete="RESTRICT"), nullable=False, index=True)
    district_name = Column(String(100), nullable=False, index=True)
    block_name = Column(String(100), nullable=True)
    implementing_agency = Column(String(150), nullable=False, index=True)
    mp_name = Column(String(150), nullable=False, index=True)
    house_of_parliament = Column(String(30), nullable=False)
    financial_year = Column(String(10), nullable=False, index=True)
    current_status = Column(String(30), nullable=False, default="Recommended", index=True)
    recommendation_date = Column(Date, nullable=False, index=True)
    sanction_date = Column(Date, nullable=True)
    work_order_date = Column(Date, nullable=True)
    expected_completion_date = Column(Date, nullable=True)
    actual_completion_date = Column(Date, nullable=True, index=True)
    search_vector = Column(TSVECTOR, server_default=FetchedValue(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    state = relationship("State", back_populates="projects")
    constituency = relationship("Constituency", back_populates="projects")
    financial = relationship(
        "Financial",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan"
    )
    progress_records = relationship(
        "Progress",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="desc(Progress.reported_date)"
    )
    risk_score = relationship(
        "RiskScore",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan"
    )
    risk_factors = relationship(
        "RiskFactor",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    history_records = relationship(
        "ProjectHistory",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="desc(ProjectHistory.event_timestamp)"
    )
    features = relationship(
        "ProjectFeature",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan"
    )
    snapshots = relationship(
        "ProjectSnapshot",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="desc(ProjectSnapshot.snapshot_datetime)"
    )
    risk_histories = relationship(
        "RiskHistory",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="desc(RiskHistory.calculated_at)"
    )

    def __repr__(self) -> str:
        return f"<Project(id='{self.project_id}', title='{self.project_title[:30]}...', status='{self.current_status}')>"


class Financial(Base):
    """
    Granular financial allocation, disbursement, expenditure, and variance accounting.
    Maps to table: financials
    """
    __tablename__ = "financials"

    financial_id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(String(64), ForeignKey("projects.project_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    currency = Column(String(10), nullable=False, default="INR")
    recommended_amount = Column(Numeric(14, 2), nullable=False)
    sanctioned_amount = Column(Numeric(14, 2), nullable=True)
    released_amount = Column(Numeric(14, 2), nullable=False, default=0.00)
    expenditure_amount = Column(Numeric(14, 2), nullable=False, default=0.00)
    # unspent_balance is a generated column in DB (released_amount - expenditure_amount)
    unspent_balance = Column(Numeric(14, 2), server_default=FetchedValue())
    utilization_rate_pct = Column(Numeric(6, 2), nullable=True, index=True)
    cost_overrun_amount = Column(Numeric(14, 2), nullable=False, default=0.00, index=True)
    cost_overrun_pct = Column(Numeric(6, 2), nullable=False, default=0.00)
    last_disbursement_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="financial")

    def __repr__(self) -> str:
        return f"<Financial(project_id='{self.project_id}', sanctioned={self.sanctioned_amount}, spent={self.expenditure_amount})>"


class Progress(Base):
    """
    Chronological physical execution updates, milestone tracking, and inspections.
    Maps to table: progress
    """
    __tablename__ = "progress"

    progress_id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(String(64), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    reported_date = Column(Date, nullable=False, index=True)
    physical_progress_pct = Column(Numeric(5, 2), nullable=False, default=0.00)
    financial_progress_pct = Column(Numeric(5, 2), nullable=False, default=0.00)
    current_stage = Column(String(50), nullable=False, index=True)
    days_delayed = Column(Integer, nullable=False, default=0, index=True)
    milestone_status = Column(String(30), nullable=False, default="On Track", index=True)
    inspected_by = Column(String(150), nullable=True)
    inspection_date = Column(Date, nullable=True)
    inspection_remarks = Column(Text, nullable=True)
    geo_latitude = Column(Numeric(10, 7), nullable=True)
    geo_longitude = Column(Numeric(10, 7), nullable=True)
    photo_evidence_url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="progress_records")

    __table_args__ = (
        UniqueConstraint("project_id", "reported_date", name="uq_progress_project_date"),
    )

    def __repr__(self) -> str:
        return f"<Progress(project_id='{self.project_id}', date={self.reported_date}, physical={self.physical_progress_pct}%)>"


class RiskScore(Base):
    """
    Predictive risk assessment outputs evaluating project delay and cost overrun.
    Maps to table: risk_scores
    """
    __tablename__ = "risk_scores"

    risk_score_id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(String(64), ForeignKey("projects.project_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    overall_risk_score = Column(Numeric(5, 2), nullable=False, index=True)
    delay_risk_score = Column(Numeric(5, 2), nullable=False)
    cost_overrun_risk_score = Column(Numeric(5, 2), nullable=False)
    non_completion_risk_score = Column(Numeric(5, 2), nullable=False)
    leakage_risk_score = Column(Numeric(5, 2), nullable=False)
    risk_level = Column(String(20), nullable=False, index=True)
    confidence_score = Column(Numeric(4, 3), nullable=False)
    assessment_date = Column(Date, nullable=False, index=True)
    model_version = Column(String(50), nullable=False, default="v1.0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    weights_used = Column(JSONB, nullable=True)
    config_version = Column(String(50), nullable=True, default="v1.0")
    engine_version = Column(String(50), nullable=True, default="1.0.0")
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="risk_score")
    factors = relationship("RiskFactor", back_populates="risk_score", cascade="all, delete-orphan")

    @property
    def overall_score(self) -> float:
        return float(self.overall_risk_score) if self.overall_risk_score is not None else 0.0

    @overall_score.setter
    def overall_score(self, value):
        self.overall_risk_score = value

    def __repr__(self) -> str:
        return f"<RiskScore(project_id='{self.project_id}', score={self.overall_risk_score}, level='{self.risk_level}')>"


class RiskFactor(Base):
    """
    Granular causal drivers, weights, impacts, and mitigation recommendations.
    Maps to table: risk_factors
    """
    __tablename__ = "risk_factors"

    factor_id = Column(BigInteger, primary_key=True, autoincrement=True)
    risk_score_id = Column(BigInteger, ForeignKey("risk_scores.risk_score_id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    factor_category = Column(String(50), nullable=False, index=True)
    factor_name = Column(String(150), nullable=False)
    factor_weight = Column(Numeric(4, 3), nullable=False)
    factor_impact = Column(String(20), nullable=False, index=True)
    mitigation_recommendation = Column(Text, nullable=False)
    is_mitigated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    engine_name = Column(String(100), nullable=True, index=True)
    score = Column(Numeric(5, 2), nullable=True, index=True)
    risk_level = Column(String(20), nullable=True)
    reason = Column(Text, nullable=True)
    confidence = Column(Numeric(4, 3), nullable=True)
    details = Column(JSONB, nullable=True)

    # Relationships
    risk_score = relationship("RiskScore", back_populates="factors")
    project = relationship("Project", back_populates="risk_factors")

    __table_args__ = (
        UniqueConstraint("risk_score_id", "factor_name", name="uq_risk_factors_score_factor"),
    )

    def __repr__(self) -> str:
        return f"<RiskFactor(id={self.factor_id}, category='{self.factor_category}', impact='{self.factor_impact}')>"



class ProjectHistory(Base):
    """
    Immutable temporal audit ledger recording state transitions and events.
    Maps to table: project_history
    """
    __tablename__ = "project_history"

    history_id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(String(64), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    event_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    performed_by = Column(String(100), nullable=False)
    event_description = Column(Text, nullable=False)
    metadata_json = Column(JSONB, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="history_records")

    def __repr__(self) -> str:
        return f"<ProjectHistory(project_id='{self.project_id}', event='{self.event_type}', time={self.event_timestamp})>"


class ProjectFeature(Base):
    """
    Engineered analytical and telemetry features per project for predictive risk scoring.
    Maps to table: project_features
    """
    __tablename__ = "project_features"

    project_id = Column(String(64), ForeignKey("projects.project_id", ondelete="CASCADE"), primary_key=True, index=True)
    delay_days = Column(Integer, nullable=False, default=0, index=True)
    is_delayed = Column(Boolean, nullable=False, default=False, index=True)
    utilization_ratio = Column(Numeric(6, 4), nullable=False, default=0.0000, index=True)
    utilization_ratio_released = Column(Numeric(6, 4), nullable=False, default=0.0000)
    utilization_ratio_sanctioned = Column(Numeric(6, 4), nullable=False, default=0.0000)
    cost_per_category = Column(Numeric(14, 2), nullable=False, default=0.00)
    cost_relative_to_category = Column(Numeric(6, 4), nullable=False, default=1.0000)
    cost_category_zscore = Column(Numeric(6, 4), nullable=False, default=0.0000)
    progress_gap = Column(Numeric(6, 2), nullable=False, default=0.00, index=True)
    progress_gap_schedule = Column(Numeric(6, 2), nullable=False, default=0.00)
    progress_gap_fin_phy = Column(Numeric(6, 2), nullable=False, default=0.00)
    cost_deviation = Column(Numeric(14, 2), nullable=False, default=0.00, index=True)
    cost_deviation_sanction = Column(Numeric(14, 2), nullable=False, default=0.00)
    cost_deviation_sanction_pct = Column(Numeric(6, 2), nullable=False, default=0.00)
    cost_deviation_expenditure = Column(Numeric(14, 2), nullable=False, default=0.00)
    cost_deviation_expenditure_pct = Column(Numeric(6, 2), nullable=False, default=0.00)
    project_duration = Column(Integer, nullable=False, default=0, index=True)
    project_duration_days = Column(Integer, nullable=False, default=0)
    planned_duration_days = Column(Integer, nullable=True)
    actual_duration_days = Column(Integer, nullable=True)
    elapsed_duration_days = Column(Integer, nullable=False, default=0)
    admin_sanction_duration_days = Column(Integer, nullable=True)
    sanction_sla_delay_days = Column(Integer, nullable=False, default=0)
    unreleased_allocation = Column(Numeric(14, 2), nullable=False, default=0.00)
    is_schedule_lagging = Column(Boolean, nullable=False, default=False, index=True)
    is_disbursement_skewed = Column(Boolean, nullable=False, default=False, index=True)
    has_cost_overrun = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="features")

    def __repr__(self) -> str:
        return f"<ProjectFeature(project_id='{self.project_id}', delay={self.delay_days}d, util={self.utilization_ratio})>"


# =============================================================================
# 3. Historical Tracking & Risk Evolution Models (Phase 11)
# =============================================================================

class ProjectSnapshot(Base):
    """
    Immutable point-in-time snapshot capturing project financial progress,
    physical execution, milestone status, derived telemetry, and risk states.
    Maps to table: project_snapshots
    """
    __tablename__ = "project_snapshots"

    snapshot_id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(String(64), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_datetime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    snapshot_date = Column(Date, server_default=func.current_date(), nullable=False, index=True)
    project_status = Column(String(30), nullable=False, index=True)

    # Financial metrics
    recommended_amount = Column(Numeric(14, 2), nullable=False, default=0.00)
    sanctioned_amount = Column(Numeric(14, 2), nullable=True)
    released_amount = Column(Numeric(14, 2), nullable=False, default=0.00)
    expenditure_amount = Column(Numeric(14, 2), nullable=False, default=0.00)
    unspent_balance = Column(Numeric(14, 2), nullable=False, default=0.00)
    utilization_rate_pct = Column(Numeric(6, 2), nullable=True)
    cost_overrun_amount = Column(Numeric(14, 2), nullable=False, default=0.00)

    # Physical & financial progress
    physical_progress_pct = Column(Numeric(5, 2), nullable=False, default=0.00)
    financial_progress_pct = Column(Numeric(5, 2), nullable=False, default=0.00)

    # Milestone & completion tracking
    expected_completion_date = Column(Date, nullable=True)
    actual_completion_date = Column(Date, nullable=True)
    days_delayed = Column(Integer, nullable=False, default=0)
    milestone_status = Column(String(30), nullable=False, default="On Track")

    # Derived metrics & analytics telemetry
    cost_deviation = Column(Numeric(14, 2), nullable=False, default=0.00)
    progress_gap = Column(Numeric(6, 2), nullable=False, default=0.00)
    derived_metrics = Column(JSONB, nullable=True)

    # Point-in-time risk evaluation
    overall_risk_score = Column(Numeric(5, 2), nullable=False, default=0.00)
    risk_level = Column(String(20), nullable=False, default="Low", index=True)

    # Delta explanation & audit metadata
    change_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="snapshots")
    risk_history = relationship("RiskHistory", back_populates="snapshot", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ProjectSnapshot(id={self.snapshot_id}, project_id='{self.project_id}', time={self.snapshot_datetime}, score={self.overall_risk_score})>"


class RiskHistory(Base):
    """
    Detailed risk evaluation calculations and multi-detector decompositions
    corresponding to project snapshots over time.
    Maps to table: risk_history
    """
    __tablename__ = "risk_history"

    history_id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(String(64), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_id = Column(BigInteger, ForeignKey("project_snapshots.snapshot_id", ondelete="CASCADE"), nullable=True, index=True)
    overall_risk_score = Column(Numeric(5, 2), nullable=False)
    risk_level = Column(String(20), nullable=False, index=True)

    # Individual detector breakdown scores
    delay_risk_score = Column(Numeric(5, 2), nullable=True)
    cost_overrun_risk_score = Column(Numeric(5, 2), nullable=True)
    non_completion_risk_score = Column(Numeric(5, 2), nullable=True)
    leakage_risk_score = Column(Numeric(5, 2), nullable=True)

    # Modular risk engine decomposition
    detector_scores = Column(JSONB, nullable=True)
    weights_used = Column(JSONB, nullable=True)
    primary_factors = Column(JSONB, nullable=True)

    # Model & engine versions
    engine_version = Column(String(50), nullable=True, default="1.0.0")
    model_version = Column(String(50), nullable=True, default="v1.0")

    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="risk_histories")
    snapshot = relationship("ProjectSnapshot", back_populates="risk_history")

    def __repr__(self) -> str:
        return f"<RiskHistory(id={self.history_id}, project_id='{self.project_id}', score={self.overall_risk_score}, level='{self.risk_level}')>"


