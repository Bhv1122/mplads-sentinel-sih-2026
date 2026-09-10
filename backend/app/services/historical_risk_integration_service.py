"""
backend/app/services/historical_risk_integration_service.py
=============================================================================
Historical Risk Integration Service (Phase 11).
=============================================================================

Coordinates transactional project updates with historical snapshotting and
the complete 6-engine risk assessment suite:
1. Detects meaningful changes using HistoricalComparisonService.
2. In a transaction, creates an immutable ProjectSnapshot representing the new state.
3. Executes the existing modular risk engines:
   - Cost Anomaly Engine
   - Duplicate Detection Engine
   - Delay Detection Engine
   - Fund Utilization Detector
   - Progress Mismatch Engine
   - Agency Pattern Engine
   - Central Risk Aggregation & Explained Risk Engine
4. Records the resulting composite risk and detector scores in risk_history linked to the snapshot.
5. Updates the live project and related tables only after risk calculation succeeds.
6. Ensures transactional atomicity: any failure in calculation rolls back all changes.
"""

import logging
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, Union
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, text

try:
    from app.models.project import (
        Project, Financial, Progress, RiskScore, RiskFactor,
        ProjectHistory, ProjectFeature, ProjectSnapshot, RiskHistory
    )
    from app.services.historical_comparison_service import (
        HistoricalComparisonService, ComparisonResult, ComparisonTolerances
    )
    from app.services.risk_engine import RiskEngine
    from app.services.risk.fund_utilization import FundUtilizationDetector
except ImportError:
    from backend.app.models.project import (
        Project, Financial, Progress, RiskScore, RiskFactor,
        ProjectHistory, ProjectFeature, ProjectSnapshot, RiskHistory
    )
    from backend.app.services.historical_comparison_service import (
        HistoricalComparisonService, ComparisonResult, ComparisonTolerances
    )
    from backend.app.services.risk_engine import RiskEngine
    from backend.app.services.risk.fund_utilization import FundUtilizationDetector

logger = logging.getLogger(__name__)


def _normalize_db_risk_level(level: Optional[str]) -> str:
    """Normalizes risk level string to match DB CHECK constraint."""
    if not level:
        return "Low"
    l = str(level).strip().capitalize()
    if l in ("Low", "Moderate", "Medium", "High", "Critical"):
        return l
    if l.upper() == "MEDIUM":
        return "Medium"
    return "Low"


def _normalize_milestone_status(status: Optional[str]) -> str:
    """Normalizes milestone status to match DB CHECK constraint."""
    if not status:
        return "On Track"
    s = str(status).strip()
    if s in ("On Track", "Delayed", "Critical", "Completed"):
        return s
    low = s.lower()
    if "critical" in low:
        return "Critical"
    if "delay" in low:
        return "Delayed"
    if "complete" in low:
        return "Completed"
    return "On Track"


def _derive_stage_from_progress(physical_pct: Optional[Decimal]) -> str:
    """Derives valid current_stage string based on physical execution percentage."""
    if physical_pct is None:
        return "Structure"
    try:
        p = float(physical_pct)
    except Exception:
        return "Structure"
    if p >= 100.0:
        return "Completed"
    elif p >= 80.0:
        return "Finishing"
    elif p >= 30.0:
        return "Structure"
    elif p > 0.0:
        return "Foundation"
    return "Feasibility"


def _to_decimal(val: Any) -> Optional[Decimal]:
    """Safely converts input to Decimal."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val).strip())
    except Exception:
        return None


class UpdateProcessingResult(BaseModel):
    """Execution summary of an integrated project update."""
    project_id: str
    updated: bool
    historical_update_required: bool = True
    is_initial: bool = False
    message: str = ""
    snapshot_id: Optional[int] = None
    history_id: Optional[int] = None
    overall_risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    change_summary: str = ""
    changes_count: int = 0
    detector_scores: Optional[Dict[str, Any]] = None


class HistoricalRiskIntegrationService:
    """
    Manages transactional project updates with automated historical versioning
    and integrated multi-engine risk evaluation.
    """

    def __init__(
        self,
        risk_engine: Optional[RiskEngine] = None,
        fund_utilization_detector: Optional[FundUtilizationDetector] = None,
        comparison_service: Optional[HistoricalComparisonService] = None,
    ):
        self.risk_engine = risk_engine or RiskEngine()
        self.fund_utilization_detector = fund_utilization_detector or FundUtilizationDetector()
        self.comparison_service = comparison_service or HistoricalComparisonService

    def process_project_update_transactional(
        self,
        db: Session,
        project_id: str,
        update_payload: Dict[str, Any],
        performed_by: str = "System Admin",
        force_snapshot: bool = False,
        tolerances: Optional[ComparisonTolerances] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> UpdateProcessingResult:
        """
        Executes an atomic update of project data, creating a historical snapshot,
        evaluating all 6 risk engines, persisting risk_history, and updating the project.

        Idempotent: If identical data or changes below tolerance are submitted,
        no duplicate snapshot or risk calculation is created.

        Concurrency: Uses PostgreSQL transaction advisory locking and row-level locking
        (FOR UPDATE) to prevent race conditions across parallel requests.
        """
        # 1. Acquire transaction advisory lock on PostgreSQL to serialize concurrent updates for this project
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:pid))"), {"pid": project_id})

        # Lock the project row for update
        stmt = select(Project).where(Project.project_id == project_id).with_for_update()
        project = db.execute(stmt).scalars().first()
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        financial = db.execute(
            select(Financial).where(Financial.project_id == project_id)
        ).scalars().first()

        latest_progress = db.execute(
            select(Progress)
            .where(Progress.project_id == project_id)
            .order_by(desc(Progress.reported_date))
            .limit(1)
        ).scalars().first()

        current_risk = db.execute(
            select(RiskScore).where(RiskScore.project_id == project_id)
        ).scalars().first()

        features = db.execute(
            select(ProjectFeature).where(ProjectFeature.project_id == project_id)
        ).scalars().first()

        # Retrieve latest snapshot after acquiring exclusive lock
        latest_snapshot = self.comparison_service.get_latest_snapshot(db, project_id)

        # 2. Build full representation of the proposed incoming state
        def coalesce_incoming(key: str, fallback_obj: Any, attr_name: Optional[str] = None) -> Any:
            if key in update_payload and update_payload[key] is not None:
                return update_payload[key]
            if fallback_obj:
                return getattr(fallback_obj, attr_name or key, None)
            return None

        proposed_state = {
            "project_status": update_payload.get("project_status") or update_payload.get("current_status") or project.current_status,
            "recommended_amount": coalesce_incoming("recommended_amount", financial),
            "sanctioned_amount": coalesce_incoming("sanctioned_amount", financial),
            "released_amount": coalesce_incoming("released_amount", financial),
            "expenditure_amount": coalesce_incoming("expenditure_amount", financial),
            "unspent_balance": coalesce_incoming("unspent_balance", financial),
            "utilization_rate_pct": coalesce_incoming("utilization_rate_pct", financial),
            "cost_overrun_amount": coalesce_incoming("cost_overrun_amount", financial),
            "physical_progress_pct": coalesce_incoming("physical_progress_pct", latest_progress),
            "financial_progress_pct": coalesce_incoming("financial_progress_pct", latest_progress),
            "expected_completion_date": coalesce_incoming("expected_completion_date", project),
            "actual_completion_date": coalesce_incoming("actual_completion_date", project),
            "days_delayed": coalesce_incoming("days_delayed", latest_progress),
            "milestone_status": coalesce_incoming("milestone_status", latest_progress),
            "cost_deviation": coalesce_incoming("cost_deviation", features),
            "progress_gap": coalesce_incoming("progress_gap", features),
            "derived_metrics": update_payload.get("derived_metrics") or (features.derived_metrics if hasattr(features, "derived_metrics") else None),
            "overall_risk_score": update_payload.get("overall_risk_score") or (latest_snapshot.overall_risk_score if latest_snapshot else (current_risk.overall_risk_score if current_risk else Decimal("0.00"))),
            "risk_level": _normalize_db_risk_level(update_payload.get("risk_level") or (latest_snapshot.risk_level if latest_snapshot else (current_risk.risk_level if current_risk else "Low")))
        }

        # Dynamically recalculate unspent balance & overruns for mathematical consistency
        sanctioned_amt = _to_decimal(proposed_state["sanctioned_amount"])
        released_amt = _to_decimal(proposed_state["released_amount"])
        expenditure_amt = _to_decimal(proposed_state["expenditure_amount"])

        if released_amt is not None and expenditure_amt is not None:
            proposed_state["unspent_balance"] = max(Decimal("0.00"), released_amt - expenditure_amt)
            if released_amt > 0:
                raw_util = (expenditure_amt / released_amt) * Decimal("100.0")
                proposed_state["utilization_rate_pct"] = min(Decimal("100.00"), max(Decimal("0.00"), round(raw_util, 2)))

        if sanctioned_amt is not None and expenditure_amt is not None:
            if expenditure_amt > sanctioned_amt:
                proposed_state["cost_overrun_amount"] = expenditure_amt - sanctioned_amt
            else:
                proposed_state["cost_overrun_amount"] = Decimal("0.00")

        # 3. Detect meaningful changes against latest snapshot
        comp_result: ComparisonResult = self.comparison_service.compare_data(
            previous_snapshot=latest_snapshot,
            incoming_data=proposed_state,
            tolerances=tolerances
        )

        if not comp_result.has_meaningful_changes and not force_snapshot:
            # Apply non-monitored descriptive fields if any
            non_monitored_keys = [
                "project_title", "project_description", "sector", "sub_sector",
                "block_name", "implementing_agency", "sanction_date", "work_order_date"
            ]
            applied_any = False
            for k in non_monitored_keys:
                if k in update_payload and update_payload[k] is not None and getattr(project, k, None) != update_payload[k]:
                    setattr(project, k, update_payload[k])
                    applied_any = True

            # Retrieve existing risk history for the latest snapshot
            latest_risk_hist = None
            if latest_snapshot:
                latest_risk_hist = db.execute(
                    select(RiskHistory).where(RiskHistory.snapshot_id == latest_snapshot.snapshot_id)
                ).scalars().first()

            # Always commit to release PostgreSQL advisory lock and row lock
            db.commit()


            return UpdateProcessingResult(
                project_id=project_id,
                updated=applied_any,
                historical_update_required=False,
                is_initial=False,
                message="No historical update was required: incoming project state is identical to the latest snapshot within tolerance.",
                snapshot_id=latest_snapshot.snapshot_id if latest_snapshot else None,
                history_id=latest_risk_hist.history_id if latest_risk_hist else None,
                overall_risk_score=float(latest_snapshot.overall_risk_score) if latest_snapshot else None,
                risk_level=latest_snapshot.risk_level if latest_snapshot else None,
                change_summary=comp_result.change_summary_text or "No meaningful project changes detected within numeric tolerance thresholds.",
                changes_count=0,
                detector_scores=latest_risk_hist.detector_scores if latest_risk_hist else None
            )

        # 4. Execute Transactional Pipeline
        try:
            now_dt = datetime.now(timezone.utc)
            today_d = date.today()

            # -----------------------------------------------------------------
            # Step A: Stage changes on project, financial, progress
            # (Flushed so risk detectors querying DB see the new state)
            # -----------------------------------------------------------------
            # Project Master fields
            for f in [
                "project_title", "project_description", "sector", "sub_sector",
                "block_name", "implementing_agency", "sanction_date", "work_order_date",
                "expected_completion_date", "actual_completion_date"
            ]:
                if f in update_payload and update_payload[f] is not None:
                    setattr(project, f, update_payload[f])

            old_status = project.current_status
            new_status = proposed_state["project_status"]
            project.current_status = new_status

            # Financial record
            if financial:
                for f in ["recommended_amount", "sanctioned_amount", "released_amount", "expenditure_amount"]:
                    if f in update_payload and update_payload[f] is not None:
                        setattr(financial, f, update_payload[f])

                if financial.released_amount is not None and financial.expenditure_amount is not None:
                    if financial.released_amount > 0:
                        raw_util = (financial.expenditure_amount / financial.released_amount) * Decimal("100.0")
                        financial.utilization_rate_pct = min(Decimal("100.00"), max(Decimal("0.00"), round(raw_util, 2)))

                if financial.sanctioned_amount is not None and financial.expenditure_amount is not None:
                    if financial.expenditure_amount > financial.sanctioned_amount:
                        financial.cost_overrun_amount = financial.expenditure_amount - financial.sanctioned_amount
                        financial.cost_overrun_pct = round((financial.cost_overrun_amount / financial.sanctioned_amount) * Decimal("100.0"), 2)
                    else:
                        financial.cost_overrun_amount = Decimal("0.00")
                        financial.cost_overrun_pct = Decimal("0.00")

            # Progress record (insert or update latest progress if supplied)
            if any(k in update_payload for k in ["physical_progress_pct", "financial_progress_pct", "days_delayed", "milestone_status"]):
                if latest_progress and latest_progress.reported_date == today_d:
                    if "physical_progress_pct" in update_payload:
                        latest_progress.physical_progress_pct = update_payload["physical_progress_pct"]
                    if "financial_progress_pct" in update_payload:
                        latest_progress.financial_progress_pct = update_payload["financial_progress_pct"]
                    if "days_delayed" in update_payload:
                        latest_progress.days_delayed = update_payload["days_delayed"]
                    if "milestone_status" in update_payload:
                        latest_progress.milestone_status = _normalize_milestone_status(update_payload["milestone_status"])
                    if "physical_progress_pct" in update_payload:
                        latest_progress.current_stage = _derive_stage_from_progress(update_payload["physical_progress_pct"])
                else:
                    new_prog = Progress(
                        project_id=project_id,
                        reported_date=today_d,
                        physical_progress_pct=proposed_state["physical_progress_pct"] or Decimal("0.00"),
                        financial_progress_pct=proposed_state["financial_progress_pct"] or Decimal("0.00"),
                        current_stage=_derive_stage_from_progress(proposed_state["physical_progress_pct"]),
                        days_delayed=proposed_state["days_delayed"] or 0,
                        milestone_status=_normalize_milestone_status(proposed_state["milestone_status"])
                    )
                    db.add(new_prog)

            db.flush()

            # -----------------------------------------------------------------
            # Step B: Create immutable ProjectSnapshot representing new state
            # -----------------------------------------------------------------
            snapshot = ProjectSnapshot(
                project_id=project_id,
                snapshot_datetime=now_dt,
                snapshot_date=today_d,
                project_status=new_status,
                recommended_amount=proposed_state["recommended_amount"] or Decimal("0.00"),
                sanctioned_amount=proposed_state["sanctioned_amount"],
                released_amount=proposed_state["released_amount"] or Decimal("0.00"),
                expenditure_amount=proposed_state["expenditure_amount"] or Decimal("0.00"),
                unspent_balance=proposed_state["unspent_balance"] or Decimal("0.00"),
                utilization_rate_pct=proposed_state["utilization_rate_pct"],
                cost_overrun_amount=proposed_state["cost_overrun_amount"] or Decimal("0.00"),
                physical_progress_pct=proposed_state["physical_progress_pct"] or Decimal("0.00"),
                financial_progress_pct=proposed_state["financial_progress_pct"] or Decimal("0.00"),
                expected_completion_date=proposed_state["expected_completion_date"],
                actual_completion_date=proposed_state["actual_completion_date"],
                days_delayed=proposed_state["days_delayed"] or 0,
                milestone_status=_normalize_milestone_status(proposed_state["milestone_status"]),
                cost_deviation=proposed_state["cost_deviation"] or Decimal("0.00"),
                progress_gap=proposed_state["progress_gap"] or Decimal("0.00"),
                derived_metrics=proposed_state["derived_metrics"],
                overall_risk_score=proposed_state["overall_risk_score"] or Decimal("0.00"),
                risk_level=proposed_state["risk_level"] or "Low",
                change_summary=comp_result.change_summary_text
            )
            db.add(snapshot)
            db.flush()

            # -----------------------------------------------------------------
            # Step C: Execute Existing Risk Engines
            # (Cost Anomaly, Duplicate, Delay, Fund Utilization, Progress Mismatch, Agency Pattern)
            # -----------------------------------------------------------------
            # 1. Run Engines 1–5 + Aggregation + Explained Risk Engine via RiskEngine
            # commit=False ensures all updates stay in this transaction
            engine_res = self.risk_engine.evaluate(
                project_id=project_id,
                db=db,
                persist=True,  # Updates current RiskScore & RiskFactors
                context=context,
                commit=False
            )

            # 2. Run Fund Utilization Detector explicitly
            fund_res = self.fund_utilization_detector.detect(
                project_id=project_id,
                db=db,
                context=context
            )
            fund_dict = fund_res.to_dict()

            # 3. Assemble complete 6-detector decomposition
            raw_breakdown = {
                item["detector_key"]: item
                for item in engine_res.get("detector_breakdown", [])
            }
            detector_scores = {
                "cost_anomaly": raw_breakdown.get("cost_anomaly", {}),
                "duplicate_detection": raw_breakdown.get("duplicate_detection", {}),
                "delay_detection": raw_breakdown.get("delay_detection", {}),
                "fund_utilization": fund_dict,
                "progress_mismatch": raw_breakdown.get("progress_mismatch", {}),
                "agency_pattern": raw_breakdown.get("agency_pattern", {}),
                "explained_risk": engine_res.get("explained_risk", {})
            }

            computed_overall_score = Decimal(str(round(engine_res["overall_risk_score"], 2)))
            computed_risk_level = _normalize_db_risk_level(engine_res.get("risk_level"))
            sub_scores = engine_res.get("sub_scores", {})
            fund_score = fund_dict.get("score", 0.0)

            # Update snapshot's risk score and level with freshly computed values
            snapshot.overall_risk_score = computed_overall_score
            snapshot.risk_level = computed_risk_level

            # -----------------------------------------------------------------
            # Step D: Store RiskHistory linked to snapshot.snapshot_id
            # -----------------------------------------------------------------
            risk_history = RiskHistory(
                project_id=project_id,
                snapshot_id=snapshot.snapshot_id,
                overall_risk_score=computed_overall_score,
                risk_level=computed_risk_level,
                delay_risk_score=Decimal(str(round(sub_scores.get("delay_risk_score", 0.0), 2))),
                cost_overrun_risk_score=Decimal(str(round(sub_scores.get("cost_overrun_risk_score", 0.0), 2))),
                non_completion_risk_score=Decimal(str(round(sub_scores.get("non_completion_risk_score", 0.0), 2))),
                leakage_risk_score=Decimal(str(round(sub_scores.get("leakage_risk_score", fund_score), 2))),
                detector_scores=detector_scores,
                weights_used=engine_res.get("weights_used"),
                primary_factors=engine_res.get("detector_breakdown"),
                engine_version=engine_res.get("engine_version", "1.0.0"),
                model_version=engine_res.get("model_version", "v1.0"),
                calculated_at=now_dt
            )
            db.add(risk_history)

            # -----------------------------------------------------------------
            # Step E: Log status change audit in ProjectHistory if status changed
            # -----------------------------------------------------------------
            if new_status != old_status:
                history_record = ProjectHistory(
                    project_id=project_id,
                    event_type="Status Changed",
                    previous_status=old_status,
                    new_status=new_status,
                    performed_by=performed_by,
                    event_description=f"Status transitioned from '{old_status}' to '{new_status}' by {performed_by}. {comp_result.change_summary_text}",
                    metadata_json={
                        "snapshot_id": snapshot.snapshot_id,
                        "overall_risk_score": float(computed_overall_score),
                        "risk_level": computed_risk_level
                    }
                )
                db.add(history_record)

            # -----------------------------------------------------------------
            # Step F: Commit transaction atomically
            # -----------------------------------------------------------------
            db.commit()

            message = (
                "Initial baseline project snapshot and risk evaluation recorded upon first ingestion."
                if comp_result.is_initial
                else f"Meaningful project update detected: created snapshot #{snapshot.snapshot_id} and risk calculation #{risk_history.history_id}."
            )

            return UpdateProcessingResult(
                project_id=project_id,
                updated=True,
                historical_update_required=True,
                is_initial=comp_result.is_initial,
                message=message,
                snapshot_id=snapshot.snapshot_id,
                history_id=risk_history.history_id,
                overall_risk_score=float(computed_overall_score),
                risk_level=computed_risk_level,
                change_summary=comp_result.change_summary_text,
                changes_count=comp_result.changes_count,
                detector_scores=detector_scores
            )

        except Exception as e:
            db.rollback()
            logger.error(
                "Transactional project update & risk evaluation failed for '%s'. Rolled back completely: %s",
                project_id, str(e), exc_info=True
            )
            raise


# Global singleton instance
historical_risk_integration_service = HistoricalRiskIntegrationService()
