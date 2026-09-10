"""
backend/app/services/risk/delay_detector.py
=============================================================================
Schedule Delay Risk Detector for MPLADS Projects.
=============================================================================

Calculates calendar delay and schedule slippage metrics across project lifecycles.
Distinguishes between:
1. Completed projects (Actual vs Planned completion dates)
2. Ongoing projects (Current reference date vs Planned completion date)
3. Cancelled / Closed projects (Zero delay risk)
4. Projects with missing completion dates (Neutral score; never assigns false high risk)

Generates 0-100 score, severity (low, medium, high), and human-readable explanation.
"""

import logging
from datetime import date, datetime
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from app.models.project import Project
    from app.services.risk.base import BaseRiskDetector, RiskDetectorResult, score_to_severity
except ImportError:
    from backend.app.models.project import Project
    from backend.app.services.risk.base import BaseRiskDetector, RiskDetectorResult, score_to_severity

logger = logging.getLogger(__name__)


class DelayDetector(BaseRiskDetector):
    """
    Evaluates temporal slippage and schedule execution drag for MPLADS works.
    """
    name: str = "delay"
    version: str = "1.0.0"

    def detect(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> RiskDetectorResult:
        """
        Executes delay detection for a single project.
        """
        try:
            # 1. Fetch project record
            stmt = select(Project).where(Project.project_id == project_id)
            project = db.execute(stmt).scalar_one_or_none()

            if not project:
                return RiskDetectorResult(
                    score=0,
                    reason=f"Project '{project_id}' not found in database.",
                    severity="low",
                    details={"error": "not_found", "project_id": project_id}
                )

            # 2. Determine reference date
            ref_date = date.today()
            if context and "as_of_date" in context:
                raw_ref = context["as_of_date"]
                if isinstance(raw_ref, str):
                    try:
                        ref_date = datetime.strptime(raw_ref, "%Y-%m-%d").date()
                    except ValueError:
                        ref_date = date.today()
                elif isinstance(raw_ref, date):
                    ref_date = raw_ref

            status_clean = (project.current_status or "").strip().lower()

            # 3. Rule: Cancelled / Closed / Dropped projects
            if status_clean in {"cancelled", "closed", "dropped", "rejected"}:
                return RiskDetectorResult(
                    score=0,
                    reason=f"Project status is '{project.current_status}'; schedule delay is not applicable.",
                    severity="low",
                    details={
                        "status": project.current_status,
                        "overdue_days": 0,
                        "project_id": project_id
                    }
                )

            # 4. Dates extraction
            expected_comp = project.expected_completion_date
            actual_comp = project.actual_completion_date
            start_date = (
                project.work_order_date
                or project.sanction_date
                or project.recommendation_date
            )

            # Rule: Missing expected completion date
            if expected_comp is None:
                return RiskDetectorResult(
                    score=0,
                    reason="Planned completion date not recorded in official records; delay cannot be determined.",
                    severity="low",
                    details={
                        "status": project.current_status,
                        "expected_completion": None,
                        "overdue_days": 0,
                        "missing_dates": True
                    }
                )

            # Planned duration in days
            planned_duration = (expected_comp - start_date).days if start_date else None
            if planned_duration is not None and planned_duration <= 0:
                planned_duration = 30  # Safety fallback for zero or reverse data entry

            # 5. Rule: Completed projects
            is_completed = (actual_comp is not None) or (status_clean == "completed")
            if is_completed:
                if actual_comp is not None:
                    delay_days = (actual_comp - expected_comp).days
                    if delay_days > 0:
                        score = self._score_delay(delay_days, planned_duration)
                        severity = score_to_severity(score)
                        return RiskDetectorResult(
                            score=score,
                            reason=f"Completed project finished {delay_days} days behind schedule.",
                            severity=severity,
                            details={
                                "status": "completed",
                                "overdue_days": delay_days,
                                "planned_completion": expected_comp.isoformat(),
                                "actual_completion": actual_comp.isoformat(),
                                "planned_duration_days": planned_duration
                            }
                        )
                    else:
                        # Completed on-time or early
                        return RiskDetectorResult(
                            score=0,
                            reason=f"Completed on schedule (finished {abs(delay_days)} days early).",
                            severity="low",
                            details={
                                "status": "completed",
                                "overdue_days": 0,
                                "planned_completion": expected_comp.isoformat(),
                                "actual_completion": actual_comp.isoformat(),
                                "early_days": abs(delay_days)
                            }
                        )
                else:
                    # Completed status without explicit actual date
                    return RiskDetectorResult(
                        score=0,
                        reason="Project marked as completed; no actual completion date recorded to measure delay.",
                        severity="low",
                        details={
                            "status": "completed",
                            "overdue_days": 0,
                            "expected_completion": expected_comp.isoformat()
                        }
                    )

            # 6. Rule: Ongoing / In-flight projects
            if ref_date > expected_comp:
                overdue_days = (ref_date - expected_comp).days
                elapsed_duration = (ref_date - start_date).days if start_date else None
                delay_pct = (
                    round((overdue_days / planned_duration) * 100, 1)
                    if planned_duration and planned_duration > 0
                    else None
                )

                score = self._score_delay(overdue_days, planned_duration)
                severity = score_to_severity(score)

                reason = (
                    f"Project is {overdue_days} days overdue beyond planned completion date "
                    f"({expected_comp.isoformat()})"
                )
                if delay_pct and delay_pct > 25:
                    reason += f" (+{delay_pct:.0f}% over scheduled duration)"

                return RiskDetectorResult(
                    score=score,
                    reason=reason,
                    severity=severity,
                    details={
                        "status": project.current_status,
                        "overdue_days": overdue_days,
                        "delay_pct": delay_pct,
                        "planned_completion": expected_comp.isoformat(),
                        "planned_duration_days": planned_duration,
                        "elapsed_duration_days": elapsed_duration,
                        "as_of_date": ref_date.isoformat()
                    }
                )
            else:
                # Within schedule window
                days_remaining = (expected_comp - ref_date).days
                return RiskDetectorResult(
                    score=0,
                    reason=f"Project is currently within contractual timeline ({days_remaining} days remaining).",
                    severity="low",
                    details={
                        "status": project.current_status,
                        "overdue_days": 0,
                        "days_remaining": days_remaining,
                        "planned_completion": expected_comp.isoformat(),
                        "as_of_date": ref_date.isoformat()
                    }
                )

        except Exception as e:
            logger.error("DelayDetector error for project %s: %s", project_id, str(e), exc_info=True)
            return RiskDetectorResult(
                score=0,
                reason=f"Unable to calculate delay risk due to internal error: {str(e)}",
                severity="low",
                details={"error": str(e), "project_id": project_id}
            )

    def _score_delay(self, overdue_days: int, planned_duration: Optional[int]) -> int:
        """
        Translates overdue calendar days and schedule percentage into a 0-100 risk score.
        """
        if overdue_days <= 0:
            return 0

        # Base score on calendar days overdue
        if overdue_days <= 14:
            base = 15 + int((overdue_days / 14.0) * 15)       # 15 - 30 (low to med)
        elif overdue_days <= 45:
            base = 30 + int(((overdue_days - 14) / 31.0) * 20) # 30 - 50 (medium)
        elif overdue_days <= 90:
            base = 50 + int(((overdue_days - 45) / 45.0) * 20) # 50 - 70 (medium)
        elif overdue_days <= 180:
            base = 70 + int(((overdue_days - 90) / 90.0) * 18) # 70 - 88 (high)
        else:
            base = 88 + min(12, int(((overdue_days - 180) / 180.0) * 12)) # 88 - 100 (high)

        # Scale modifier if delay exceeds significant portion of planned duration
        if planned_duration and planned_duration > 0:
            pct_overrun = (overdue_days / planned_duration)
            if pct_overrun > 1.0:
                base = min(100, base + 10)
            elif pct_overrun > 0.5:
                base = min(100, base + 5)

        return max(0, min(100, base))
