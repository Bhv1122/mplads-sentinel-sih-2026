"""
backend/app/routes/agencies.py
=============================================================================
FastAPI router for agency historical pattern analysis and risk profiling.
=============================================================================
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Path, HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.project import Project, RiskScore
from app.schemas.risk_engine import (
    AgencyRiskPatternResponse,
    AgencyProjectSummary,
)
from app.services.risk.agency_pattern_engine import AgencyPatternEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agencies", tags=["Agency Risk Analytics"])
agency_pattern_engine = AgencyPatternEngine()


@router.get(
    "/{agency_id}/risk-pattern",
    response_model=AgencyRiskPatternResponse,
    summary="Get agency historical risk pattern and project performance statistics"
)
def get_agency_risk_pattern(
    agency_id: str = Path(..., description="Agency name, abbreviation, slug, or identifier (e.g. 'drda', 'District Rural Development Agency')"),
    db: Session = Depends(get_db)
):
    """
    Analyzes historical performance patterns for an implementing or executing agency:
    - total projects analyzed
    - institutional delay rate, cost anomaly rate, and progress mismatch rate
    - portfolio completion rate and mean fund utilization
    - agency risk score (0-100) and risk tier
    - associated project summary records

    Returns HTTP 404 if no projects are found for the specified agency.
    Returns HTTP 400 for empty or invalid agency identifier.
    """
    clean_query = agency_id.strip().lower()
    if not clean_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agency identifier."
        )

    # Search projects matching agency name
    # 1. Exact match (case-insensitive)
    # 2. Substring / acronym match (e.g. 'drda' in 'District Rural Development Agency (DRDA)')
    conditions = [
        func.trim(func.lower(Project.implementing_agency)) == clean_query,
        func.lower(Project.implementing_agency).contains(clean_query),
    ]

    # Check fallback agency fields if present on model
    for fallback in ("executing_agency", "department", "contractor", "authority"):
        if hasattr(Project, fallback):
            col = getattr(Project, fallback)
            conditions.append(func.trim(func.lower(col)) == clean_query)
            conditions.append(func.lower(col).contains(clean_query))

    stmt = (
        select(Project)
        .where(or_(*conditions))
        .options(
            selectinload(Project.risk_score),
            selectinload(Project.financial),
        )
    )
    raw_portfolio = db.execute(stmt).scalars().all()

    # Deduplicate projects
    seen_ids = set()
    portfolio: List[Project] = []
    for p in raw_portfolio:
        if p.project_id not in seen_ids:
            seen_ids.add(p.project_id)
            portfolio.append(p)

    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agency '{agency_id}' not found in project records."
        )

    # Resolve primary canonical agency name from matched records
    canonical_agency_name = portfolio[0].implementing_agency or agency_id

    # Compute institutional stats using AgencyPatternEngine
    eval_res = agency_pattern_engine.evaluate_agency_portfolio(portfolio, db, canonical_agency_name)
    score = eval_res["score"]
    risk_tier = eval_res["risk_level"]
    conf = eval_res["confidence"]
    reason = eval_res["reason"]
    stats = eval_res["stats"]

    # Format project summaries
    project_summaries: List[AgencyProjectSummary] = []
    for p in portfolio:
        rs = p.risk_score
        fin = p.financial
        score_val = float(rs.overall_risk_score) if rs and rs.overall_risk_score is not None else None
        level_val = rs.risk_level if rs else None
        sanc_val = float(fin.sanctioned_amount) if fin and fin.sanctioned_amount is not None else None
        exp_val = float(fin.expenditure_amount) if fin and fin.expenditure_amount is not None else None
        project_summaries.append(
            AgencyProjectSummary(
                project_id=p.project_id,
                project_title=p.project_title,
                current_status=p.current_status,
                sanctioned_amount=sanc_val,
                expenditure_amount=exp_val,
                overall_risk_score=score_val,
                risk_level=level_val,
            )
        )

    return AgencyRiskPatternResponse(
        agency_id=agency_id,
        agency_name=canonical_agency_name,
        projects_analyzed=len(portfolio),
        agency_risk_score=float(score),
        agency_risk_level=risk_tier,
        confidence=float(conf),
        reason=reason,
        details={
            "delay_rate": round(float(stats.get("delay_rate", 0.0)), 3),
            "cost_anomaly_rate": round(float(stats.get("cost_anomaly_rate", 0.0)), 3),
            "mismatch_rate": round(float(stats.get("mismatch_rate", 0.0)), 3),
            "completion_rate": round(float(stats.get("completion_rate", 0.0)), 3),
            "average_cost": round(float(stats.get("average_cost", 0.0)), 2),
            "median_cost": round(float(stats.get("median_cost", 0.0)), 2),
            "average_utilization": round(float(stats.get("average_utilization", 0.0)), 3),
            "delayed_projects_count": stats.get("delayed_count", 0),
            "cost_anomaly_count": stats.get("cost_anomaly_count", 0),
            "mismatched_count": stats.get("mismatch_count", 0),
            "completed_count": stats.get("completed_count", 0),
        },
        projects=project_summaries,
    )
