"""
backend/tests/test_historical_risk_integration.py
=============================================================================
Unit and integration tests for Phase 11 Historical Risk Engine Integration:
1. Meaningful update triggers immutable snapshot creation.
2. Complete execution of all 6 risk engines (cost anomaly, duplicate detection,
   delay detection, fund utilization, progress mismatch, agency pattern) + risk aggregation.
3. Persistence of composite risk score, risk level, and detector scores in risk_history
   linked directly to the snapshot.
4. Live project record update strictly after snapshot and risk calculation succeed.
5. Immutability guarantee: previous snapshots and risk calculations are never modified.
6. Atomic transactionality: full rollback on risk engine failure leaves no orphan snapshots.
7. Insignificant changes within tolerance do not create redundant snapshots.
8. End-to-end ProjectService.update_project integration.
=============================================================================
"""

import pytest
from datetime import datetime, date, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from sqlalchemy import select, desc, func

from app.database import SessionLocal
from app.models.project import (
    Project, Financial, Progress, RiskScore, RiskFactor,
    ProjectSnapshot, RiskHistory, ProjectHistory
)
from app.schemas.project import ProjectUpdate
from app.services.historical_risk_integration_service import (
    HistoricalRiskIntegrationService,
    historical_risk_integration_service,
    UpdateProcessingResult
)
from app.services.project_service import ProjectService


@pytest.fixture(scope="function")
def db():
    """Yields a database session for each test."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def sample_project(db):
    """Creates a dedicated isolated project for testing and tears it down afterward."""
    pid = "MPLADS-HIST-TEST-99"
    # Ensure any previous residue is removed
    existing = db.get(Project, pid)
    if existing:
        db.delete(existing)
        db.commit()

    # Create new isolated project
    proj = Project(
        project_id=pid,
        project_code="TEST-HIST-99",
        project_title="Integration Test Health Clinic",
        sector="Drinking Water",
        state_id=34,
        constituency_id=532,
        district_name="Maldaha Uttar District",
        implementing_agency="District Rural Development Agency (DRDA)",
        mp_name="Test MP",
        house_of_parliament="Lok Sabha",
        current_status="Sanctioned",
        financial_year="2024-25",
        recommendation_date=date(2024, 5, 1),
        sanction_date=date(2024, 6, 1),
        expected_completion_date=date(2025, 6, 1)
    )
    db.add(proj)
    db.flush()

    fin = Financial(
        project_id=pid,
        recommended_amount=Decimal("2000000.00"),
        sanctioned_amount=Decimal("2000000.00"),
        released_amount=Decimal("1500000.00"),
        expenditure_amount=Decimal("500000.00"),
        utilization_rate_pct=Decimal("33.33")
    )
    db.add(fin)

    prog = Progress(
        project_id=pid,
        reported_date=date(2024, 8, 1),
        physical_progress_pct=Decimal("25.00"),
        financial_progress_pct=Decimal("25.00"),
        current_stage="Foundation",
        milestone_status="On Track"
    )
    db.add(prog)
    db.commit()

    db.refresh(proj)
    yield proj

    # Teardown: delete project and all cascading relationships
    try:
        cleanup_proj = db.get(Project, pid)
        if cleanup_proj:
            db.delete(cleanup_proj)
            db.commit()
    except Exception:
        db.rollback()


class TestHistoricalRiskIntegration:
    """Verifies transactional historical snapshotting linked to the 6-detector risk engine."""

    def test_meaningful_update_creates_snapshot_and_risk_history(self, db, sample_project):
        """
        Verifies that a meaningful update creates an immutable snapshot, executes all 6
        risk engines, stores detector scores in risk_history linked to snapshot, and updates project.
        """
        pid = sample_project.project_id

        # Record baseline counts
        snap_count_before = db.execute(
            select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
        ).scalar() or 0

        risk_count_before = db.execute(
            select(func.count(RiskHistory.history_id)).where(RiskHistory.project_id == pid)
        ).scalar() or 0

        # Fetch current financial to create a meaningful financial update
        fin = db.execute(select(Financial).where(Financial.project_id == pid)).scalars().first()
        base_exp = fin.expenditure_amount if fin and fin.expenditure_amount else Decimal("100000.00")
        new_exp = base_exp + Decimal("75000.00")  # Significant monetary change (> tolerance)

        update_payload = {
            "current_status": "In Progress",
            "expenditure_amount": new_exp,
            "physical_progress_pct": Decimal("45.50"),
            "days_delayed": 15,
            "milestone_status": "Delayed"
        }

        result: UpdateProcessingResult = historical_risk_integration_service.process_project_update_transactional(
            db=db,
            project_id=pid,
            update_payload=update_payload,
            performed_by="Integration Tester"
        )

        assert result.updated is True
        assert result.snapshot_id is not None
        assert result.history_id is not None
        assert result.overall_risk_score is not None
        assert 0.0 <= result.overall_risk_score <= 100.0
        assert result.risk_level in ("Low", "Moderate", "Medium", "High", "Critical")
        assert result.changes_count >= 1

        # 1. Verify snapshot record in database
        snap = db.get(ProjectSnapshot, result.snapshot_id)
        assert snap is not None
        assert snap.project_id == pid
        assert snap.project_status == "In Progress"
        assert snap.expenditure_amount == new_exp
        assert snap.physical_progress_pct == Decimal("45.50")
        assert snap.days_delayed == 15
        assert snap.milestone_status == "Delayed"
        assert float(snap.overall_risk_score) == result.overall_risk_score
        assert snap.risk_level == result.risk_level
        assert len(snap.change_summary) > 0

        # 2. Verify risk_history record linked to snapshot_id
        rh = db.get(RiskHistory, result.history_id)
        assert rh is not None
        assert rh.project_id == pid
        assert rh.snapshot_id == snap.snapshot_id  # Strict foreign key link
        assert float(rh.overall_risk_score) == result.overall_risk_score
        assert rh.risk_level == result.risk_level

        # 3. Verify all 6 modular risk detectors + explained risk are decomposed in detector_scores
        det_scores = rh.detector_scores
        assert isinstance(det_scores, dict)
        assert "cost_anomaly" in det_scores, "Engine 1: cost_anomaly missing from detector_scores"
        assert "duplicate_detection" in det_scores, "Engine 2: duplicate_detection missing"
        assert "delay_detection" in det_scores, "Engine 3: delay_detection missing"
        assert "fund_utilization" in det_scores, "Engine 4 (Fund Utilization) missing"
        assert "progress_mismatch" in det_scores, "Engine 5: progress_mismatch missing"
        assert "agency_pattern" in det_scores, "Engine 6: agency_pattern missing"
        assert "explained_risk" in det_scores, "Explained risk synthesis missing"

        # 4. Verify live project record updated
        db.refresh(sample_project)
        assert sample_project.current_status == "In Progress"

        # 5. Verify counts incremented by exactly 1
        snap_count_after = db.execute(
            select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
        ).scalar() or 0
        risk_count_after = db.execute(
            select(func.count(RiskHistory.history_id)).where(RiskHistory.project_id == pid)
        ).scalar() or 0

        assert snap_count_after == snap_count_before + 1
        assert risk_count_after == risk_count_before + 1

    def test_immutability_of_previous_snapshots_and_risk_history(self, db, sample_project):
        """
        Verifies that subsequent updates NEVER alter prior snapshots or risk calculations.
        All historical rows remain strictly immutable.
        """
        pid = sample_project.project_id

        # Create First Snapshot
        update_1 = {
            "current_status": "In Progress",
            "physical_progress_pct": Decimal("50.00"),
            "expenditure_amount": Decimal("200000.00")
        }
        res_1 = historical_risk_integration_service.process_project_update_transactional(
            db=db, project_id=pid, update_payload=update_1, force_snapshot=True
        )

        snap_1 = db.get(ProjectSnapshot, res_1.snapshot_id)
        rh_1 = db.get(RiskHistory, res_1.history_id)

        # Record exact state of snapshot 1 and risk history 1
        snap_1_values = {
            "snapshot_id": snap_1.snapshot_id,
            "datetime": snap_1.snapshot_datetime,
            "expenditure": snap_1.expenditure_amount,
            "progress": snap_1.physical_progress_pct,
            "risk_score": snap_1.overall_risk_score,
            "change_summary": snap_1.change_summary
        }
        rh_1_values = {
            "history_id": rh_1.history_id,
            "snapshot_id": rh_1.snapshot_id,
            "overall_risk_score": rh_1.overall_risk_score,
            "calculated_at": rh_1.calculated_at,
            "detector_scores": rh_1.detector_scores
        }

        # Create Second Snapshot with different values
        update_2 = {
            "current_status": "Completed",
            "physical_progress_pct": Decimal("100.00"),
            "expenditure_amount": Decimal("350000.00")
        }
        res_2 = historical_risk_integration_service.process_project_update_transactional(
            db=db, project_id=pid, update_payload=update_2
        )

        assert res_2.snapshot_id != res_1.snapshot_id
        assert res_2.history_id != res_1.history_id

        # Re-fetch snapshot 1 and risk history 1 from DB and verify 100% immutability
        db.expire_all()
        re_snap_1 = db.get(ProjectSnapshot, res_1.snapshot_id)
        re_rh_1 = db.get(RiskHistory, res_1.history_id)

        assert re_snap_1.snapshot_id == snap_1_values["snapshot_id"]
        assert re_snap_1.snapshot_datetime == snap_1_values["datetime"]
        assert re_snap_1.expenditure_amount == snap_1_values["expenditure"]
        assert re_snap_1.physical_progress_pct == snap_1_values["progress"]
        assert re_snap_1.overall_risk_score == snap_1_values["risk_score"]
        assert re_snap_1.change_summary == snap_1_values["change_summary"]

        assert re_rh_1.history_id == rh_1_values["history_id"]
        assert re_rh_1.snapshot_id == rh_1_values["snapshot_id"]
        assert re_rh_1.overall_risk_score == rh_1_values["overall_risk_score"]
        assert re_rh_1.calculated_at == rh_1_values["calculated_at"]
        assert re_rh_1.detector_scores == rh_1_values["detector_scores"]

    def test_no_meaningful_change_does_not_create_snapshot(self, db, sample_project):
        """
        Verifies that insignificant changes (below numeric tolerance) do not generate
        superfluous snapshots or risk recalculations.
        """
        pid = sample_project.project_id

        # Fetch latest snapshot to compare against
        latest_snap = db.execute(
            select(ProjectSnapshot)
            .where(ProjectSnapshot.project_id == pid)
            .order_by(desc(ProjectSnapshot.snapshot_datetime), desc(ProjectSnapshot.snapshot_id))
            .limit(1)
        ).scalars().first()

        if not latest_snap:
            # Create a baseline snapshot first
            historical_risk_integration_service.process_project_update_transactional(
                db=db, project_id=pid, update_payload={"current_status": sample_project.current_status}, force_snapshot=True
            )
            latest_snap = db.execute(
                select(ProjectSnapshot)
                .where(ProjectSnapshot.project_id == pid)
                .order_by(desc(ProjectSnapshot.snapshot_datetime), desc(ProjectSnapshot.snapshot_id))
                .limit(1)
            ).scalars().first()

        snap_count_before = db.execute(
            select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
        ).scalar()

        # Submit change below monetary tolerance (< 1000 INR default) and percentage (< 0.5% default)
        insignificant_update = {
            "project_status": latest_snap.project_status,
            "expenditure_amount": latest_snap.expenditure_amount + Decimal("0.50"),
            "physical_progress_pct": latest_snap.physical_progress_pct + Decimal("0.05")
        }

        res = historical_risk_integration_service.process_project_update_transactional(
            db=db,
            project_id=pid,
            update_payload=insignificant_update
        )

        assert res.updated is False
        assert res.changes_count == 0

        # Snapshot count in database must remain unchanged
        snap_count_after = db.execute(
            select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
        ).scalar()
        assert snap_count_after == snap_count_before

    def test_transactional_rollback_on_failure(self, db, sample_project):
        """
        Verifies that if risk calculation or persistence fails, the entire transaction
        rolls back cleanly: no orphan snapshot, no partial risk history, and no master project change.
        """
        pid = sample_project.project_id

        # Baseline counts
        snap_count_before = db.execute(
            select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
        ).scalar() or 0
        risk_count_before = db.execute(
            select(func.count(RiskHistory.history_id)).where(RiskHistory.project_id == pid)
        ).scalar() or 0

        orig_status = sample_project.current_status

        # Create a mock risk engine that crashes on evaluate
        faulty_risk_engine = MagicMock()
        faulty_risk_engine.evaluate.side_effect = RuntimeError("Simulated risk engine hardware/model failure")

        service_with_fault = HistoricalRiskIntegrationService(
            risk_engine=faulty_risk_engine
        )

        # Propose a distinct status change and financial update
        failing_update = {
            "current_status": "Completed" if orig_status != "Completed" else "In Progress",
            "physical_progress_pct": Decimal("100.00"),
            "expenditure_amount": Decimal("999999.00")
        }

        # Assert exception is raised
        with pytest.raises(RuntimeError, match="Simulated risk engine hardware/model failure"):
            service_with_fault.process_project_update_transactional(
                db=db,
                project_id=pid,
                update_payload=failing_update
            )

        # Verify complete transactional rollback
        db.expire_all()

        # 1. No new snapshot created
        snap_count_after = db.execute(
            select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
        ).scalar() or 0
        assert snap_count_after == snap_count_before, "Orphan ProjectSnapshot was committed despite failure!"

        # 2. No partial risk_history created
        risk_count_after = db.execute(
            select(func.count(RiskHistory.history_id)).where(RiskHistory.project_id == pid)
        ).scalar() or 0
        assert risk_count_after == risk_count_before, "Partial RiskHistory was committed despite failure!"

        # 3. Master project record remained in original state
        refreshed_project = db.get(Project, pid)
        assert refreshed_project.current_status == orig_status, "Project status was mutated despite failure!"

    def test_project_service_update_integration(self, db, sample_project):
        """
        Verifies that ProjectService.update_project calls HistoricalRiskIntegrationService
        and returns a fully updated ProjectDetail with updated risk attributes.
        """
        pid = sample_project.project_id

        # Update via ProjectUpdate schema (transition status from Sanctioned to In Progress)
        update_in = ProjectUpdate(
            current_status="In Progress",
            project_description="Updated description via integrated ProjectService update_project."
        )

        project_detail = ProjectService.update_project(
            db=db,
            project_id=pid,
            project_in=update_in,
            performed_by="Project Service Test Runner"
        )

        assert project_detail.project_id == pid
        assert project_detail.current_status == "In Progress"

        # Verify a snapshot and risk_history was created for this update
        latest_snap = db.execute(
            select(ProjectSnapshot)
            .where(ProjectSnapshot.project_id == pid)
            .order_by(desc(ProjectSnapshot.snapshot_datetime), desc(ProjectSnapshot.snapshot_id))
            .limit(1)
        ).scalars().first()

        assert latest_snap is not None
        assert latest_snap.project_status == "In Progress"

        # Verify audit history logged
        hist = db.execute(
            select(ProjectHistory)
            .where(ProjectHistory.project_id == pid)
            .order_by(desc(ProjectHistory.event_timestamp))
            .limit(1)
        ).scalars().first()

        assert hist is not None
        assert hist.event_type == "Status Changed"
        assert hist.new_status == "In Progress"
