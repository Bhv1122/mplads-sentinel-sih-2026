"""
backend/app/services/risk/fund_utilization.py
=============================================================================
Fund Utilization Risk Detector for MPLADS Projects.
=============================================================================

Monitors expenditure velocity against sanctioned allocations and released tranches.
Detects:
1. Severe Cost Overrun: Expenditure exceeds sanctioned budget ceiling.
2. Disbursement Deficit: Expenditure exceeds released funds (unbacked liabilities).
3. Fund Stagnation / Low Utilization: Unusually low absorption (<20%) on ongoing works.
4. Normal / Balanced Utilization: 70% to 100% absorption within allocation limits.

Note:
Identifies financial governance anomalies and risk flags without making accusations of fraud.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from app.models.project import Project, Financial
    from app.services.risk.base import BaseRiskDetector, RiskDetectorResult, score_to_severity
except ImportError:
    from backend.app.models.project import Project, Financial
    from backend.app.services.risk.base import BaseRiskDetector, RiskDetectorResult, score_to_severity

logger = logging.getLogger(__name__)


class FundUtilizationDetector(BaseRiskDetector):
    """
    Detects fund absorption anomalies, budget deficits, and capital allocation bottlenecks.
    """
    name: str = "fund_utilization"
    version: str = "1.0.0"

    def detect(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> RiskDetectorResult:
        """
        Calculates fund utilization risk score for a single project.
        """
        try:
            # 1. Fetch project and financial records
            stmt = (
                select(Project, Financial)
                .outerjoin(Financial, Project.project_id == Financial.project_id)
                .where(Project.project_id == project_id)
            )
            row = db.execute(stmt).first()

            if not row:
                return RiskDetectorResult(
                    score=0,
                    reason=f"Project '{project_id}' not found in database.",
                    severity="low",
                    details={"error": "not_found", "project_id": project_id}
                )

            project, financial = row

            if not financial:
                return RiskDetectorResult(
                    score=0,
                    reason="Financial accounting record not found for this project; risk cannot be evaluated.",
                    severity="low",
                    details={"project_id": project_id, "missing_financials": True}
                )

            sanctioned = float(financial.sanctioned_amount) if financial.sanctioned_amount is not None else 0.0
            released = float(financial.released_amount) if financial.released_amount is not None else 0.0
            expenditure = float(financial.expenditure_amount) if financial.expenditure_amount is not None else 0.0

            # Rule: Zero or unrecorded allocation
            if sanctioned <= 0.0:
                return RiskDetectorResult(
                    score=0,
                    reason="No sanctioned allocation recorded for project; utilization score not applicable.",
                    severity="low",
                    details={
                        "sanctioned": 0.0,
                        "released": released,
                        "expenditure": expenditure
                    }
                )

            # Ratios
            utilization_ratio = round(expenditure / sanctioned, 4)
            release_utilization = round(expenditure / released, 4) if released > 0.0 else None

            status_clean = (project.current_status or "").strip().lower()

            # -------------------------------------------------------------
            # Case 1: Cost Overrun (Expenditure > Sanctioned Amount)
            # -------------------------------------------------------------
            if expenditure > sanctioned:
                overrun_amount = round(expenditure - sanctioned, 2)
                overrun_ratio = round(expenditure / sanctioned, 4)
                overrun_pct = round((overrun_ratio - 1.0) * 100.0, 1)

                # High risk: 75 to 100
                score = 75 + min(25, int(overrun_pct * 1.5))
                severity = score_to_severity(score)

                reason = (
                    f"Reported expenditure exceeds sanctioned amount by {overrun_pct:.1f}% "
                    f"(INR {overrun_amount:,.2f} budget overrun)"
                )
                return RiskDetectorResult(
                    score=score,
                    reason=reason,
                    severity=severity,
                    details={
                        "sanctioned": sanctioned,
                        "released": released,
                        "expenditure": expenditure,
                        "overrun_amount": overrun_amount,
                        "overrun_ratio": overrun_ratio,
                        "overrun_pct": overrun_pct,
                        "utilization_ratio": utilization_ratio
                    }
                )

            # -------------------------------------------------------------
            # Case 2: Expenditure > Released Amount (Deficit / Uncovered Liability)
            # -------------------------------------------------------------
            if released > 0.0 and expenditure > (released * 1.02):  # 2% tolerance for minor rounding
                deficit_amount = round(expenditure - released, 2)
                deficit_pct = round(((expenditure / released) - 1.0) * 100.0, 1)

                score = 65 + min(25, int(deficit_pct * 1.2))
                severity = score_to_severity(score)

                reason = (
                    f"Reported expenditure exceeds released funds by INR {deficit_amount:,.2f} "
                    f"({deficit_pct:.1f}% above released tranche)"
                )
                return RiskDetectorResult(
                    score=score,
                    reason=reason,
                    severity=severity,
                    details={
                        "sanctioned": sanctioned,
                        "released": released,
                        "expenditure": expenditure,
                        "deficit_amount": deficit_amount,
                        "release_utilization": release_utilization,
                        "utilization_ratio": utilization_ratio
                    }
                )

            # -------------------------------------------------------------
            # Case 3: Completed project with incomplete utilization (< 85%)
            # -------------------------------------------------------------
            if status_clean == "completed" and utilization_ratio < 0.85:
                unspent = round(sanctioned - expenditure, 2)
                pct = round(utilization_ratio * 100.0, 1)
                score = 40 + int((0.85 - utilization_ratio) * 40)
                severity = score_to_severity(score)
                reason = (
                    f"Completed project shows only {pct:.0f}% fund utilization "
                    f"(INR {unspent:,.2f} remaining unspent without closure surrender)"
                )
                return RiskDetectorResult(
                    score=score,
                    reason=reason,
                    severity=severity,
                    details={
                        "sanctioned": sanctioned,
                        "released": released,
                        "expenditure": expenditure,
                        "utilization_ratio": utilization_ratio,
                        "unspent_balance": unspent,
                        "status": project.current_status
                    }
                )

            # -------------------------------------------------------------
            # Case 4: Low Utilization on Active Works (< 25%)
            # -------------------------------------------------------------
            if status_clean in {"in progress", "ongoing", "work commenced"} and utilization_ratio < 0.25:
                pct = round(utilization_ratio * 100.0, 1)
                # Moderate/Medium risk
                score = 45 + int((0.25 - utilization_ratio) * 100)
                severity = score_to_severity(score)
                reason = f"Only {pct:.0f}% of sanctioned funds have been utilized on active work"
                return RiskDetectorResult(
                    score=score,
                    reason=reason,
                    severity=severity,
                    details={
                        "sanctioned": sanctioned,
                        "released": released,
                        "expenditure": expenditure,
                        "utilization_ratio": utilization_ratio,
                        "status": project.current_status
                    }
                )

            # -------------------------------------------------------------
            # Case 5: Recommended / Sanctioned stage with zero utilization (Expected)
            # -------------------------------------------------------------
            if status_clean in {"recommended", "sanctioned", "tender floated"} and expenditure == 0.0:
                return RiskDetectorResult(
                    score=0,
                    reason="Pre-construction stage; zero expenditure is expected prior to work commencement.",
                    severity="low",
                    details={
                        "sanctioned": sanctioned,
                        "released": released,
                        "expenditure": 0.0,
                        "utilization_ratio": 0.0,
                        "status": project.current_status
                    }
                )

            # -------------------------------------------------------------
            # Case 6: Healthy / Normal Utilization
            # -------------------------------------------------------------
            pct = round(utilization_ratio * 100.0, 1)
            # Minor score if slightly low, otherwise 0
            if utilization_ratio >= 0.70:
                score = 0
                reason = f"Healthy fund utilization ({pct:.0f}% of sanctioned allocation absorbed)"
            else:
                score = int((0.70 - utilization_ratio) * 40)
                reason = f"Moderate fund utilization ({pct:.0f}% absorbed)"

            severity = score_to_severity(score)
            return RiskDetectorResult(
                score=score,
                reason=reason,
                severity=severity,
                details={
                    "sanctioned": sanctioned,
                    "released": released,
                    "expenditure": expenditure,
                    "utilization_ratio": utilization_ratio,
                    "release_utilization": release_utilization,
                    "status": project.current_status
                }
            )

        except Exception as e:
            logger.error("FundUtilizationDetector error for project %s: %s", project_id, str(e), exc_info=True)
            return RiskDetectorResult(
                score=0,
                reason=f"Unable to calculate fund utilization risk due to internal error: {str(e)}",
                severity="low",
                details={"error": str(e), "project_id": project_id}
            )
