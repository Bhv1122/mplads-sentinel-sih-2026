"""
backend/app/services/risk/delay_detection_engine.py
=============================================================================
Engine 3: Delay Detection Engine for MPLADS Projects.
=============================================================================

Implements the common BaseRiskEngine interface contract:
{
    "engine": "delay_detection",
    "score": 0-100,
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "reason": "...",
    "details": {
        "overdue_days": 0,
        "delay_percentage": 0,
        "status": "..."
    },
    "confidence": 0-1
}

Methodology & Rules:
1. Lifecycle Dates Extraction:
   - Start Date: work_order_date -> sanction_date -> recommendation_date
   - Target Completion Date: expected_completion_date
   - Actual Completion Date: actual_completion_date
   - Status / Reference Date: as_of_date from context (defaults to date.today())
2. Completed Projects:
   - Compares expected vs actual completion dates.
   - If actual <= expected: 0 overdue days, score 0, LOW risk ("Completed on schedule").
   - If actual > expected: overdue_days = (actual - expected).days.
3. Ongoing / In-Progress Projects:
   - Compares current/reference date vs expected completion date.
   - If ref_date <= expected: project is strictly within contractual timeline.
     Does NOT flag an ongoing project as delayed if expected completion has not passed!
     overdue_days = 0, score 0, LOW risk.
   - If ref_date > expected: overdue_days = (ref_date - expected).days.
4. Duration & Overrun Metrics:
   - planned_duration = (expected_completion_date - start_date).days
   - actual_duration = (actual_completion_date - start_date).days if completed
     else (ref_date - start_date).days (elapsed duration)
   - delay_percentage = (overdue_days / planned_duration) * 100 (if planned_duration > 0) else 0.0
5. Configurable Thresholds:
   - low_days: default 30 (score 15–29, LOW)
   - medium_days: default 90 (score 30–59, MEDIUM)
   - high_days: default 180 (score 60–79, HIGH)
   - critical_days: default 365 (score 80–100, CRITICAL)
6. Safe Handling:
   - Missing expected dates, reverse/invalid dates, cancelled status.
"""

import logging
from datetime import date, datetime, timezone
import zoneinfo
from typing import Dict, Any, Optional, Tuple, Union
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from app.config import settings
    from app.models.project import Project
    from app.schemas.risk_engine import RiskLevel, EngineResult
    from app.services.risk.engine_base import BaseRiskEngine
except ImportError:
    from backend.app.config import settings
    from backend.app.models.project import Project
    from backend.app.schemas.risk_engine import RiskLevel, EngineResult
    from backend.app.services.risk.engine_base import BaseRiskEngine

logger = logging.getLogger(__name__)

# Primary timezone for MPLADS administration (Indian Standard Time)
DEFAULT_TIMEZONE = "Asia/Kolkata"


def parse_date_safe(
    val: Any,
    default: Optional[date] = None,
    tz_name: str = DEFAULT_TIMEZONE,
) -> Optional[date]:
    """
    Robust date parser that handles:
    - datetime.date instances
    - datetime.datetime instances (naive and timezone-aware converted to Indian Standard Time)
    - ISO-8601 strings (with/without 'T', 'Z', offsets, fractions)
    - Standard Indian/International formats (DD/MM/YYYY, DD-MM-YYYY, YYYY/MM/DD, DD-Mon-YYYY)
    - Pandas Timestamp, NumPy datetime64
    - Null/empty/invalid values returning default without raising exceptions
    """
    if val is None or val == "":
        return default

    # 1. Pure date object (and not datetime subclass)
    if isinstance(val, date) and not isinstance(val, datetime):
        return val

    # 2. Datetime object (naive or timezone-aware)
    if isinstance(val, datetime):
        if val.tzinfo is not None:
            try:
                tz = zoneinfo.ZoneInfo(tz_name)
                return val.astimezone(tz).date()
            except Exception:
                return val.date()
        return val.date()

    # 3. Pandas Timestamp / NumPy datetime64 / objects with to_pydatetime or date method
    if hasattr(val, "to_pydatetime"):
        try:
            pydt = val.to_pydatetime()
            return parse_date_safe(pydt, default=default, tz_name=tz_name)
        except Exception:
            pass

    if hasattr(val, "date") and callable(getattr(val, "date")):
        try:
            res_date = val.date()
            if isinstance(res_date, date):
                return res_date
        except Exception:
            pass

    # 4. String parsing
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned or cleaned.lower() in {"none", "null", "nat", "nan", "n/a", "-", "undefined"}:
            return default

        # Try ISO format (handles '2024-07-10', '2024-07-10T12:00:00', '2024-07-10T12:00:00Z', offsets)
        try:
            iso_str = cleaned.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is not None:
                try:
                    tz = zoneinfo.ZoneInfo(tz_name)
                    return dt.astimezone(tz).date()
                except Exception:
                    return dt.date()
            return dt.date()
        except (ValueError, TypeError):
            pass

        # Try dateutil parser if available
        try:
            from dateutil import parser as dt_parser
            dt = dt_parser.parse(cleaned)
            if dt.tzinfo is not None:
                try:
                    tz = zoneinfo.ZoneInfo(tz_name)
                    return dt.astimezone(tz).date()
                except Exception:
                    return dt.date()
            return dt.date()
        except Exception:
            pass

        # Explicit fallback formats common in Indian records
        common_formats = (
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%d-%b-%Y",
            "%d-%B-%Y",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        )
        for fmt in common_formats:
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue

    return default


class DelayDetectionEngine(BaseRiskEngine):
    """
    Independent risk engine for calculating schedule slippage, overdue duration,
    and completion timeliness for MPLADS projects.
    """
    engine_name: str = "delay_detection"
    version: str = "1.0.0"

    def __init__(
        self,
        low_days: Optional[int] = None,
        medium_days: Optional[int] = None,
        high_days: Optional[int] = None,
        critical_days: Optional[int] = None,
    ):
        """
        Initializes the delay detection engine with configurable thresholds.
        """
        thresholds = self.get_engine_thresholds()
        raw_low = low_days if low_days is not None else int(thresholds.get("low_days", 30))
        raw_med = medium_days if medium_days is not None else int(thresholds.get("medium_days", 90))
        raw_high = high_days if high_days is not None else int(thresholds.get("high_days", 180))
        raw_crit = critical_days if critical_days is not None else int(thresholds.get("critical_days", 365))

        # Enforce threshold ordering safety
        self.low_days, self.medium_days, self.high_days, self.critical_days = self._validate_thresholds(
            raw_low, raw_med, raw_high, raw_crit
        )

    @classmethod
    def _validate_thresholds(
        cls,
        low: int,
        med: int,
        high: int,
        crit: int,
    ) -> Tuple[int, int, int, int]:
        """Ensures thresholds are strictly positive and monotonically increasing."""
        v_low = max(1, low)
        v_med = max(v_low + 1, med)
        v_high = max(v_med + 1, high)
        v_crit = max(v_high + 1, crit)
        return v_low, v_med, v_high, v_crit

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
        Evaluates project timeline and returns standardized EngineResult.
        """
        try:
            # Runtime context threshold overrides if provided
            low_days = self.low_days
            medium_days = self.medium_days
            high_days = self.high_days
            critical_days = self.critical_days
            if context:
                raw_low = int(context["low_days"]) if "low_days" in context else low_days
                raw_med = int(context["medium_days"]) if "medium_days" in context else medium_days
                raw_high = int(context["high_days"]) if "high_days" in context else high_days
                raw_crit = int(context["critical_days"]) if "critical_days" in context else critical_days
                low_days, medium_days, high_days, critical_days = self._validate_thresholds(
                    raw_low, raw_med, raw_high, raw_crit
                )

            # 1. Fetch project record
            stmt = select(Project).where(Project.project_id == project_id)
            project = db.execute(stmt).scalar_one_or_none()

            if not project:
                return self.build_result(
                    score=0,
                    reason=f"Project '{project_id}' not found in database.",
                    details={
                        "overdue_days": 0,
                        "delay_percentage": 0,
                        "status": "not_found",
                        "error": "not_found",
                        "project_id": project_id,
                    },
                    confidence=0.0
                )

            # 2. Determine reference/status date
            ref_date = self._parse_reference_date(context)
            status_raw = project.current_status or "Unknown"
            status_clean = status_raw.strip().lower()

            # 3. Dates Extraction & Validation
            dates = self._extract_lifecycle_dates(project)
            start_date = dates["start_date"]
            sanc_date = dates["sanction_date"]
            wo_date = dates["work_order_date"]
            expected_comp = dates["expected_completion_date"]
            actual_comp = dates["actual_completion_date"]

            # Rule: Cancelled / Dropped projects
            if status_clean in {"cancelled", "dropped", "rejected"}:
                return self.build_result(
                    score=0,
                    reason=f"Project status is '{status_raw}'; schedule delay risk is not applicable.",
                    details={
                        "overdue_days": 0,
                        "delay_percentage": 0,
                        "status": status_clean,
                        "completion_status": "NOT_APPLICABLE",
                        "planned_duration": None,
                        "actual_duration": None,
                        "project_id": project_id,
                    },
                    confidence=1.0
                )

            # Rule: Closed projects without actual completion date
            if status_clean == "closed" and actual_comp is None:
                return self.build_result(
                    score=0,
                    reason=f"Project status is '{status_raw}'; closed without recorded completion date.",
                    details={
                        "overdue_days": 0,
                        "delay_percentage": 0,
                        "status": status_clean,
                        "completion_status": "NOT_APPLICABLE",
                        "planned_duration": None,
                        "actual_duration": None,
                        "project_id": project_id,
                    },
                    confidence=1.0
                )

            # Handle missing expected completion date
            if expected_comp is None:
                return self.build_result(
                    score=0,
                    reason="Planned completion date is not recorded in official records; delay cannot be determined.",
                    details={
                        "overdue_days": 0,
                        "delay_percentage": 0,
                        "status": status_clean,
                        "completion_status": "MISSING_DATES",
                        "missing_dates": True,
                        "planned_duration": None,
                        "actual_duration": None,
                        "project_id": project_id,
                    },
                    confidence=0.0
                )

            # Determine whether completed
            is_completed = (actual_comp is not None) or (status_clean in {"completed", "physically complete", "closed"})

            # Calculate planned and actual/elapsed duration
            planned_duration, actual_duration, is_invalid_timeline = self._calculate_durations(
                start_date=start_date,
                expected_comp=expected_comp,
                actual_comp=actual_comp,
                ref_date=ref_date,
                is_completed=is_completed,
            )

            # 4. Core Delay Evaluation: Completed vs Ongoing
            if is_completed:
                if actual_comp is not None:
                    # Compare actual vs expected completion dates
                    raw_delay = (actual_comp - expected_comp).days
                    overdue_days = max(0, raw_delay)
                    early_days = max(0, -raw_delay)

                    delay_pct = (
                        round((overdue_days / planned_duration) * 100, 1)
                        if (planned_duration and planned_duration > 0 and overdue_days > 0)
                        else 0.0
                    )

                    if overdue_days > 0:
                        score = self._score_delay(
                            overdue_days=overdue_days,
                            planned_duration=planned_duration,
                            low_days=low_days,
                            medium_days=medium_days,
                            high_days=high_days,
                            critical_days=critical_days,
                        )
                        completion_status = "COMPLETED_LATE"
                        reason = (
                            f"Completed project finished {overdue_days} days behind scheduled completion date "
                            f"({expected_comp.isoformat()}). Actual completion: {actual_comp.isoformat()}."
                        )
                        if delay_pct > 10.0:
                            reason += f" (+{delay_pct:.0f}% schedule overrun)"
                    else:
                        score = 0
                        completion_status = "COMPLETED_ON_TIME"
                        if early_days > 0:
                            reason = f"Completed on schedule ({early_days} days ahead of expected completion date)."
                        else:
                            reason = "Completed exactly on schedule on the expected completion date."

                    confidence = self._compute_confidence(dates=dates, is_completed=True)

                    details = {
                        "overdue_days": overdue_days,
                        "delay_percentage": delay_pct,
                        "status": "completed",
                        "completion_status": completion_status,
                        "planned_duration": planned_duration,
                        "actual_duration": actual_duration,
                        "expected_completion_date": expected_comp.isoformat(),
                        "actual_completion_date": actual_comp.isoformat(),
                        "start_date": start_date.isoformat() if start_date else None,
                        "sanction_date": sanc_date.isoformat() if sanc_date else None,
                        "work_order_date": wo_date.isoformat() if wo_date else None,
                        "early_days": early_days,
                        "invalid_timeline": is_invalid_timeline,
                        "project_id": project_id,
                    }
                    overdue_val = max(0, (actual_comp - expected_comp).days)
                    delay_pct_val = (
                        round((overdue_val / planned_duration) * 100, 1)
                        if (planned_duration and planned_duration > 0)
                        else 0.0
                    )
                    evidence_items = [
                        {
                            "metric": "planned_completion_date",
                            "label": "Planned Completion Date",
                            "value": expected_comp.isoformat(),
                            "formatted": expected_comp.isoformat(),
                        },
                        {
                            "metric": "actual_current_date",
                            "label": "Actual Completion Date",
                            "value": actual_comp.isoformat(),
                            "formatted": actual_comp.isoformat(),
                        },
                        {
                            "metric": "delay_days",
                            "label": "Delay Days",
                            "value": overdue_val,
                            "formatted": f"{overdue_val} days",
                        },
                        {
                            "metric": "delay_percentage",
                            "label": "Schedule Slippage",
                            "value": delay_pct_val,
                            "formatted": f"{delay_pct_val:.1f}%",
                        },
                    ]
                    return self.build_result(
                        score=score,
                        reason=reason,
                        details=details,
                        confidence=confidence,
                        triggered=(score >= 30),
                        threshold=f"> {low_days} days overdue or > 15% schedule slippage",
                        actual_value=f"{overdue_val} days overdue (+{delay_pct_val:.1f}% slippage)",
                        expected_value=f"Planned completion: {expected_comp.isoformat()} (Planned duration: {planned_duration} days)",
                        reference_value=f"Completed on: {actual_comp.isoformat()}",
                        evidence=evidence_items,
                        metadata=details,
                    )
                else:
                    # Marked as completed but missing actual_completion_date
                    confidence = 0.50
                    details = {
                        "overdue_days": 0,
                        "delay_percentage": 0,
                        "status": "completed",
                        "completion_status": "COMPLETED_UNRECORDED_DATE",
                        "planned_duration": planned_duration,
                        "actual_duration": None,
                        "expected_completion_date": expected_comp.isoformat(),
                        "actual_completion_date": None,
                        "start_date": start_date.isoformat() if start_date else None,
                        "sanction_date": sanc_date.isoformat() if sanc_date else None,
                        "work_order_date": wo_date.isoformat() if wo_date else None,
                        "project_id": project_id,
                    }
                    return self.build_result(
                        score=0,
                        reason="Project is recorded as completed; actual completion date is not documented to verify slippage.",
                        details=details,
                        confidence=confidence,
                        triggered=False,
                        threshold=f"> {low_days} days overdue",
                        actual_value="Completed without documented completion date",
                        expected_value=f"Planned completion: {expected_comp.isoformat()}",
                        reference_value=None,
                        evidence=[],
                        metadata=details,
                    )

            # Ongoing / In-Progress Projects
            # Compare current reference date against expected completion date
            if ref_date > expected_comp:
                # Overdue ongoing project
                overdue_days = (ref_date - expected_comp).days
                delay_pct = (
                    round((overdue_days / planned_duration) * 100, 1)
                    if (planned_duration and planned_duration > 0)
                    else 0.0
                )
                score = self._score_delay(
                    overdue_days=overdue_days,
                    planned_duration=planned_duration,
                    low_days=low_days,
                    medium_days=medium_days,
                    high_days=high_days,
                    critical_days=critical_days,
                )
                completion_status = "ONGOING_OVERDUE"
                reason = (
                    f"Ongoing project is {overdue_days} days overdue beyond planned completion date "
                    f"({expected_comp.isoformat()} as of {ref_date.isoformat()})."
                )
                if delay_pct > 15.0:
                    reason += f" Schedule overrun: +{delay_pct:.0f}%."

                confidence = self._compute_confidence(dates=dates, is_completed=False)

                details = {
                    "overdue_days": overdue_days,
                    "delay_percentage": delay_pct,
                    "status": status_clean,
                    "completion_status": completion_status,
                    "planned_duration": planned_duration,
                    "actual_duration": actual_duration,
                    "expected_completion_date": expected_comp.isoformat(),
                    "actual_completion_date": None,
                    "start_date": start_date.isoformat() if start_date else None,
                    "sanction_date": sanc_date.isoformat() if sanc_date else None,
                    "work_order_date": wo_date.isoformat() if wo_date else None,
                    "as_of_date": ref_date.isoformat(),
                    "invalid_timeline": is_invalid_timeline,
                    "project_id": project_id,
                }
                evidence_items = [
                    {
                        "metric": "planned_completion_date",
                        "label": "Planned Completion Date",
                        "value": expected_comp.isoformat(),
                        "formatted": expected_comp.isoformat(),
                    },
                    {
                        "metric": "actual_current_date",
                        "label": "Evaluation Reference Date",
                        "value": ref_date.isoformat(),
                        "formatted": ref_date.isoformat(),
                    },
                    {
                        "metric": "delay_days",
                        "label": "Delay Days",
                        "value": overdue_days,
                        "formatted": f"{overdue_days} days",
                    },
                    {
                        "metric": "delay_percentage",
                        "label": "Schedule Slippage",
                        "value": delay_pct,
                        "formatted": f"{delay_pct:.1f}%",
                    },
                ]
                return self.build_result(
                    score=score,
                    reason=reason,
                    details=details,
                    confidence=confidence,
                    triggered=(score >= 30),
                    threshold=f"> {low_days} days overdue beyond planned completion date",
                    actual_value=f"{overdue_days} days overdue (+{delay_pct:.1f}% slippage)",
                    expected_value=f"Planned completion: {expected_comp.isoformat()} (Planned duration: {planned_duration} days)",
                    reference_value=f"As of {ref_date.isoformat()}",
                    evidence=evidence_items,
                    metadata=details,
                )
            else:
                # Ongoing project strictly on schedule (expected completion date has NOT passed)
                days_remaining = (expected_comp - ref_date).days
                score = 0
                completion_status = "ONGOING_ON_SCHEDULE"
                if days_remaining == 0:
                    reason = (
                        f"Project is on schedule within contractual timeline "
                        f"(due today on target completion date {expected_comp.isoformat()})."
                    )
                else:
                    reason = (
                        f"Project is on schedule within contractual timeline "
                        f"({days_remaining} days remaining until target completion {expected_comp.isoformat()})."
                    )
                confidence = self._compute_confidence(dates=dates, is_completed=False)

                details = {
                    "overdue_days": 0,
                    "delay_percentage": 0,
                    "status": status_clean,
                    "completion_status": completion_status,
                    "planned_duration": planned_duration,
                    "actual_duration": actual_duration,
                    "days_remaining": days_remaining,
                    "expected_completion_date": expected_comp.isoformat(),
                    "actual_completion_date": None,
                    "start_date": start_date.isoformat() if start_date else None,
                    "sanction_date": sanc_date.isoformat() if sanc_date else None,
                    "work_order_date": wo_date.isoformat() if wo_date else None,
                    "as_of_date": ref_date.isoformat(),
                    "invalid_timeline": is_invalid_timeline,
                    "project_id": project_id,
                }
                evidence_items = [
                    {
                        "metric": "planned_completion_date",
                        "label": "Planned Completion Date",
                        "value": expected_comp.isoformat(),
                        "formatted": expected_comp.isoformat(),
                    },
                    {
                        "metric": "actual_current_date",
                        "label": "Evaluation Reference Date",
                        "value": ref_date.isoformat(),
                        "formatted": ref_date.isoformat(),
                    },
                    {
                        "metric": "delay_days",
                        "label": "Delay Days",
                        "value": 0,
                        "formatted": "0 days",
                    },
                    {
                        "metric": "delay_percentage",
                        "label": "Schedule Slippage",
                        "value": 0.0,
                        "formatted": "+0.0%",
                    },
                ]
                return self.build_result(
                    score=score,
                    reason=reason,
                    details=details,
                    confidence=confidence,
                    triggered=False,
                    threshold=f"> {low_days} days overdue beyond planned completion date",
                    actual_value=f"On schedule ({days_remaining} days remaining)",
                    expected_value=f"Planned completion: {expected_comp.isoformat()} (Planned duration: {planned_duration} days)",
                    reference_value=f"As of {ref_date.isoformat()}",
                    evidence=evidence_items,
                    metadata=details,
                )

        except Exception as e:
            logger.error(
                "DelayDetectionEngine failed for project '%s': %s",
                project_id, str(e), exc_info=True
            )
            return self.build_result(
                score=0,
                reason=f"Delay detection encountered runtime error: {str(e)}",
                details={
                    "overdue_days": 0,
                    "delay_percentage": 0,
                    "status": "error",
                    "error": str(e),
                    "project_id": project_id,
                },
                confidence=0.0
            )

    # -------------------------------------------------------------------------
    # Helper: Date Parsing & Lifecycle Extraction
    # -------------------------------------------------------------------------

    @classmethod
    def _parse_reference_date(cls, context: Optional[Dict[str, Any]]) -> date:
        """
        Safely parses as_of_date (or aliases reference_date / current_date)
        from context or falls back to date.today().
        """
        if context:
            for key in ("as_of_date", "reference_date", "current_date"):
                if key in context and context[key] is not None:
                    parsed = parse_date_safe(context[key])
                    if parsed:
                        return parsed
        return date.today()

    @classmethod
    def _extract_lifecycle_dates(cls, project: Project) -> Dict[str, Optional[date]]:
        """
        Extracts and converts all project timeline dates safely using parse_date_safe.
        """
        rec_date = parse_date_safe(getattr(project, "recommendation_date", None))
        sanc_date = parse_date_safe(getattr(project, "sanction_date", None))
        wo_date = parse_date_safe(getattr(project, "work_order_date", None))
        exp_comp = parse_date_safe(getattr(project, "expected_completion_date", None))
        act_comp = parse_date_safe(getattr(project, "actual_completion_date", None))

        # Start date hierarchy: work order date -> sanction date -> recommendation date
        start_date = wo_date or sanc_date or rec_date

        return {
            "start_date": start_date,
            "work_order_date": wo_date,
            "sanction_date": sanc_date,
            "recommendation_date": rec_date,
            "expected_completion_date": exp_comp,
            "actual_completion_date": act_comp,
        }

    @classmethod
    def _calculate_durations(
        cls,
        start_date: Optional[date],
        expected_comp: date,
        actual_comp: Optional[date],
        ref_date: date,
        is_completed: bool,
    ) -> Tuple[Optional[int], Optional[int], bool]:
        """
        Calculates planned and actual/elapsed duration in days with data entry safety fallbacks.
        Returns (planned_duration, actual_duration, is_invalid_timeline).
        """
        is_invalid_timeline = False

        # 1. Planned duration
        if start_date and expected_comp:
            planned = (expected_comp - start_date).days
            if planned < 0:
                # Reverse dates entered in database (expected before start)
                is_invalid_timeline = True
                planned_duration = 30  # Fallback duration minimum
            elif planned == 0:
                # Same-day planned milestone
                planned_duration = 1
            else:
                planned_duration = planned
        else:
            planned_duration = None

        # 2. Actual duration (or elapsed duration if ongoing)
        if is_completed and actual_comp and start_date:
            actual = (actual_comp - start_date).days
            if actual < 0:
                # Actual completion before start date: flag invalid data entry
                is_invalid_timeline = True
                actual_duration = 1
            elif actual == 0:
                actual_duration = 1
            else:
                actual_duration = actual
        elif start_date:
            elapsed = (ref_date - start_date).days
            actual_duration = max(0, elapsed)
        else:
            actual_duration = None

        return planned_duration, actual_duration, is_invalid_timeline

    # -------------------------------------------------------------------------
    # Helper: Delay Scoring & Normalization (0-100)
    # -------------------------------------------------------------------------

    def _score_delay(
        self,
        overdue_days: int,
        planned_duration: Optional[int],
        low_days: int,
        medium_days: int,
        high_days: int,
        critical_days: int,
    ) -> int:
        """
        Translates overdue calendar days into a smooth normalized 0–100 risk score
        aligned with centralized thresholds:
        - 0 days: Score 0 (LOW)
        - 1 to low_days: Score 1 to 29 (LOW) - continuous linear curve, no day-1 leap
        - low_days+1 to medium_days: Score 30 to 59 (MEDIUM)
        - medium_days+1 to high_days: Score 60 to 79 (HIGH)
        - > high_days: Score 80 to 100 (CRITICAL)
        """
        if overdue_days <= 0:
            return 0

        # Tier 1: Mild slippage (1 to low_days) -> Score 1 to 29 (LOW)
        if overdue_days <= low_days:
            # Strictly continuous: Day 1 starts at 1, Day low_days reaches 29
            score = max(1.0, (overdue_days / float(low_days)) * 29.0)

        # Tier 2: Moderate delay (low_days to medium_days) -> Score 30 to 59 (MEDIUM)
        elif overdue_days <= medium_days:
            range_days = max(1, medium_days - low_days)
            score = 30.0 + ((overdue_days - low_days) / float(range_days)) * 29.0

        # Tier 3: Significant delay (medium_days to high_days) -> Score 60 to 79 (HIGH)
        elif overdue_days <= high_days:
            range_days = max(1, high_days - medium_days)
            score = 60.0 + ((overdue_days - medium_days) / float(range_days)) * 19.0

        # Tier 4: Severe / Chronic delay (> high_days) -> Score 80 to 100 (CRITICAL)
        else:
            range_days = max(1, critical_days - high_days)
            raw = 80.0 + ((overdue_days - high_days) / float(range_days)) * 20.0
            score = min(100.0, raw)

        # Relative schedule overrun modifier
        if planned_duration and planned_duration > 0:
            pct_overrun = overdue_days / float(planned_duration)
            if pct_overrun >= 1.0:
                score = min(100.0, score + 8.0)
            elif pct_overrun >= 0.50:
                score = min(100.0, score + 4.0)

        return int(round(max(0.0, min(100.0, score))))

    # -------------------------------------------------------------------------
    # Helper: Diagnostic Confidence Calculation
    # -------------------------------------------------------------------------

    @classmethod
    def _compute_confidence(
        cls,
        dates: Dict[str, Optional[date]],
        is_completed: bool,
    ) -> float:
        """
        Calculates diagnostic confidence based on timeline completeness.
        """
        start = dates.get("start_date")
        expected = dates.get("expected_completion_date")
        actual = dates.get("actual_completion_date")

        if not expected:
            return 0.0

        if is_completed:
            if actual and start:
                return 0.95
            elif actual:
                return 0.85
            return 0.50

        # Ongoing projects
        if start and expected:
            return 0.90
        elif expected:
            return 0.70

        return 0.40
