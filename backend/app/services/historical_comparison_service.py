"""
backend/app/services/historical_comparison_service.py
=============================================================================
Historical Comparison Service (Phase 11).
=============================================================================

Independent, reusable service for detecting meaningful changes between
incoming project data and the latest historical snapshot. Prevents unnecessary
duplicate snapshots caused by minor floating-point jitter while capturing
concrete modifications across project status, finances, physical execution,
milestones, derived metrics, and risk evaluations.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional, List, Union, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

try:
    from app.models.project import Project, ProjectSnapshot, RiskHistory
except ImportError:
    from backend.app.models.project import Project, ProjectSnapshot, RiskHistory


# =============================================================================
# 1. Tolerances & Data Structures
# =============================================================================

@dataclass
class ComparisonTolerances:
    """
    Thresholds below which numeric variations are treated as insignificant jitter.
    """
    monetary: Decimal = Decimal("1.00")         # Minimum ₹1.00 difference
    percentage: Decimal = Decimal("0.10")       # Minimum 0.10% difference
    risk_score: Decimal = Decimal("0.10")       # Minimum 0.10 risk score difference
    days_delayed: int = 1                       # Minimum 1 full day difference


@dataclass
class FieldChange:
    """
    Detailed metadata for an individual detected field alteration.
    """
    field_name: str
    display_name: str
    category: str                               # 'financial', 'progress', 'timeline', 'status', 'risk', 'derived'
    previous_value: Any
    new_value: Any
    delta: Optional[float] = None
    delta_pct: Optional[float] = None
    is_meaningful: bool = True
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "display_name": self.display_name,
            "category": self.category,
            "previous_value": str(self.previous_value) if isinstance(self.previous_value, (Decimal, date, datetime)) else self.previous_value,
            "new_value": str(self.new_value) if isinstance(self.new_value, (Decimal, date, datetime)) else self.new_value,
            "delta": self.delta,
            "delta_pct": self.delta_pct,
            "is_meaningful": self.is_meaningful,
            "summary": self.summary
        }


@dataclass
class ComparisonResult:
    """
    Aggregated comparison outcome across all monitored project attributes.
    """
    is_initial: bool
    has_meaningful_changes: bool
    changes_count: int
    field_changes: List[FieldChange] = field(default_factory=list)
    change_summary_text: str = ""
    structured_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_initial": self.is_initial,
            "has_meaningful_changes": self.has_meaningful_changes,
            "changes_count": self.changes_count,
            "change_summary_text": self.change_summary_text,
            "structured_summary": self.structured_summary,
            "field_changes": [c.to_dict() for c in self.field_changes]
        }


# =============================================================================
# 2. Value Normalization Utilities
# =============================================================================

def _to_decimal(val: Any) -> Optional[Decimal]:
    """Safely converts input to Decimal with precision normalization."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    try:
        # Round to 4 decimal places for floating-point comparisons
        return Decimal(str(val).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_date(val: Any) -> Optional[date]:
    """Safely converts input to datetime.date."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        # Try ISO format 'YYYY-MM-DD'
        try:
            return datetime.fromisoformat(val).date()
        except ValueError:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
    return None


def _to_str(val: Any) -> Optional[str]:
    """Safely converts input to trimmed string."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _to_int(val: Any) -> Optional[int]:
    """Safely converts input to int."""
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _format_currency(amt: Union[Decimal, float, None]) -> str:
    """Formats monetary amounts into readable currency strings."""
    if amt is None:
        return "₹0.00"
    d = Decimal(str(amt))
    return f"₹{d:,.2f}"


# =============================================================================
# 3. Historical Comparison Service Implementation
# =============================================================================

class HistoricalComparisonService:
    """
    Compares incoming project state with prior snapshots and creates new snapshots
    when meaningful deviations occur.
    """

    DEFAULT_TOLERANCES = ComparisonTolerances()

    @staticmethod
    def get_latest_snapshot(db: Session, project_id: str) -> Optional[ProjectSnapshot]:
        """
        Retrieves the most recent historical snapshot for a project.
        """
        stmt = (
            select(ProjectSnapshot)
            .where(ProjectSnapshot.project_id == project_id)
            .order_by(desc(ProjectSnapshot.snapshot_datetime), desc(ProjectSnapshot.snapshot_id))
            .limit(1)
        )
        return db.execute(stmt).scalars().first()

    @classmethod
    def compare_data(
        cls,
        previous_snapshot: Optional[ProjectSnapshot],
        incoming_data: Union[Dict[str, Any], Any],
        tolerances: Optional[ComparisonTolerances] = None
    ) -> ComparisonResult:
        """
        Compares incoming project data with an existing snapshot.
        If previous_snapshot is None, marks as first-ever initial ingestion.
        """
        tol = tolerances or cls.DEFAULT_TOLERANCES

        # Helper to extract key from dict or object
        def get_val(data: Any, key: str, default: Any = None) -> Any:
            if isinstance(data, dict):
                return data.get(key, default)
            return getattr(data, key, default)

        # ---------------------------------------------------------------------
        # Case A: First-ever ingestion (no previous snapshot)
        # ---------------------------------------------------------------------
        if previous_snapshot is None:
            return ComparisonResult(
                is_initial=True,
                has_meaningful_changes=True,
                changes_count=1,
                field_changes=[],
                change_summary_text="Initial baseline project snapshot recorded upon first ingestion.",
                structured_summary={
                    "event": "initial_baseline",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )

        # ---------------------------------------------------------------------
        # Case B: Incremental comparison against prior snapshot
        # ---------------------------------------------------------------------
        field_changes: List[FieldChange] = []

        # 1. Project Status (Categorical)
        old_status = _to_str(previous_snapshot.project_status)
        new_status = _to_str(get_val(incoming_data, "project_status") or get_val(incoming_data, "current_status"))
        if new_status and old_status != new_status:
            field_changes.append(FieldChange(
                field_name="project_status",
                display_name="Project Status",
                category="status",
                previous_value=old_status,
                new_value=new_status,
                summary=f"Project status changed from '{old_status}' to '{new_status}'."
            ))

        # 2. Monetary Fields (Financials)
        monetary_fields = [
            ("sanctioned_amount", "Sanctioned Amount", "financial"),
            ("released_amount", "Released Amount", "financial"),
            ("expenditure_amount", "Expenditure Amount", "financial"),
            ("recommended_amount", "Recommended Amount", "financial"),
            ("unspent_balance", "Unspent Balance", "financial"),
            ("cost_overrun_amount", "Cost Overrun Amount", "financial"),
            ("cost_deviation", "Cost Deviation", "derived")
        ]

        for field_name, display_name, category in monetary_fields:
            old_val = _to_decimal(getattr(previous_snapshot, field_name, None))
            new_val = _to_decimal(get_val(incoming_data, field_name))

            if new_val is not None:
                if old_val is None:
                    # Transition from None to Value
                    field_changes.append(FieldChange(
                        field_name=field_name,
                        display_name=display_name,
                        category=category,
                        previous_value=None,
                        new_value=float(new_val),
                        delta=float(new_val),
                        summary=f"{display_name} initialized to {_format_currency(new_val)}."
                    ))
                else:
                    diff = new_val - old_val
                    if abs(diff) >= tol.monetary:
                        pct_change = float((diff / old_val) * 100) if old_val != 0 else None
                        sign = "+" if diff > 0 else ""
                        pct_str = f" ({sign}{pct_change:.1f}%)" if pct_change is not None else ""
                        field_changes.append(FieldChange(
                            field_name=field_name,
                            display_name=display_name,
                            category=category,
                            previous_value=float(old_val),
                            new_value=float(new_val),
                            delta=float(diff),
                            delta_pct=round(pct_change, 2) if pct_change is not None else None,
                            summary=f"{display_name} shifted from {_format_currency(old_val)} to {_format_currency(new_val)} ({sign}{_format_currency(diff)}{pct_str})."
                        ))

        # 3. Percentage Fields (Physical & Financial Progress, Utilization)
        pct_fields = [
            ("physical_progress_pct", "Physical Progress", "progress"),
            ("financial_progress_pct", "Financial Progress", "progress"),
            ("utilization_rate_pct", "Fund Utilization", "financial"),
            ("progress_gap", "Progress Gap", "derived")
        ]

        for field_name, display_name, category in pct_fields:
            old_val = _to_decimal(getattr(previous_snapshot, field_name, None))
            new_val = _to_decimal(get_val(incoming_data, field_name))

            if new_val is not None:
                if old_val is None:
                    field_changes.append(FieldChange(
                        field_name=field_name,
                        display_name=display_name,
                        category=category,
                        previous_value=None,
                        new_value=float(new_val),
                        delta=float(new_val),
                        summary=f"{display_name} initialized to {float(new_val):.1f}%."
                    ))
                else:
                    diff = new_val - old_val
                    if abs(diff) >= tol.percentage:
                        sign = "+" if diff > 0 else ""
                        field_changes.append(FieldChange(
                            field_name=field_name,
                            display_name=display_name,
                            category=category,
                            previous_value=float(old_val),
                            new_value=float(new_val),
                            delta=float(diff),
                            delta_pct=float(diff),
                            summary=f"{display_name} changed from {float(old_val):.1f}% to {float(new_val):.1f}% ({sign}{float(diff):.1f}%)."
                        ))

        # 4. Timeline Dates & Overdue Days
        date_fields = [
            ("expected_completion_date", "Expected Completion Date"),
            ("actual_completion_date", "Actual Completion Date")
        ]

        for field_name, display_name in date_fields:
            old_d = _to_date(getattr(previous_snapshot, field_name, None))
            new_d = _to_date(get_val(incoming_data, field_name))

            # Only record if incoming date is explicitly provided or transitioned
            incoming_has_key = (
                field_name in incoming_data if isinstance(incoming_data, dict)
                else hasattr(incoming_data, field_name)
            )
            if incoming_has_key and old_d != new_d:
                if old_d is None and new_d is not None:
                    field_changes.append(FieldChange(
                        field_name=field_name,
                        display_name=display_name,
                        category="timeline",
                        previous_value=None,
                        new_value=new_d.isoformat(),
                        summary=f"{display_name} set to {new_d.isoformat()}."
                    ))
                elif old_d is not None and new_d is None:
                    field_changes.append(FieldChange(
                        field_name=field_name,
                        display_name=display_name,
                        category="timeline",
                        previous_value=old_d.isoformat(),
                        new_value=None,
                        summary=f"{display_name} cleared from {old_d.isoformat()}."
                    ))
                elif old_d and new_d:
                    delta_d = (new_d - old_d).days
                    sign = "+" if delta_d > 0 else ""
                    field_changes.append(FieldChange(
                        field_name=field_name,
                        display_name=display_name,
                        category="timeline",
                        previous_value=old_d.isoformat(),
                        new_value=new_d.isoformat(),
                        delta=delta_d,
                        summary=f"{display_name} moved from {old_d.isoformat()} to {new_d.isoformat()} ({sign}{delta_d} days)."
                    ))

        # Days Delayed
        old_delay = _to_int(previous_snapshot.days_delayed) or 0
        new_delay_raw = get_val(incoming_data, "days_delayed")
        if new_delay_raw is not None:
            new_delay = _to_int(new_delay_raw) or 0
            diff_delay = new_delay - old_delay
            if abs(diff_delay) >= tol.days_delayed:
                sign = "+" if diff_delay > 0 else ""
                field_changes.append(FieldChange(
                    field_name="days_delayed",
                    display_name="Days Delayed",
                    category="timeline",
                    previous_value=old_delay,
                    new_value=new_delay,
                    delta=diff_delay,
                    summary=f"Overdue delay changed from {old_delay}d to {new_delay}d ({sign}{diff_delay}d)."
                ))

        # Milestone Status
        old_ms = _to_str(previous_snapshot.milestone_status)
        new_ms = _to_str(get_val(incoming_data, "milestone_status"))
        if new_ms and old_ms != new_ms:
            field_changes.append(FieldChange(
                field_name="milestone_status",
                display_name="Milestone Status",
                category="timeline",
                previous_value=old_ms,
                new_value=new_ms,
                summary=f"Milestone status updated from '{old_ms}' to '{new_ms}'."
            ))

        # 5. Risk Scores & Categorical Tier
        old_score = _to_decimal(previous_snapshot.overall_risk_score) or Decimal("0.00")
        new_score = _to_decimal(get_val(incoming_data, "overall_risk_score") or get_val(incoming_data, "risk_score"))

        if new_score is not None:
            diff_score = new_score - old_score
            if abs(diff_score) >= tol.risk_score:
                sign = "+" if diff_score > 0 else ""
                field_changes.append(FieldChange(
                    field_name="overall_risk_score",
                    display_name="Overall Risk Score",
                    category="risk",
                    previous_value=float(old_score),
                    new_value=float(new_score),
                    delta=float(diff_score),
                    summary=f"Overall risk score adjusted from {float(old_score):.1f} to {float(new_score):.1f} ({sign}{float(diff_score):.1f})."
                ))

        def _norm_tier(t: Optional[str]) -> Optional[str]:
            if not t:
                return None
            s = t.strip().capitalize()
            return "Medium" if s == "Moderate" else s

        old_tier = _to_str(previous_snapshot.risk_level)
        new_tier = _to_str(get_val(incoming_data, "risk_level"))
        if new_tier and _norm_tier(old_tier) != _norm_tier(new_tier):
            field_changes.append(FieldChange(
                field_name="risk_level",
                display_name="Risk Tier",
                category="risk",
                previous_value=old_tier,
                new_value=new_tier,
                summary=f"Risk classification moved from '{old_tier}' to '{new_tier}'."
            ))

        # ---------------------------------------------------------------------
        # Final Summary Synthesis
        # ---------------------------------------------------------------------
        has_changes = len(field_changes) > 0
        if has_changes:
            narrative = "; ".join(c.summary for c in field_changes)
            structured = {
                "changes_count": len(field_changes),
                "modified_fields": [c.field_name for c in field_changes],
                "details": {c.field_name: c.to_dict() for c in field_changes}
            }
        else:
            narrative = "No meaningful project changes detected within numeric tolerance thresholds."
            structured = {"changes_count": 0, "modified_fields": [], "details": {}}

        return ComparisonResult(
            is_initial=False,
            has_meaningful_changes=has_changes,
            changes_count=len(field_changes),
            field_changes=field_changes,
            change_summary_text=narrative,
            structured_summary=structured
        )

    @classmethod
    def create_or_update_snapshot(
        cls,
        db: Session,
        project_id: str,
        incoming_data: Union[Dict[str, Any], Any],
        tolerances: Optional[ComparisonTolerances] = None,
        force_snapshot: bool = False
    ) -> Tuple[Optional[ProjectSnapshot], ComparisonResult]:
        """
        Retrieves the latest snapshot, executes the delta comparison, and inserts
        a new ProjectSnapshot if meaningful changes occurred or force_snapshot is True.
        Returns (created_snapshot_or_None, comparison_result).
        """
        # Helper to extract key
        def get_val(data: Any, key: str, default: Any = None) -> Any:
            if isinstance(data, dict):
                return data.get(key, default)
            return getattr(data, key, default)

        latest_snap = cls.get_latest_snapshot(db, project_id)
        comp_result = cls.compare_data(latest_snap, incoming_data, tolerances)

        if not comp_result.has_meaningful_changes and not force_snapshot:
            return None, comp_result

        # Build new snapshot object using incoming values with fallbacks to prior snapshot
        def coalesce_val(key: str, default: Any = None) -> Any:
            val = get_val(incoming_data, key)
            if val is not None:
                return val
            if latest_snap:
                return getattr(latest_snap, key, default)
            return default

        now = datetime.now(timezone.utc)
        today = date.today()

        status_val = (
            get_val(incoming_data, "project_status") or
            get_val(incoming_data, "current_status") or
            (latest_snap.project_status if latest_snap else "Recommended")
        )

        sanctioned_amt = _to_decimal(coalesce_val("sanctioned_amount"))
        released_amt = _to_decimal(coalesce_val("released_amount", Decimal("0.00"))) or Decimal("0.00")
        expenditure_amt = _to_decimal(coalesce_val("expenditure_amount", Decimal("0.00"))) or Decimal("0.00")
        recommended_amt = _to_decimal(coalesce_val("recommended_amount", Decimal("0.00"))) or Decimal("0.00")
        
        # Calculate unspent balance if not explicitly provided
        unspent_val = _to_decimal(get_val(incoming_data, "unspent_balance"))
        if unspent_val is None:
            unspent_val = max(Decimal("0.00"), released_amt - expenditure_amt)

        util_val = _to_decimal(get_val(incoming_data, "utilization_rate_pct"))
        if util_val is None and released_amt > 0:
            util_val = round((expenditure_amt / released_amt) * Decimal("100.0"), 2)

        snapshot = ProjectSnapshot(
            project_id=project_id,
            snapshot_datetime=now,
            snapshot_date=today,
            project_status=str(status_val),
            recommended_amount=recommended_amt,
            sanctioned_amount=sanctioned_amt,
            released_amount=released_amt,
            expenditure_amount=expenditure_amt,
            unspent_balance=unspent_val,
            utilization_rate_pct=util_val,
            cost_overrun_amount=_to_decimal(coalesce_val("cost_overrun_amount", Decimal("0.00"))) or Decimal("0.00"),
            physical_progress_pct=_to_decimal(coalesce_val("physical_progress_pct", Decimal("0.00"))) or Decimal("0.00"),
            financial_progress_pct=_to_decimal(coalesce_val("financial_progress_pct", Decimal("0.00"))) or Decimal("0.00"),
            expected_completion_date=_to_date(coalesce_val("expected_completion_date")),
            actual_completion_date=_to_date(coalesce_val("actual_completion_date")),
            days_delayed=_to_int(coalesce_val("days_delayed", 0)) or 0,
            milestone_status=str(coalesce_val("milestone_status", "On Track")),
            cost_deviation=_to_decimal(coalesce_val("cost_deviation", Decimal("0.00"))) or Decimal("0.00"),
            progress_gap=_to_decimal(coalesce_val("progress_gap", Decimal("0.00"))) or Decimal("0.00"),
            derived_metrics=get_val(incoming_data, "derived_metrics") or (latest_snap.derived_metrics if latest_snap else None),
            overall_risk_score=_to_decimal(coalesce_val("overall_risk_score", coalesce_val("risk_score", Decimal("0.00")))) or Decimal("0.00"),
            risk_level=str(coalesce_val("risk_level", "Low")),
            change_summary=comp_result.change_summary_text
        )

        db.add(snapshot)
        db.flush()

        return snapshot, comp_result
