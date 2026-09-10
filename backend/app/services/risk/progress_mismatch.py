"""
backend/app/services/risk/progress_mismatch.py
=============================================================================
Progress Mismatch Risk Detector for MPLADS Projects.
=============================================================================

Compares financial progress percentage with physical progress milestone completion.
Detects bidirectional divergence:
1. Financial >> Physical: Funds drawn ahead of physical asset creation (leakage/premature billing).
2. Physical >> Financial: Asset reported completed/advanced without recorded expenditure
   (contractor liability backlog, pending bills, or delayed measurement books).
3. Balanced execution: Financial and physical progress tracking within acceptable tolerances.

Score range: 0 to 100.
Handles missing progress records and unstarted projects gracefully.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

try:
    from app.models.project import Project, Financial, Progress
    from app.services.risk.base import BaseRiskDetector, RiskDetectorResult, score_to_severity
except ImportError:
    from backend.app.models.project import Project, Financial, Progress
    from backend.app.services.risk.base import BaseRiskDetector, RiskDetectorResult, score_to_severity

logger = logging.getLogger(__name__)


class ProgressMismatchDetector(BaseRiskDetector):
    """
    Evaluates variance between reported physical delivery and financial fund drawdowns.
    """
    name: str = "progress_mismatch"
    version: str = "1.0.0"

    def detect(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> RiskDetectorResult:
        """
        Calculates progress divergence score for a given project.
        """
        try:
            # 1. Fetch project master
            proj_stmt = select(Project).where(Project.project_id == project_id)
            project = db.execute(proj_stmt).scalar_one_or_none()

            if not project:
                return RiskDetectorResult(
                    score=0,
                    reason=f"Project '{project_id}' not found in database.",
                    severity="low",
                    details={"error": "not_found", "project_id": project_id}
                )

            # 2. Fetch financial data
            fin_stmt = select(Financial).where(Financial.project_id == project_id)
            financial = db.execute(fin_stmt).scalar_one_or_none()

            # 3. Fetch latest progress record
            prog_stmt = (
                select(Progress)
                .where(Progress.project_id == project_id)
                .order_by(desc(Progress.reported_date))
                .limit(1)
            )
            progress = db.execute(prog_stmt).scalar_one_or_none()

            status_clean = (project.current_status or "").strip().lower()

            # Determine financial progress percentage
            financial_progress: Optional[float] = None
            if financial and financial.sanctioned_amount and float(financial.sanctioned_amount) > 0:
                spent = float(financial.expenditure_amount or 0.0)
                sanctioned = float(financial.sanctioned_amount)
                financial_progress = round(min(150.0, max(0.0, (spent / sanctioned) * 100.0)), 1)

            # Determine physical progress percentage
            physical_progress: Optional[float] = None
            if progress and progress.physical_progress_pct is not None:
                physical_progress = round(float(progress.physical_progress_pct), 1)
            elif status_clean == "completed":
                physical_progress = 100.0
            elif status_clean in {"recommended", "sanctioned", "tender floated"}:
                physical_progress = 0.0

            # 4. Handle Missing Data Safely
            if financial_progress is None and physical_progress is None:
                return RiskDetectorResult(
                    score=0,
                    reason="Neither financial expenditure nor physical milestone data is available for this project.",
                    severity="low",
                    details={
                        "financial_progress": None,
                        "physical_progress": None,
                        "gap": 0.0,
                        "status": project.current_status
                    }
                )

            if financial_progress is None:
                return RiskDetectorResult(
                    score=0,
                    reason="Sanctioned budget not recorded; financial progress cannot be calculated.",
                    severity="low",
                    details={
                        "financial_progress": None,
                        "physical_progress": physical_progress,
                        "gap": 0.0
                    }
                )

            if physical_progress is None:
                return RiskDetectorResult(
                    score=0,
                    reason="Physical progress milestone has not been reported yet; progress mismatch cannot be assessed.",
                    severity="low",
                    details={
                        "financial_progress": financial_progress,
                        "physical_progress": None,
                        "gap": 0.0
                    }
                )

            # 5. Calculate Gap Metrics
            # gap > 0: financial > physical (funds drawn ahead of work)
            # gap < 0: physical > financial (work ahead of funds)
            gap = round(financial_progress - physical_progress, 1)
            abs_gap = abs(gap)

            # 6. Scoring Logic
            # Normal tolerance: abs_gap <= 15% is low risk
            if abs_gap <= 15.0:
                score = max(0, int(abs_gap * 1.2))  # 0 - 18
                severity = score_to_severity(score)
                reason = (
                    f"Physical progress ({physical_progress:.0f}%) and financial progress "
                    f"({financial_progress:.0f}%) are well aligned (gap of {gap:+.1f} points)"
                )
                return RiskDetectorResult(
                    score=score,
                    reason=reason,
                    severity=severity,
                    details={
                        "financial_progress": financial_progress,
                        "physical_progress": physical_progress,
                        "gap": gap,
                        "abs_gap": abs_gap
                    }
                )

            # Direction 1: Financial ahead of Physical (High Concern)
            if gap > 15.0:
                if gap >= 40.0:
                    score = 75 + min(25, int((gap - 40.0) * 1.5))  # 75 - 100 (high)
                elif gap >= 25.0:
                    score = 50 + int(((gap - 25.0) / 15.0) * 25)   # 50 - 75 (medium/high)
                else:
                    score = 25 + int(((gap - 15.0) / 10.0) * 25)   # 25 - 50 (medium)

                severity = score_to_severity(score)
                reason = (
                    f"Financial progress ({financial_progress:.0f}%) is {gap:.0f} percentage "
                    f"points ahead of physical progress ({physical_progress:.0f}%)"
                )
                return RiskDetectorResult(
                    score=score,
                    reason=reason,
                    severity=severity,
                    details={
                        "financial_progress": financial_progress,
                        "physical_progress": physical_progress,
                        "gap": gap,
                        "abs_gap": abs_gap,
                        "direction": "financial_leading"
                    }
                )

            # Direction 2: Physical ahead of Financial (Unusual / Pending Billing)
            # e.g. physical=80%, financial=20% -> gap = -60%
            if gap < -15.0:
                if abs_gap >= 50.0:
                    score = 65 + min(25, int((abs_gap - 50.0) * 1.0)) # 65 - 90 (medium/high)
                elif abs_gap >= 30.0:
                    score = 40 + int(((abs_gap - 30.0) / 20.0) * 25)  # 40 - 65 (medium)
                else:
                    score = 20 + int(((abs_gap - 15.0) / 15.0) * 20)  # 20 - 40 (low/medium)

                severity = score_to_severity(score)
                reason = (
                    f"Physical progress ({physical_progress:.0f}%) is {abs_gap:.0f} percentage "
                    f"points ahead of recorded expenditure ({financial_progress:.0f}%) "
                    "(potential contractor payment backlog or delayed measurement entry)"
                )
                return RiskDetectorResult(
                    score=score,
                    reason=reason,
                    severity=severity,
                    details={
                        "financial_progress": financial_progress,
                        "physical_progress": physical_progress,
                        "gap": gap,
                        "abs_gap": abs_gap,
                        "direction": "physical_leading"
                    }
                )

        except Exception as e:
            logger.error("ProgressMismatchDetector error for project %s: %s", project_id, str(e), exc_info=True)
            return RiskDetectorResult(
                score=0,
                reason=f"Unable to calculate progress mismatch risk due to internal error: {str(e)}",
                severity="low",
                details={"error": str(e), "project_id": project_id}
            )
