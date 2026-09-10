"""
backend/app/routes/analytics.py
=============================================================================
FastAPI router for governance dashboards, predictive risk, and fiscal analytics.
=============================================================================
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.project import (
    KPIOverviewResponse,
    SectorAnalyticsItem,
    DelayedProjectItem,
    HighRiskProjectItem,
    MissingInfoAuditItem,
    StateEquityItem,
    StateEfficiencyItem,
    BudgetHistoricalItem,
    AnalyticsSummaryResponse
)
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    StateAnalyticsResponse,
    DistrictAnalyticsResponse,
    DelayAnalyticsResponse,
    CostAnomalyAnalyticsResponse,
    TrendAnalyticsResponse,
    MapAnalyticsResponse,
)
from app.schemas.risk_engine import (
    RiskDistributionResponse,
    EngineAnalyticsResponse,
    EngineFlaggedProject,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics & Governance"])
high_risk_router = APIRouter(tags=["Analytics & Governance"])


@router.get(
    "",
    response_model=AnalyticsSummaryResponse,
    summary="Get comprehensive project-level governance and operational analytics"
)
def get_analytics(db: Session = Depends(get_db)):
    """
    Calculates useful project-level statistics from actual PostgreSQL data:
    - total projects
    - total allocated/sanctioned/released/expenditure amount
    - completed, ongoing, delayed, and stalled projects
    - average physical progress percentage
    - risk distribution breakdown
    - state/district/sector aggregations
    """
    return AnalyticsService.get_analytics_summary(db=db)


@high_risk_router.get(
    "/high-risk",
    response_model=List[HighRiskProjectItem],
    summary="List projects classified as high risk sorted by risk score"
)
def get_high_risk_projects_direct(
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum risk score threshold"),
    db: Session = Depends(get_db)
):
    """
    Returns projects classified as high risk using risk_scores and risk_factors,
    including project ID, project name, risk score, risk level, and important risk factors.
    Sorted highest-risk projects first.
    """
    return AnalyticsService.get_high_risk_projects(db=db, limit=limit, offset=offset, min_score=min_score)


@router.get(
    "/kpis",
    response_model=KPIOverviewResponse,
    summary="Get national and portfolio KPI metrics"
)
def get_kpi_overview(db: Session = Depends(get_db)):
    """
    Returns high-level KPI cards: total sanctioned funds (in Cr), released funds,
    expenditure, utilization rate %, active delayed count, and critical risk count.
    """
    return AnalyticsService.get_kpis(db=db)


@router.get(
    "/sectors",
    response_model=List[SectorAnalyticsItem],
    summary="Get sector-wise financial and physical progress breakdown"
)
def get_sector_analytics(db: Session = Depends(get_db)):
    """
    Aggregates project counts, completions, sanctioned/released/spent funds,
    utilization %, and average risk scores by developmental sector.
    """
    return AnalyticsService.get_sector_summary(db=db)


@router.get(
    "/delayed",
    response_model=List[DelayedProjectItem],
    summary="Real-time surveillance of delayed, stalled, and critical projects"
)
def get_delayed_projects(
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Returns prioritized delayed and stalled projects ordered by days delayed
    and delay likelihood risk score.
    """
    return AnalyticsService.get_delayed_projects(db=db, limit=limit, offset=offset)


@router.get(
    "/high-risk",
    response_model=List[HighRiskProjectItem],
    summary="Predictive high-risk project escalation list with causal factors"
)
def get_high_risk_projects(
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum risk score threshold"),
    db: Session = Depends(get_db)
):
    """
    Returns vulnerable works (risk score >= 40 or High/Critical risk tier)
    with aggregated primary causal factors and recommended mitigations in structured JSON.
    """
    return AnalyticsService.get_high_risk_projects(db=db, limit=limit, offset=offset, min_score=min_score)


@router.get(
    "/missing-info",
    response_model=List[MissingInfoAuditItem],
    summary="Compliance audit identifying projects with missing information"
)
def get_missing_information_audit(
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Audits administrative compliance by flagging uninspected projects,
    missing completion dates, unmapped geo-coordinates, or absent work orders.
    """
    return AnalyticsService.get_missing_info_audit(db=db, limit=limit, offset=offset)


@router.get(
    "/state-equity",
    response_model=List[StateEquityItem],
    summary="SC/ST statutory allocation and state equity analysis"
)
def get_state_equity(db: Session = Depends(get_db)):
    """
    Evaluates statutory SC (15%) and ST (7.5%) target funding allocations
    versus cumulative disbursements across all 36 States and Union Territories.
    """
    return AnalyticsService.get_state_equity_summary(db=db)


@router.get(
    "/state-efficiency",
    response_model=List[StateEfficiencyItem],
    summary="State and UT efficiency rankings"
)
def get_state_efficiency(
    limit: int = Query(36, ge=1, le=36, description="Number of States/UTs to return"),
    db: Session = Depends(get_db)
):
    """
    Ranks States and UTs on fund utilization %, works sanction rates,
    and completion efficiency.
    """
    return AnalyticsService.get_state_efficiency_rankings(db=db, limit=limit)


@router.get(
    "/budget-history",
    response_model=List[BudgetHistoricalItem],
    summary="33-year Union Budget Demand No. 91 trends (1993-2025)"
)
def get_budget_history(db: Session = Depends(get_db)):
    """
    Returns the complete longitudinal fiscal series of MPLADS budgetary allocations,
    revised estimates, actual disbursements, and variance trends since scheme inception.
    """
    return AnalyticsService.get_budget_history(db=db)


# =============================================================================
# Risk Analytics Endpoints
# =============================================================================

ENGINE_METADATA: Dict[str, Dict[str, str]] = {
    "cost_anomaly": {
        "display_name": "Cost Anomaly Detection",
        "description": "Statistical peer outlier analysis comparing unit costs against sector benchmarks."
    },
    "duplicate_detection": {
        "display_name": "Duplicate Detection",
        "description": "Semantic embedding similarity detection identifying duplicative work proposals."
    },
    "delay_detection": {
        "display_name": "Delay Detection",
        "description": "Timeline slippage and overdue delivery milestone tracking for ongoing and completed works."
    },
    "progress_mismatch": {
        "display_name": "Financial/Physical Progress Mismatch",
        "description": "Divergence monitoring between physical on-ground milestone delivery and fund expenditure."
    },
    "agency_pattern": {
        "display_name": "Agency Pattern Analysis",
        "description": "Historical institutional performance tracking across executing and implementing agencies."
    },
    "explained_risk": {
        "display_name": "Explained Risk Synthesis",
        "description": "Narrative risk synthesis and causal factor ranking with actionable review recommendations."
    }
}


@router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    summary="Get comprehensive filtered KPI overview for analytics dashboards"
)
def get_analytics_overview(
    state: Optional[str] = Query(None, description="Filter by state name"),
    district: Optional[str] = Query(None, description="Filter by district name"),
    risk_level: Optional[str] = Query(None, description="Filter by risk category (Low, Medium, High, Critical)"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    sector: Optional[str] = Query(None, description="Filter by sector category"),
    fy: Optional[str] = Query(None, description="Filter by financial year (e.g. '2024-25')"),
    db: Session = Depends(get_db)
):
    """
    Returns filtered portfolio summary KPIs:
    - total projects
    - high risk projects
    - critical risk projects
    - average risk score
    - flagged percentage
    - total sanctioned, expenditure, and utilization rate %
    - total delayed and cost anomalous projects
    """
    return AnalyticsService.get_overview_filtered(
        db=db,
        state_name=state,
        district_name=district,
        risk_level=risk_level,
        status=status,
        sector=sector,
        financial_year=fy,
    )


@router.get(
    "/risk-distribution",
    response_model=RiskDistributionResponse,
    summary="Get portfolio-wide risk distribution and engine averages (with optional filters)"
)
def get_risk_distribution(
    state: Optional[str] = Query(None, description="Filter by state name"),
    district: Optional[str] = Query(None, description="Filter by district name"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    sector: Optional[str] = Query(None, description="Filter by sector category"),
    fy: Optional[str] = Query(None, description="Filter by financial year"),
    db: Session = Depends(get_db)
):
    """
    Returns portfolio risk distribution across tiers (LOW, MEDIUM, HIGH, CRITICAL),
    percentages, portfolio average, and individual engine score averages with optional filtering.
    """
    return AnalyticsService.get_risk_distribution_filtered(
        db=db,
        state_name=state,
        district_name=district,
        status=status,
        sector=sector,
        financial_year=fy,
    )


@router.get(
    "/states",
    response_model=StateAnalyticsResponse,
    summary="Get state-level risk, delay, and financial comparative analytics"
)
def get_states_analytics(
    metric: str = Query("risk_score", description="Metric to sort by (risk_score, projects, critical, delays, cost_anomalies)"),
    state: Optional[str] = Query(None, description="Optional filter by single state"),
    risk_level: Optional[str] = Query(None, description="Filter by risk category"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    sector: Optional[str] = Query(None, description="Filter by sector category"),
    fy: Optional[str] = Query(None, description="Filter by financial year"),
    limit: int = Query(36, ge=1, le=50, description="Max states to return"),
    db: Session = Depends(get_db)
):
    """
    Provides multi-metric state ranking and comparative analytics:
    - total projects
    - high risk & critical risk counts
    - average risk score
    - average delay days
    - cost anomaly count
    - sanctioned amount & expenditure
    """
    return AnalyticsService.get_states_analytics(
        db=db,
        metric=metric,
        state_name=state,
        risk_level=risk_level,
        status=status,
        sector=sector,
        financial_year=fy,
        limit=limit,
    )


@router.get(
    "/districts",
    response_model=DistrictAnalyticsResponse,
    summary="Get district-level risk, delay, and project volume analytics"
)
def get_districts_analytics(
    state: Optional[str] = Query(None, description="Filter by state name"),
    district: Optional[str] = Query(None, description="Filter by specific district name"),
    risk_level: Optional[str] = Query(None, description="Filter by risk category"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    sector: Optional[str] = Query(None, description="Filter by sector category"),
    fy: Optional[str] = Query(None, description="Filter by financial year"),
    limit: int = Query(15, ge=1, le=100, description="Max districts to return"),
    sort_by: str = Query("projects", description="Sort field: projects, risk_score, delay, critical, sanctioned"),
    db: Session = Depends(get_db)
):
    """
    Returns ranked district records with state/risk/status filters:
    - total projects
    - high-risk projects
    - critical-risk projects
    - average risk score
    - average delay days
    """
    return AnalyticsService.get_districts_analytics(
        db=db,
        state_name=state,
        district_name=district,
        risk_level=risk_level,
        status=status,
        sector=sector,
        financial_year=fy,
        limit=limit,
        sort_by=sort_by,
    )


@router.get(
    "/delays",
    response_model=DelayAnalyticsResponse,
    summary="Get delay distribution histogram and overdue delivery statistics"
)
def get_delays_analytics(
    state: Optional[str] = Query(None, description="Filter by state name"),
    district: Optional[str] = Query(None, description="Filter by district name"),
    risk_level: Optional[str] = Query(None, description="Filter by risk category"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    sector: Optional[str] = Query(None, description="Filter by sector category"),
    fy: Optional[str] = Query(None, description="Filter by financial year"),
    db: Session = Depends(get_db)
):
    """
    Returns delay analytics based on existing feature-engineering & delay detector:
    - on-time, delayed, severely delayed counts
    - average and maximum delay in days
    - delay buckets: 0, 1-30, 31-90, 91-180, 181-365, 365+ days
    - top overdue projects with delay metrics
    """
    return AnalyticsService.get_delays_analytics(
        db=db,
        state_name=state,
        district_name=district,
        risk_level=risk_level,
        status=status,
        sector=sector,
        financial_year=fy,
    )


@router.get(
    "/cost-anomalies",
    response_model=CostAnomalyAnalyticsResponse,
    summary="Get cost anomaly distribution and statistical peer comparisons"
)
def get_cost_anomalies_analytics(
    state: Optional[str] = Query(None, description="Filter by state name"),
    district: Optional[str] = Query(None, description="Filter by district name"),
    risk_level: Optional[str] = Query(None, description="Filter by risk category"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    sector: Optional[str] = Query(None, description="Filter by sector category"),
    fy: Optional[str] = Query(None, description="Filter by financial year"),
    db: Session = Depends(get_db)
):
    """
    Returns cost anomaly statistics from the Cost Anomaly Engine:
    - normal vs anomalous projects count
    - cost anomaly rate %
    - cost deviation distribution buckets (<0%, 0-25%, 25-50%, 50-100%, 100-200%, 200%+)
    - projects with largest cost deviations alongside peer median/IQR context
    """
    return AnalyticsService.get_cost_anomalies_analytics(
        db=db,
        state_name=state,
        district_name=district,
        risk_level=risk_level,
        status=status,
        sector=sector,
        financial_year=fy,
    )


@router.get(
    "/trends",
    response_model=TrendAnalyticsResponse,
    summary="Get temporal monthly/quarterly trends for risk, volume, and delays"
)
def get_temporal_trends(
    state: Optional[str] = Query(None, description="Filter by state name"),
    district: Optional[str] = Query(None, description="Filter by district name"),
    risk_level: Optional[str] = Query(None, description="Filter by risk category"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    sector: Optional[str] = Query(None, description="Filter by sector category"),
    fy: Optional[str] = Query(None, description="Filter by financial year"),
    db: Session = Depends(get_db)
):
    """
    Computes time-based trend points based on project sanction dates:
    - project volume over time
    - high-risk projects and average risk score over time
    - delayed projects and cost anomalies over time
    - sanctioned amount and expenditure trends over time
    """
    return AnalyticsService.get_temporal_trends(
        db=db,
        state_name=state,
        district_name=district,
        risk_level=risk_level,
        status=status,
        sector=sector,
        financial_year=fy,
    )


@router.get(
    "/map",
    response_model=MapAnalyticsResponse,
    summary="Get state-level geospatial choropleth data for India map visualization"
)
def get_map_analytics(
    metric: str = Query("projects", description="Metric for choropleth shading: projects, risk_score, delays, sanctioned"),
    state: Optional[str] = Query(None, description="Optional filter by single state"),
    risk_level: Optional[str] = Query(None, description="Filter by risk category"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    sector: Optional[str] = Query(None, description="Filter by sector category"),
    fy: Optional[str] = Query(None, description="Filter by financial year"),
    db: Session = Depends(get_db)
):
    """
    Returns state-level geospatial mapping data including:
    - ISO 3166-2:IN state codes
    - state project count, high-risk, critical-risk counts
    - average risk score, average delay days
    - normalized density score [0, 100] for map choropleth shading
    """
    return AnalyticsService.get_map_analytics(
        db=db,
        metric=metric,
        state_name=state,
        risk_level=risk_level,
        status=status,
        sector=sector,
        financial_year=fy,
    )


@router.get(
    "/engine/{engine_name}",
    response_model=EngineAnalyticsResponse,
    summary="Get analytics, distribution, and top flagged projects for a specific engine"
)
def get_engine_analytics(
    engine_name: str = Path(..., description="Canonical engine name (e.g. 'delay_detection', 'cost_anomaly')"),
    limit: int = Query(10, ge=1, le=50, description="Max flagged projects to return"),
    db: Session = Depends(get_db)
):
    """
    Returns summary statistics, score distribution across risk tiers,
    and top-flagged projects for the requested risk engine.
    Returns HTTP 400 if an invalid engine name is provided.
    """
    clean_engine = engine_name.strip().lower()
    if clean_engine not in ENGINE_METADATA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid engine name '{engine_name}'. Allowed engines: {sorted(list(ENGINE_METADATA.keys()))}"
        )

    from app.models.project import Project, RiskFactor
    from sqlalchemy import func

    # Aggregate metrics
    stats = (
        db.query(
            func.count(RiskFactor.factor_id),
            func.avg(RiskFactor.score),
            func.min(RiskFactor.score),
            func.max(RiskFactor.score),
            func.avg(RiskFactor.confidence),
        )
        .filter(RiskFactor.engine_name == clean_engine)
        .first()
    )

    total_proj = stats[0] or 0
    avg_score = float(stats[1] or 0.0)
    min_score = float(stats[2] or 0.0)
    max_score = float(stats[3] or 0.0)
    avg_conf = float(stats[4] or 0.0)

    # Tier distribution for this engine
    low_c = db.query(func.count(RiskFactor.factor_id)).filter(
        RiskFactor.engine_name == clean_engine, RiskFactor.score < 30
    ).scalar() or 0
    med_c = db.query(func.count(RiskFactor.factor_id)).filter(
        RiskFactor.engine_name == clean_engine, RiskFactor.score >= 30, RiskFactor.score < 60
    ).scalar() or 0
    high_c = db.query(func.count(RiskFactor.factor_id)).filter(
        RiskFactor.engine_name == clean_engine, RiskFactor.score >= 60, RiskFactor.score < 80
    ).scalar() or 0
    crit_c = db.query(func.count(RiskFactor.factor_id)).filter(
        RiskFactor.engine_name == clean_engine, RiskFactor.score >= 80
    ).scalar() or 0

    tier_dist = {"LOW": low_c, "MEDIUM": med_c, "HIGH": high_c, "CRITICAL": crit_c}

    # Top flagged projects
    top_rows = (
        db.query(RiskFactor, Project.project_title)
        .join(Project, Project.project_id == RiskFactor.project_id)
        .filter(RiskFactor.engine_name == clean_engine)
        .order_by(RiskFactor.score.desc())
        .limit(limit)
        .all()
    )

    flagged = [
        EngineFlaggedProject(
            project_id=f.project_id,
            project_title=title,
            score=float(f.score or 0.0),
            risk_level=f.risk_level or "LOW",
            reason=f.reason or "",
            confidence=float(f.confidence or 1.0),
            details=f.details or {},
        )
        for f, title in top_rows
    ]

    meta = ENGINE_METADATA[clean_engine]
    return EngineAnalyticsResponse(
        engine_name=clean_engine,
        display_name=meta["display_name"],
        description=meta["description"],
        total_projects=total_proj,
        average_score=round(avg_score, 2),
        min_score=round(min_score, 2),
        max_score=round(max_score, 2),
        average_confidence=round(avg_conf, 3),
        risk_tier_distribution=tier_dist,
        top_flagged_projects=flagged,
    )
