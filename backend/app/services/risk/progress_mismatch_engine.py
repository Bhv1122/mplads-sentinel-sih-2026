"""
backend/app/services/risk/progress_mismatch_engine.py
=============================================================================
Engine 4: Financial and Physical Progress Mismatch Engine for MPLADS Projects.
=============================================================================

Implements the common BaseRiskEngine interface contract:
{
    "engine": "progress_mismatch",
    "score": 0-100,
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "reason": "...",
    "details": {
        "financial_progress": 0.0,
        "physical_progress": 0.0,
        "progress_gap": 0.0
    },
    "confidence": 0-1
}

Methodology & Rules:
1. Data Extraction:
   - Project: current_status, project_id, project_title
   - Financials: sanctioned_amount, released_amount, expenditure_amount, utilization_rate_pct
   - Progress: physical_progress_pct, financial_progress_pct, current_stage, reported_date
2. Metric Calculations:
   - physical_progress: reported on-ground physical percentage [0.0, 100.0]
     (fallback: 100.0% for "Completed", 0.0% for unstarted/pre-work stages)
   - financial_progress: reported financial progress percentage [0.0, 100.0]
     (fallback: (expenditure / sanctioned) * 100 or (expenditure / released) * 100)
   - progress_gap = financial_progress - physical_progress
3. Bidirectional Detection:
   - Direction 1: Financial >> Physical (progress_gap > tolerance)
     Funds drawn ahead of verified on-ground asset creation.
     Characterized as "significant financial/physical gap", "potential reporting
     inconsistency", and "requires verification".
   - Direction 2: Physical >> Financial (progress_gap < -tolerance)
     Works reported advanced without corresponding recorded expenditure.
     Characterized as "potential contractor payment backlog or delayed measurement
     book entry requiring verification".
   - Balanced Execution: |progress_gap| <= tolerance
     Progress tracks normally within acceptable construction variance.
4. Normalized 0–100 Risk Score with configurable thresholds:
   - tolerance: default 15.0% (Score 0–29, LOW)
   - moderate_gap: default 25.0% (Score 30–59, MEDIUM)
   - high_gap: default 40.0% (Score 60–79, HIGH)
   - critical_gap: default 60.0% (Score 80–100, CRITICAL)
5. Safe Handling:
   - Missing financial and/or physical records handled without false accusations.
   - Cancelled/dropped/rejected projects mapped to score 0 (NOT_APPLICABLE).
"""

import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

try:
    from app.config import settings
    from app.models.project import Project, Financial, Progress
    from app.schemas.risk_engine import RiskLevel, EngineResult
    from app.services.risk.engine_base import BaseRiskEngine
except ImportError:
    from backend.app.config import settings
    from backend.app.models.project import Project, Financial, Progress
    from backend.app.schemas.risk_engine import RiskLevel, EngineResult
    from backend.app.services.risk.engine_base import BaseRiskEngine

logger = logging.getLogger(__name__)


class ProgressMismatchEngine(BaseRiskEngine):
    """
    Independent risk engine evaluating bidirectional divergence between
    financial fund drawdowns and physical milestone delivery.
    """
    engine_name: str = "progress_mismatch"
    version: str = "1.0.0"

    def __init__(
        self,
        tolerance: Optional[float] = None,
        moderate_gap: Optional[float] = None,
        high_gap: Optional[float] = None,
        critical_gap: Optional[float] = None,
        low_gap: Optional[float] = None,
        medium_gap: Optional[float] = None,
    ):
        """
        Initializes the progress mismatch engine with configurable gap thresholds.
        Supports both tolerance/moderate_gap and low_gap/medium_gap naming conventions.
        """
        thresholds = self.get_engine_thresholds()
        eff_tol = tolerance if tolerance is not None else low_gap
        eff_mod = moderate_gap if moderate_gap is not None else medium_gap

        raw_tol = eff_tol if eff_tol is not None else float(thresholds.get("tolerance", thresholds.get("low_gap", 15.0)))
        raw_mod = eff_mod if eff_mod is not None else float(thresholds.get("moderate_gap", thresholds.get("medium_gap", 25.0)))
        raw_high = high_gap if high_gap is not None else float(thresholds.get("high_gap", 40.0))
        raw_crit = critical_gap if critical_gap is not None else float(thresholds.get("critical_gap", 60.0))

        # Enforce threshold ordering safety
        self.tolerance, self.moderate_gap, self.high_gap, self.critical_gap = self._validate_thresholds(
            raw_tol, raw_mod, raw_high, raw_crit
        )
        self.low_gap = self.tolerance
        self.medium_gap = self.moderate_gap

    @classmethod
    def _validate_thresholds(
        cls,
        tol: float,
        mod: float,
        high: float,
        crit: float,
    ) -> Tuple[float, float, float, float]:
        """Ensures thresholds are strictly positive and monotonically increasing."""
        v_tol = max(1.0, float(tol))
        v_mod = max(v_tol + 1.0, float(mod))
        v_high = max(v_mod + 1.0, float(high))
        v_crit = max(v_high + 1.0, float(crit))
        return v_tol, v_mod, v_high, v_crit

    # -------------------------------------------------------------------------
    # Public Evaluation Interface
    # -------------------------------------------------------------------------

    def evaluate(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> EngineResult:
        """
        Evaluates project financial and physical progress alignment.
        """
        try:
            # 1. Resolve runtime thresholds
            tolerance = self.tolerance
            moderate_gap = self.moderate_gap
            high_gap = self.high_gap
            critical_gap = self.critical_gap
            if context:
                raw_tol = context.get("tolerance", context.get("low_gap", tolerance))
                raw_mod = context.get("moderate_gap", context.get("medium_gap", moderate_gap))
                raw_high = context.get("high_gap", high_gap)
                raw_crit = context.get("critical_gap", critical_gap)
                tolerance, moderate_gap, high_gap, critical_gap = self._validate_thresholds(
                    float(raw_tol), float(raw_mod), float(raw_high), float(raw_crit)
                )

            # 2. Fetch project master record
            proj_stmt = select(Project).where(Project.project_id == project_id)
            project = db.execute(proj_stmt).scalar_one_or_none()

            if not project:
                return self.build_result(
                    score=0,
                    reason=f"Project '{project_id}' not found in database.",
                    details={
                        "financial_progress": 0.0,
                        "physical_progress": 0.0,
                        "progress_gap": 0.0,
                        "status": "not_found",
                        "error": "not_found",
                        "project_id": project_id,
                    },
                    confidence=0.0
                )

            status_raw = project.current_status or "Unknown"
            status_clean = status_raw.strip().lower()

            # Rule: Cancelled / Dropped / Rejected projects
            if status_clean in {"cancelled", "dropped", "rejected"}:
                return self.build_result(
                    score=0,
                    reason=f"Project status is '{status_raw}'; progress mismatch risk is not applicable.",
                    details={
                        "financial_progress": 0.0,
                        "physical_progress": 0.0,
                        "progress_gap": 0.0,
                        "status": status_clean,
                        "completion_status": "NOT_APPLICABLE",
                        "direction": "not_applicable",
                        "project_id": project_id,
                    },
                    confidence=1.0
                )

            # 3. Fetch financial and progress records
            fin_stmt = select(Financial).where(Financial.project_id == project_id)
            financial = db.execute(fin_stmt).scalar_one_or_none()

            prog_stmt = (
                select(Progress)
                .where(Progress.project_id == project_id)
                .order_by(desc(Progress.reported_date), desc(Progress.progress_id))
                .limit(1)
            )
            progress = db.execute(prog_stmt).scalar_one_or_none()

            # 4. Extract and calculate progress percentages
            fin_val, phy_val, missing_type = self._extract_progress_values(
                project=project,
                financial=financial,
                progress=progress
            )

            # 5. Handle missing values
            if fin_val is None and phy_val is None:
                return self.build_result(
                    score=0,
                    reason="Neither financial expenditure nor physical milestone data is available for this project; requires verification.",
                    details={
                        "financial_progress": 0.0,
                        "physical_progress": 0.0,
                        "progress_gap": 0.0,
                        "status": status_clean,
                        "direction": "missing_data",
                        "missing_data": True,
                        "missing_type": "both",
                        "project_id": project_id,
                    },
                    confidence=0.0
                )

            if fin_val is None:
                return self.build_result(
                    score=0,
                    reason="Financial expenditure records are not documented; financial-physical gap cannot be determined.",
                    details={
                        "financial_progress": 0.0,
                        "physical_progress": round(phy_val, 1) if phy_val is not None else 0.0,
                        "progress_gap": 0.0,
                        "status": status_clean,
                        "direction": "missing_financial",
                        "missing_data": True,
                        "missing_type": "financial",
                        "project_id": project_id,
                    },
                    confidence=0.30
                )

            if phy_val is None:
                return self.build_result(
                    score=0,
                    reason="Physical progress milestones have not been reported yet; progress mismatch cannot be assessed.",
                    details={
                        "financial_progress": round(fin_val, 1) if fin_val is not None else 0.0,
                        "physical_progress": 0.0,
                        "progress_gap": 0.0,
                        "status": status_clean,
                        "direction": "missing_physical",
                        "missing_data": True,
                        "missing_type": "physical",
                        "project_id": project_id,
                    },
                    confidence=0.30
                )

            # 6. Calculate Progress Gap: financial_progress - physical_progress
            financial_progress = round(float(fin_val), 1)
            physical_progress = round(float(phy_val), 1)
            progress_gap = round(financial_progress - physical_progress, 1)
            abs_gap = abs(progress_gap)

            # 7. Directional Score & Explanation
            score, direction, reason = self._score_and_explain(
                financial_progress=financial_progress,
                physical_progress=physical_progress,
                progress_gap=progress_gap,
                abs_gap=abs_gap,
                status_raw=status_raw,
                tolerance=tolerance,
                moderate_gap=moderate_gap,
                high_gap=high_gap,
                critical_gap=critical_gap,
            )

            # 8. Diagnostic Confidence
            confidence = self._calculate_confidence(
                financial=financial,
                progress=progress,
                status_clean=status_clean
            )

            details = {
                "financial_progress": financial_progress,
                "physical_progress": physical_progress,
                "progress_gap": progress_gap,
                "direction": direction,
                "sanctioned_amount": float(financial.sanctioned_amount) if (financial and financial.sanctioned_amount is not None) else None,
                "released_amount": float(financial.released_amount) if (financial and financial.released_amount is not None) else None,
                "expenditure_amount": float(financial.expenditure_amount) if (financial and financial.expenditure_amount is not None) else None,
                "expenditure_ratio_sanctioned": (
                    round((float(financial.expenditure_amount) / float(financial.sanctioned_amount)) * 100.0, 1)
                    if (financial and financial.sanctioned_amount and financial.expenditure_amount is not None and float(financial.sanctioned_amount) > 0)
                    else None
                ),
                "expenditure_ratio_released": (
                    round((float(financial.expenditure_amount) / float(financial.released_amount)) * 100.0, 1)
                    if (financial and financial.released_amount and financial.expenditure_amount is not None and float(financial.released_amount) > 0)
                    else None
                ),
                "utilization_rate_pct": (
                    float(financial.utilization_rate_pct)
                    if (financial and financial.utilization_rate_pct is not None)
                    else None
                ),
                "current_status": status_raw,
                "current_stage": progress.current_stage if progress else None,
                "tolerance": tolerance,
                "project_id": project_id,
            }

            stage_str = progress.current_stage if progress and progress.current_stage else "Unrecorded"
            evidence_items = [
                {
                    "metric": "financial_progress",
                    "label": "Financial Disbursement",
                    "value": financial_progress,
                    "formatted": f"{financial_progress:.1f}%",
                },
                {
                    "metric": "physical_progress",
                    "label": "Physical Completion",
                    "value": physical_progress,
                    "formatted": f"{physical_progress:.1f}%",
                },
                {
                    "metric": "progress_gap",
                    "label": "Progress Gap (Financial - Physical)",
                    "value": progress_gap,
                    "formatted": f"{progress_gap:+.1f}%",
                },
                {
                    "metric": "tolerance_threshold",
                    "label": "Tolerance Threshold",
                    "value": tolerance,
                    "formatted": f"±{tolerance:.1f}%",
                },
            ]

            return self.build_result(
                score=score,
                reason=reason,
                details=details,
                confidence=confidence,
                triggered=(score >= 30),
                threshold=f"Disbursement leads physical completion by >= {moderate_gap:.1f}% (Tolerance: ±{tolerance:.1f}%)",
                actual_value=f"Financial {financial_progress:.1f}% vs Physical {physical_progress:.1f}% (Gap: {progress_gap:+.1f}%)",
                expected_value=f"Physical progress commensurate with disbursement (balanced ±{tolerance:.1f}%)",
                reference_value=f"Current stage: '{stage_str}' (Status: '{status_raw}')",
                evidence=evidence_items,
                metadata=details,
            )

        except Exception as e:
            logger.error(
                "ProgressMismatchEngine failed for project '%s': %s",
                project_id, str(e), exc_info=True
            )
            return self.build_result(
                score=0,
                reason=f"Progress mismatch detection encountered runtime error: {str(e)}",
                details={
                    "financial_progress": 0.0,
                    "physical_progress": 0.0,
                    "progress_gap": 0.0,
                    "status": "error",
                    "error": str(e),
                    "project_id": project_id,
                },
                confidence=0.0
            )

    # -------------------------------------------------------------------------
    # Helper: Formatting
    # -------------------------------------------------------------------------

    @staticmethod
    def _fmt_pct(val: float) -> str:
        """Formats a percentage cleanly without awkward trailing .0 when whole."""
        rounded = round(val, 1)
        if rounded == int(rounded):
            return f"{int(rounded)}%"
        return f"{rounded:.1f}%"

    # -------------------------------------------------------------------------
    # Helper: Progress Values Extraction
    # -------------------------------------------------------------------------

    @classmethod
    def _extract_progress_values(
        cls,
        project: Project,
        financial: Optional[Financial],
        progress: Optional[Progress],
    ) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Extracts financial and physical progress values safely using primary
        reported telemetry with rigorous accounting fallbacks.
        Returns: (financial_progress, physical_progress, missing_type)
        """
        status_clean = (project.current_status or "").strip().lower()

        # --- A. Physical Progress ---
        physical_progress: Optional[float] = None
        if progress and progress.physical_progress_pct is not None:
            physical_progress = min(100.0, max(0.0, float(progress.physical_progress_pct)))
        elif status_clean in {"completed", "physically complete"}:
            physical_progress = 100.0
        elif status_clean in {"recommended", "sanctioned", "tender floated"}:
            physical_progress = 0.0

        # --- B. Financial Progress ---
        financial_progress: Optional[float] = None
        if progress and progress.financial_progress_pct is not None:
            financial_progress = min(100.0, max(0.0, float(progress.financial_progress_pct)))
        elif financial:
            spent = float(financial.expenditure_amount or 0.0) if financial.expenditure_amount is not None else None
            sanctioned = float(financial.sanctioned_amount) if (financial.sanctioned_amount and float(financial.sanctioned_amount) > 0) else None
            released = float(financial.released_amount) if (financial.released_amount and float(financial.released_amount) > 0) else None

            if spent is not None and sanctioned is not None:
                financial_progress = min(100.0, max(0.0, (spent / sanctioned) * 100.0))
            elif spent is not None and released is not None:
                financial_progress = min(100.0, max(0.0, (spent / released) * 100.0))
            elif financial.utilization_rate_pct is not None:
                financial_progress = min(100.0, max(0.0, float(financial.utilization_rate_pct)))

        missing_type = None
        if financial_progress is None and physical_progress is None:
            missing_type = "both"
        elif financial_progress is None:
            missing_type = "financial"
        elif physical_progress is None:
            missing_type = "physical"

        return financial_progress, physical_progress, missing_type

    # -------------------------------------------------------------------------
    # Helper: Bidirectional Scoring & Reason Generation
    # -------------------------------------------------------------------------

    def _score_and_explain(
        self,
        financial_progress: float,
        physical_progress: float,
        progress_gap: float,
        abs_gap: float,
        status_raw: str,
        tolerance: float,
        moderate_gap: float,
        high_gap: float,
        critical_gap: float,
    ) -> Tuple[int, str, str]:
        """
        Calculates normalized 0–100 risk score and non-accusatory governance explanation.
        Returns: (score, direction, reason)
        """
        fin_str = self._fmt_pct(financial_progress)
        phy_str = self._fmt_pct(physical_progress)

        # Case 0: Balanced Progress (|progress_gap| <= tolerance)
        if abs_gap <= tolerance:
            direction = "balanced"
            score = int(round((abs_gap / float(tolerance)) * 29.0))
            score = max(0, min(29, score))

            if abs_gap == 0.0:
                reason = (
                    f"Physical delivery ({phy_str}) and financial expenditure "
                    f"({fin_str}) are perfectly aligned (gap of 0.0 points)."
                )
            else:
                reason = (
                    f"Physical delivery ({phy_str}) and financial expenditure "
                    f"({fin_str}) are well aligned within governance tolerance "
                    f"(gap of {progress_gap:+.1f} points)."
                )
            return score, direction, reason

        # Case 1: Financial Leads Physical (progress_gap > tolerance)
        if progress_gap > tolerance:
            direction = "financial_leading"

            # Tier 2: Moderate financial lead (tolerance to moderate_gap) -> Score 30 to 59 (MEDIUM)
            if progress_gap <= moderate_gap:
                range_gap = max(1.0, moderate_gap - tolerance)
                raw_score = 30.0 + ((progress_gap - tolerance) / range_gap) * 29.0
            # Tier 3: High financial lead (moderate_gap to high_gap) -> Score 60 to 79 (HIGH)
            elif progress_gap <= high_gap:
                range_gap = max(1.0, high_gap - moderate_gap)
                raw_score = 60.0 + ((progress_gap - moderate_gap) / range_gap) * 19.0
            # Tier 4: Critical financial lead (> high_gap) -> Score 80 to 100 (CRITICAL)
            else:
                range_gap = max(1.0, critical_gap - high_gap)
                raw_score = 80.0 + ((progress_gap - high_gap) / range_gap) * 20.0

            score = int(round(max(30.0, min(100.0, raw_score))))

            reason = (
                f"Significant financial/physical gap: recorded financial progress ({fin_str}) "
                f"leads verified physical progress ({phy_str}) by +{progress_gap:.1f} percentage points. "
                "Potential reporting inconsistency or premature drawdown; requires verification."
            )
            return score, direction, reason

        # Case 2: Physical Leads Financial (progress_gap < -tolerance)
        direction = "physical_leading"
        # Tier 2: Moderate physical lead (tolerance to moderate_gap + 5) -> Score 30 to 49 (MEDIUM)
        lead_band_1 = moderate_gap + 5.0
        lead_band_2 = high_gap + 10.0

        if abs_gap <= lead_band_1:
            range_gap = max(1.0, lead_band_1 - tolerance)
            raw_score = 30.0 + ((abs_gap - tolerance) / range_gap) * 19.0
        # Tier 3: High physical lead (lead_band_1 to lead_band_2) -> Score 50 to 69 (MEDIUM/HIGH)
        elif abs_gap <= lead_band_2:
            range_gap = max(1.0, lead_band_2 - lead_band_1)
            raw_score = 50.0 + ((abs_gap - lead_band_1) / range_gap) * 19.0
        # Tier 4: Severe physical lead (> lead_band_2) -> Score 70 to 85 (HIGH)
        else:
            range_gap = max(1.0, critical_gap - lead_band_2)
            raw_score = 70.0 + ((abs_gap - lead_band_2) / range_gap) * 15.0

        score = int(round(max(30.0, min(85.0, raw_score))))

        reason = (
            f"Significant financial/physical gap: physical progress ({phy_str}) "
            f"is reported {abs_gap:.1f} percentage points ahead of recorded expenditure ({fin_str}). "
            "Potential contractor payment backlog or delayed measurement entry; requires verification."
        )
        return score, direction, reason

    # -------------------------------------------------------------------------
    # Helper: Diagnostic Confidence Calculation
    # -------------------------------------------------------------------------

    @classmethod
    def _calculate_confidence(
        cls,
        financial: Optional[Financial],
        progress: Optional[Progress],
        status_clean: str,
    ) -> float:
        """
        Calculates diagnostic confidence based on signal availability and quality.
        """
        if not financial and not progress:
            return 0.0

        # Full telemetry available
        if financial and progress:
            has_spent = financial.expenditure_amount is not None
            has_sanc = financial.sanctioned_amount is not None
            has_phy = progress.physical_progress_pct is not None
            has_fin = progress.financial_progress_pct is not None

            if has_spent and has_sanc and has_phy and has_fin:
                return 0.95
            elif (has_spent or has_fin) and has_phy:
                return 0.90
            return 0.80

        # One record available with status completion context
        if status_clean in {"completed", "physically complete"} and financial:
            return 0.85
        if progress and progress.physical_progress_pct is not None:
            return 0.60
        if financial and financial.expenditure_amount is not None:
            return 0.60

        return 0.40
