"""
backend/tests/test_historical_idempotency.py
=============================================================================
Test Suite for Idempotent Phase 11 Historical Tracking Pipeline.
=============================================================================

Verifies:
1. Repeated identical ingestion creates zero duplicate snapshots or risk histories.
2. Returns structured response with historical_update_required=False on duplicate.
3. Repeated changed-data ingestion creates exactly one snapshot and one risk calculation per change.
4. Database unique index (uq_risk_history_snapshot_id) strictly prevents duplicate risk records.
5. Numeric sub-tolerance jitter does not create redundant snapshots.
6. Concurrent / race-condition requests for the same project serialize cleanly with zero duplicates.
"""

import pytest
import concurrent.futures
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.project import (
    Project, Financial, Progress, RiskScore, RiskFactor,
    ProjectSnapshot, RiskHistory, ProjectHistory
)
from app.services.historical_risk_integration_service import (
    HistoricalRiskIntegrationService,
    historical_risk_integration_service,
    UpdateProcessingResult
)


@pytest.fixture(scope="function")
def db():
    """Provides an isolated database session."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def idempotent_test_project(db):
    """Creates a dedicated isolated project for idempotency testing and tears it down afterward."""
    pid = "MPLADS-IDEMP-TEST-01"
    
    # Clean up any leftover records
    existing = db.get(Project, pid)
    if existing:
        db.delete(existing)
        db.commit()

    proj = Project(
        project_id=pid,
        project_code="TEST-IDEMP-01",
        project_title="Idempotency Test Solar Drinking Water Plant",
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
        recommended_amount=Decimal("3000000.00"),
        sanctioned_amount=Decimal("3000000.00"),
        released_amount=Decimal("2000000.00"),
        expenditure_amount=Decimal("500000.00"),
        utilization_rate_pct=Decimal("25.00")
    )
    db.add(fin)

    prog = Progress(
        project_id=pid,
        reported_date=date(2024, 8, 1),
        physical_progress_pct=Decimal("20.00"),
        financial_progress_pct=Decimal("16.67"),
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


class TestHistoricalIdempotency:
    """Tests the idempotency guarantees of the Phase 11 historical update pipeline."""

    def test_repeated_identical_ingestion_creates_no_duplicates(self, db, idempotent_test_project):
        """
        Verifies that repeated ingestion of identical project data creates exactly ONE
        initial snapshot, and subsequent calls return historical_update_required=False
        without inserting duplicate snapshots or duplicate risk-history records.
        """
        pid = idempotent_test_project.project_id

        payload = {
            "current_status": "Sanctioned",
            "sanctioned_amount": Decimal("3000000.00"),
            "released_amount": Decimal("2000000.00"),
            "expenditure_amount": Decimal("500000.00"),
            "physical_progress_pct": Decimal("20.00"),
            "financial_progress_pct": Decimal("16.67"),
            "milestone_status": "On Track"
        }

        # 1. First Ingestion: Creates initial baseline snapshot & risk calculation
        res1: UpdateProcessingResult = historical_risk_integration_service.process_project_update_transactional(
            db=db, project_id=pid, update_payload=payload, performed_by="Idempotency Ingester"
        )

        assert res1.updated is True
        assert res1.historical_update_required is True
        assert res1.is_initial is True
        assert res1.snapshot_id is not None
        assert res1.history_id is not None
        assert res1.changes_count >= 1
        initial_snap_id = res1.snapshot_id
        initial_hist_id = res1.history_id

        # Verify initial record in database
        snap_count = db.execute(
            select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
        ).scalar()
        risk_count = db.execute(
            select(func.count(RiskHistory.history_id)).where(RiskHistory.project_id == pid)
        ).scalar()
        assert snap_count == 1
        assert risk_count == 1

        # 2. Repeated Ingestions: Ingest the EXACT same data 5 times in succession
        for iteration in range(1, 6):
            res_repeat: UpdateProcessingResult = historical_risk_integration_service.process_project_update_transactional(
                db=db, project_id=pid, update_payload=payload, performed_by=f"Repeated Ingester #{iteration}"
            )

            # Assert response explicitly flags that no historical update was required
            assert res_repeat.historical_update_required is False, f"Iteration {iteration} incorrectly flagged update required"
            assert res_repeat.updated is False, f"Iteration {iteration} incorrectly marked updated"
            assert res_repeat.changes_count == 0
            assert res_repeat.snapshot_id == initial_snap_id, f"Iteration {iteration} returned wrong snapshot_id"
            assert res_repeat.history_id == initial_hist_id, f"Iteration {iteration} returned wrong history_id"
            assert "no historical update was required" in res_repeat.message.lower()

            # Assert database snapshot and risk_history counts REMAIN 1
            current_snap_count = db.execute(
                select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
            ).scalar()
            current_risk_count = db.execute(
                select(func.count(RiskHistory.history_id)).where(RiskHistory.project_id == pid)
            ).scalar()

            assert current_snap_count == 1, f"Iteration {iteration} created duplicate snapshot! Total: {current_snap_count}"
            assert current_risk_count == 1, f"Iteration {iteration} created duplicate risk_history! Total: {current_risk_count}"

    def test_repeated_changed_data_ingestion(self, db, idempotent_test_project):
        """
        Verifies that when meaningful changes occur, exactly ONE snapshot and ONE risk_history
        are created, and repeating THAT same changed state produces no duplicates.
        """
        pid = idempotent_test_project.project_id

        # Step 0: Baseline
        res0 = historical_risk_integration_service.process_project_update_transactional(
            db=db, project_id=pid, update_payload={"current_status": "Sanctioned"}, force_snapshot=True
        )
        assert res0.historical_update_required is True
        baseline_snap_id = res0.snapshot_id
        baseline_hist_id = res0.history_id

        # ---------------------------------------------------------------------
        # Change 1: Increase expenditure & progress
        # ---------------------------------------------------------------------
        change_payload_1 = {
            "current_status": "In Progress",
            "expenditure_amount": Decimal("1200000.00"),  # Meaningful jump from 500k
            "physical_progress_pct": Decimal("40.00")
        }

        res_change_1 = historical_risk_integration_service.process_project_update_transactional(
            db=db, project_id=pid, update_payload=change_payload_1
        )
        assert res_change_1.historical_update_required is True
        assert res_change_1.snapshot_id != baseline_snap_id
        assert res_change_1.history_id != baseline_hist_id
        snap_id_1 = res_change_1.snapshot_id
        hist_id_1 = res_change_1.history_id

        # Total snapshots now 2
        snap_count_1 = db.execute(
            select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
        ).scalar()
        assert snap_count_1 == 2

        # Ingest Change 1 repeatedly 3 times
        for _ in range(3):
            dup_res = historical_risk_integration_service.process_project_update_transactional(
                db=db, project_id=pid, update_payload=change_payload_1
            )
            assert dup_res.historical_update_required is False
            assert dup_res.snapshot_id == snap_id_1
            assert dup_res.history_id == hist_id_1

        # Count must still be 2
        assert db.execute(
            select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
        ).scalar() == 2

        # ---------------------------------------------------------------------
        # Change 2: Advance to Finishing stage & delay
        # ---------------------------------------------------------------------
        change_payload_2 = {
            "current_status": "In Progress",
            "expenditure_amount": Decimal("1800000.00"),
            "physical_progress_pct": Decimal("85.00"),
            "days_delayed": 30,
            "milestone_status": "Delayed"
        }

        res_change_2 = historical_risk_integration_service.process_project_update_transactional(
            db=db, project_id=pid, update_payload=change_payload_2
        )
        assert res_change_2.historical_update_required is True
        snap_id_2 = res_change_2.snapshot_id
        hist_id_2 = res_change_2.history_id
        assert snap_id_2 not in (baseline_snap_id, snap_id_1)

        # Total snapshots now 3
        assert db.execute(
            select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
        ).scalar() == 3

        # Ingest Change 2 repeatedly 3 times
        for _ in range(3):
            dup_res = historical_risk_integration_service.process_project_update_transactional(
                db=db, project_id=pid, update_payload=change_payload_2
            )
            assert dup_res.historical_update_required is False
            assert dup_res.snapshot_id == snap_id_2
            assert dup_res.history_id == hist_id_2

        # Count must still be 3
        assert db.execute(
            select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
        ).scalar() == 3

    def test_database_unique_constraint_prevents_duplicate_risk_history(self, db, idempotent_test_project):
        """
        Verifies that PostgreSQL unique index `uq_risk_history_snapshot_id` enforces
        at the database schema level that two risk_history records cannot be linked to
        the same snapshot_id.
        """
        pid = idempotent_test_project.project_id

        # Create one snapshot
        res = historical_risk_integration_service.process_project_update_transactional(
            db=db, project_id=pid, update_payload={"current_status": "In Progress"}, force_snapshot=True
        )
        sid = res.snapshot_id
        assert sid is not None

        # Attempt to insert a second RiskHistory referencing the same snapshot_id
        duplicate_rh = RiskHistory(
            project_id=pid,
            snapshot_id=sid,
            overall_risk_score=Decimal("50.00"),
            risk_level="Medium",
            delay_risk_score=Decimal("10.00"),
            cost_overrun_risk_score=Decimal("10.00"),
            non_completion_risk_score=Decimal("10.00"),
            leakage_risk_score=Decimal("10.00"),
            detector_scores={"duplicate_attempt": True},
            calculated_at=datetime.now(timezone.utc)
        )
        db.add(duplicate_rh)

        with pytest.raises(IntegrityError) as exc_info:
            db.commit()

        db.rollback()
        assert "uq_risk_history_snapshot_id" in str(exc_info.value) or "unique" in str(exc_info.value).lower()

    def test_sub_tolerance_jitter_treated_as_idempotent_no_op(self, db, idempotent_test_project):
        """
        Verifies that subtle numeric jitter below tolerances (₹0.50, 0.05% progress)
        returns historical_update_required=False and does not create snapshots.
        """
        pid = idempotent_test_project.project_id

        # Baseline
        res_base = historical_risk_integration_service.process_project_update_transactional(
            db=db, project_id=pid, update_payload={"current_status": "In Progress"}, force_snapshot=True
        )
        base_snap = db.get(ProjectSnapshot, res_base.snapshot_id)

        # Send jittery payload
        jitter_payload = {
            "current_status": "In Progress",
            "expenditure_amount": base_snap.expenditure_amount + Decimal("0.45"),  # < ₹1.00
            "physical_progress_pct": base_snap.physical_progress_pct + Decimal("0.04")  # < 0.10%
        }

        res_jitter = historical_risk_integration_service.process_project_update_transactional(
            db=db, project_id=pid, update_payload=jitter_payload
        )

        assert res_jitter.historical_update_required is False
        assert res_jitter.updated is False
        assert res_jitter.snapshot_id == base_snap.snapshot_id
        assert res_jitter.changes_count == 0

    def test_concurrent_identical_ingestion_race_condition_safety(self, idempotent_test_project):
        """
        Simulates 5 concurrent threads attempting to ingest the identical project update
        at the exact same moment. Verifies that advisory locks and row locks serialize
        the requests, resulting in EXACTLY ONE snapshot and ONE risk_history created.
        """
        pid = idempotent_test_project.project_id

        update_payload = {
            "current_status": "In Progress",
            "expenditure_amount": Decimal("1500000.00"),
            "physical_progress_pct": Decimal("55.00"),
            "milestone_status": "On Track"
        }

        def worker_task(worker_id: int):
            worker_db = SessionLocal()
            try:
                result = historical_risk_integration_service.process_project_update_transactional(
                    db=worker_db,
                    project_id=pid,
                    update_payload=update_payload,
                    performed_by=f"Concurrent Worker #{worker_id}"
                )
                return {
                    "worker_id": worker_id,
                    "updated": result.updated,
                    "update_required": result.historical_update_required,
                    "snapshot_id": result.snapshot_id,
                    "history_id": result.history_id
                }
            finally:
                worker_db.close()

        # Execute 5 concurrent threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_task, i) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Inspect thread outcomes
        required_updates = [r for r in results if r["update_required"] is True]
        skipped_updates = [r for r in results if r["update_required"] is False]

        # Exactly ONE worker should have triggered the historical snapshot creation
        assert len(required_updates) == 1, f"Expected exactly 1 thread to perform update, but got {len(required_updates)}"
        assert len(skipped_updates) == 4, f"Expected 4 threads to be skipped as duplicates, but got {len(skipped_updates)}"

        # All workers must agree on the same snapshot_id
        canonical_snapshot_id = required_updates[0]["snapshot_id"]
        for r in results:
            assert r["snapshot_id"] == canonical_snapshot_id

        # Verify database has strictly 1 snapshot and 1 risk history
        verify_db = SessionLocal()
        try:
            total_snaps = verify_db.execute(
                select(func.count(ProjectSnapshot.snapshot_id)).where(ProjectSnapshot.project_id == pid)
            ).scalar()
            total_risks = verify_db.execute(
                select(func.count(RiskHistory.history_id)).where(RiskHistory.project_id == pid)
            ).scalar()

            assert total_snaps == 1, f"Database has {total_snaps} snapshots instead of 1!"
            assert total_risks == 1, f"Database has {total_risks} risk histories instead of 1!"
        finally:
            verify_db.close()
