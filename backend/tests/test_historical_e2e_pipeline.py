"""
backend/tests/test_historical_e2e_pipeline.py
=============================================================================
End-to-End Test Suite for Phase 11 Historical Tracking Pipeline.
=============================================================================

Validates:
1. Creation of a representative project and processing through the ingestion pipeline.
2. Initial state and baseline risk score recording.
3. Multiple simulated updates in chronological sequence:
   - Expenditure increase
   - Physical-progress update
   - Financial-progress update
   - Increased delay and milestone status change
   - Final critical risk-score escalation
4. Verification that each meaningful update produces an immutable ProjectSnapshot
   and corresponding RiskHistory record.
5. Verification that current Project, Financial, and Progress tables hold the latest
   state while previous historical snapshots remain strictly immutable and unchanged.
6. Verification that re-ingesting identical data produces no duplicate snapshots (idempotency).
7. Verification that sub-tolerance numeric jitter does not trigger snapshot creation.
8. Verification that historical API endpoints return records in strict chronological order.
9. Verification of edge cases:
   - First-ever ingestion
   - Missing/partial update values (coalescing existing state)
   - API error handling (404 for missing project, 422 for invalid parameters)
   - Transactional rollback behavior upon failure (zero orphan records left in DB)
=============================================================================
"""

import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select, desc

from app.main import app
from app.database import SessionLocal
from app.models.project import (
    Project, Financial, Progress, RiskScore, RiskFactor,
    ProjectSnapshot, RiskHistory
)
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.project_service import ProjectService
from app.services.historical_risk_integration_service import (
    HistoricalRiskIntegrationService,
    historical_risk_integration_service,
    UpdateProcessingResult
)

client = TestClient(app)


@pytest.fixture(scope="function")
def e2e_db():
    """Provides a dedicated database session for E2E testing with cleanup."""
    db = SessionLocal()
    pid = "MPLADS-E2E-TEST-001"

    # Pre-test cleanup of any previous run
    p = db.get(Project, pid)
    if p:
        db.delete(p)
        db.commit()

    yield db

    # Post-test cleanup
    db.rollback()
    p = db.get(Project, pid)
    if p:
        db.delete(p)
        db.commit()
    db.close()


class TestHistoricalTrackingE2EPipeline:
    """Comprehensive E2E suite for Phase 11 Historical Tracking."""

    def test_complete_e2e_lifecycle_and_immutability(self, e2e_db):
        """
        Executes the full end-to-end lifecycle:
        1. Project creation
        2. First ingestion (baseline snapshot & risk evaluation)
        3. Update 1: Expenditure increase
        4. Update 2: Physical progress advancement
        5. Update 3: Financial progress update
        6. Update 4: Delay increase and schedule slippage
        7. Update 5: Final high-risk escalation
        8. Idempotent re-ingestion of identical state
        9. Immutability audit of all past snapshots
        10. Chronological verification across all historical API endpoints
        """
        pid = "MPLADS-E2E-TEST-001"

        # ---------------------------------------------------------------------
        # Step 1: Create Representative Project via ProjectService
        # ---------------------------------------------------------------------
        create_in = ProjectCreate(
            project_id=pid,
            project_code="E2E-CODE-001",
            project_title="E2E Integrated Skill & Innovation Center",
            project_description="Multipurpose community facility for youth skilling and digital education.",
            sector="Skill Development",
            sub_sector="Vocational Training",
            state_id=34,
            constituency_id=532,
            district_name="Maldaha Uttar District",
            block_name="Chanchal-I",
            implementing_agency="District Rural Development Agency (DRDA)",
            mp_name="Dr. Representative MP",
            house_of_parliament="Lok Sabha",
            current_status="Sanctioned",
            financial_year="2024-25",
            recommendation_date=date(2024, 1, 15),
            sanction_date=date(2024, 2, 1),
            work_order_date=date(2024, 3, 1),
            expected_completion_date=date(2025, 3, 1),
            recommended_amount=Decimal("3000000.00")
        )
        created_detail = ProjectService.create_project(
            db=e2e_db, project_in=create_in, performed_by="E2E System Admin"
        )
        assert created_detail.project_id == pid
        assert created_detail.current_status == "Sanctioned"

        # ---------------------------------------------------------------------
        # Step 2: First Ingestion (Initial Baseline Snapshot & Risk Calculation)
        # ---------------------------------------------------------------------
        baseline_payload = {
            "project_status": "Sanctioned",
            "sanctioned_amount": Decimal("3000000.00"),
            "released_amount": Decimal("1500000.00"),
            "expenditure_amount": Decimal("150000.00"),
            "physical_progress_pct": Decimal("5.00"),
            "financial_progress_pct": Decimal("5.00"),
            "days_delayed": 0,
            "milestone_status": "On Track"
        }
        res_baseline: UpdateProcessingResult = historical_risk_integration_service.process_project_update_transactional(
            db=e2e_db,
            project_id=pid,
            update_payload=baseline_payload,
            performed_by="Baseline Ingester"
        )

        assert res_baseline.updated is True
        assert res_baseline.historical_update_required is True
        assert res_baseline.is_initial is True
        assert res_baseline.snapshot_id is not None
        assert res_baseline.history_id is not None
        snap1_id = res_baseline.snapshot_id
        hist1_id = res_baseline.history_id
        baseline_score = res_baseline.overall_risk_score
        assert baseline_score is not None
        assert 0.0 <= baseline_score <= 100.0

        # Snapshot #1 Verification in DB
        snap1 = e2e_db.get(ProjectSnapshot, snap1_id)
        assert snap1 is not None
        assert snap1.project_status == "Sanctioned"
        assert snap1.sanctioned_amount == Decimal("3000000.00")
        assert snap1.expenditure_amount == Decimal("150000.00")
        assert snap1.physical_progress_pct == Decimal("5.00")
        assert snap1.days_delayed == 0
        assert snap1.milestone_status == "On Track"
        assert float(snap1.overall_risk_score) == pytest.approx(baseline_score, 0.01)

        # ---------------------------------------------------------------------
        # Step 3: Update 1 — Expenditure Increase
        # (Status moves to In Progress, expenditure jumps from 1.5L to 10L)
        # ---------------------------------------------------------------------
        update1_payload = {
            "current_status": "In Progress",
            "released_amount": Decimal("1500000.00"),
            "expenditure_amount": Decimal("1000000.00"),
            "physical_progress_pct": Decimal("12.00"),
            "financial_progress_pct": Decimal("33.33"),
            "days_delayed": 0,
            "milestone_status": "On Track"
        }
        res_up1 = historical_risk_integration_service.process_project_update_transactional(
            db=e2e_db,
            project_id=pid,
            update_payload=update1_payload,
            performed_by="Financial Officer"
        )

        assert res_up1.updated is True
        assert res_up1.historical_update_required is True
        assert res_up1.is_initial is False
        assert res_up1.snapshot_id is not None and res_up1.snapshot_id > snap1_id
        snap2_id = res_up1.snapshot_id
        snap2 = e2e_db.get(ProjectSnapshot, snap2_id)
        assert snap2.expenditure_amount == Decimal("1000000.00")
        assert snap2.project_status == "In Progress"

        # ---------------------------------------------------------------------
        # Step 4: Update 2 — Physical-Progress Update
        # (Physical progress advances significantly to 40% after ground inspection)
        # ---------------------------------------------------------------------
        update2_payload = {
            "current_status": "In Progress",
            "expenditure_amount": Decimal("1100000.00"),
            "physical_progress_pct": Decimal("40.00"),
            "financial_progress_pct": Decimal("36.67"),
            "days_delayed": 0,
            "milestone_status": "On Track"
        }
        res_up2 = historical_risk_integration_service.process_project_update_transactional(
            db=e2e_db,
            project_id=pid,
            update_payload=update2_payload,
            performed_by="Site Engineer"
        )

        assert res_up2.historical_update_required is True
        snap3_id = res_up2.snapshot_id
        snap3 = e2e_db.get(ProjectSnapshot, snap3_id)
        assert snap3.physical_progress_pct == Decimal("40.00")

        # ---------------------------------------------------------------------
        # Step 5: Update 3 — Financial-Progress Update
        # (Second tranche released, expenditure reaches 22L, financial progress 73.3%)
        # ---------------------------------------------------------------------
        update3_payload = {
            "current_status": "In Progress",
            "released_amount": Decimal("2800000.00"),
            "expenditure_amount": Decimal("2200000.00"),
            "physical_progress_pct": Decimal("45.00"),
            "financial_progress_pct": Decimal("73.33"),
            "days_delayed": 15,
            "milestone_status": "On Track"
        }
        res_up3 = historical_risk_integration_service.process_project_update_transactional(
            db=e2e_db,
            project_id=pid,
            update_payload=update3_payload,
            performed_by="Accounts Department"
        )

        assert res_up3.historical_update_required is True
        snap4_id = res_up3.snapshot_id
        snap4 = e2e_db.get(ProjectSnapshot, snap4_id)
        assert snap4.expenditure_amount == Decimal("2200000.00")
        assert snap4.financial_progress_pct == Decimal("73.33")

        # ---------------------------------------------------------------------
        # Step 6: Update 4 — Increased Delay & Schedule Slippage
        # (Project hits serious delays: 120 days overdue, milestone marked Delayed)
        # ---------------------------------------------------------------------
        update4_payload = {
            "current_status": "In Progress",
            "expenditure_amount": Decimal("2300000.00"),
            "physical_progress_pct": Decimal("50.00"),
            "financial_progress_pct": Decimal("76.67"),
            "days_delayed": 120,
            "milestone_status": "Delayed"
        }
        res_up4 = historical_risk_integration_service.process_project_update_transactional(
            db=e2e_db,
            project_id=pid,
            update_payload=update4_payload,
            performed_by="Monitoring Cell"
        )

        assert res_up4.historical_update_required is True
        snap5_id = res_up4.snapshot_id
        snap5 = e2e_db.get(ProjectSnapshot, snap5_id)
        assert snap5.days_delayed == 120
        assert snap5.milestone_status == "Delayed"
        # Delay score in risk history should now reflect delay detection
        rh5 = e2e_db.execute(select(RiskHistory).where(RiskHistory.snapshot_id == snap5_id)).scalars().first()
        assert rh5 is not None
        assert rh5.detector_scores["delay_detection"]["score"] > 0

        # ---------------------------------------------------------------------
        # Step 7: Update 5 — Final Risk-Score Escalation
        # (Cost overrun: expenditure 35L > sanctioned 30L, 400 days delay, Critical)
        # ---------------------------------------------------------------------
        update5_payload = {
            "current_status": "In Progress",
            "released_amount": Decimal("3000000.00"),
            "expenditure_amount": Decimal("3500000.00"),  # ₹5,00,000 cost overrun
            "physical_progress_pct": Decimal("55.00"),
            "financial_progress_pct": Decimal("100.00"),
            "days_delayed": 400,
            "milestone_status": "Critical"
        }
        res_up5 = historical_risk_integration_service.process_project_update_transactional(
            db=e2e_db,
            project_id=pid,
            update_payload=update5_payload,
            performed_by="Audit Directorate"
        )

        assert res_up5.historical_update_required is True
        snap6_id = res_up5.snapshot_id
        snap6 = e2e_db.get(ProjectSnapshot, snap6_id)
        assert snap6.days_delayed == 400
        assert snap6.milestone_status == "Critical"
        assert snap6.cost_overrun_amount == Decimal("500000.00")
        assert float(snap6.overall_risk_score) > float(snap1.overall_risk_score)

        # ---------------------------------------------------------------------
        # Step 8: Verify Immutability of All Previous Snapshots
        # ---------------------------------------------------------------------
        # Re-fetch all snapshots from DB
        all_snaps = e2e_db.execute(
            select(ProjectSnapshot)
            .where(ProjectSnapshot.project_id == pid)
            .order_by(ProjectSnapshot.snapshot_id)
        ).scalars().all()

        assert len(all_snaps) == 6

        # Check Snapshot #1 has its original baseline values
        s1 = all_snaps[0]
        assert s1.snapshot_id == snap1_id
        assert s1.project_status == "Sanctioned"
        assert s1.expenditure_amount == Decimal("150000.00")
        assert s1.physical_progress_pct == Decimal("5.00")
        assert s1.days_delayed == 0
        assert s1.milestone_status == "On Track"

        # Check Snapshot #2
        s2 = all_snaps[1]
        assert s2.snapshot_id == snap2_id
        assert s2.expenditure_amount == Decimal("1000000.00")
        assert s2.physical_progress_pct == Decimal("12.00")

        # Check Snapshot #3
        s3 = all_snaps[2]
        assert s3.snapshot_id == snap3_id
        assert s3.physical_progress_pct == Decimal("40.00")

        # Check Snapshot #4
        s4 = all_snaps[3]
        assert s4.snapshot_id == snap4_id
        assert s4.expenditure_amount == Decimal("2200000.00")

        # Check Snapshot #5
        s5 = all_snaps[4]
        assert s5.snapshot_id == snap5_id
        assert s5.days_delayed == 120
        assert s5.milestone_status == "Delayed"

        # Check Snapshot #6 (Latest)
        s6 = all_snaps[5]
        assert s6.snapshot_id == snap6_id
        assert s6.days_delayed == 400
        assert s6.cost_overrun_amount == Decimal("500000.00")

        # ---------------------------------------------------------------------
        # Step 9: Verify Current Live Project Matches Latest State (#6)
        # ---------------------------------------------------------------------
        live_proj = e2e_db.get(Project, pid)
        live_fin = e2e_db.execute(select(Financial).where(Financial.project_id == pid)).scalars().first()
        live_prog = e2e_db.execute(
            select(Progress).where(Progress.project_id == pid).order_by(desc(Progress.reported_date))
        ).scalars().first()
        live_risk = e2e_db.execute(select(RiskScore).where(RiskScore.project_id == pid)).scalars().first()

        assert live_proj.current_status == "In Progress"
        assert live_fin.expenditure_amount == Decimal("3500000.00")
        assert live_fin.cost_overrun_amount == Decimal("500000.00")
        assert live_prog.physical_progress_pct == Decimal("55.00")
        assert live_prog.days_delayed == 400
        assert live_prog.milestone_status == "Critical"
        assert float(live_risk.overall_risk_score) == pytest.approx(float(snap6.overall_risk_score), 0.01)

        # ---------------------------------------------------------------------
        # Step 10: Idempotent Re-Ingestion (Identical Data & Jitter)
        # ---------------------------------------------------------------------
        # Repeated identical ingestion
        res_repeat = historical_risk_integration_service.process_project_update_transactional(
            db=e2e_db,
            project_id=pid,
            update_payload=update5_payload,
            performed_by="Automated Scheduler (Duplicate)"
        )
        assert res_repeat.historical_update_required is False
        assert res_repeat.changes_count == 0
        assert res_repeat.snapshot_id == snap6_id

        # Insignificant jitter (₹0.50 difference, 0.05% progress difference)
        jitter_payload = dict(update5_payload)
        jitter_payload["expenditure_amount"] = Decimal("3500000.50")
        jitter_payload["physical_progress_pct"] = Decimal("55.05")
        res_jitter = historical_risk_integration_service.process_project_update_transactional(
            db=e2e_db,
            project_id=pid,
            update_payload=jitter_payload,
            performed_by="Sensor Poller (Jitter)"
        )
        assert res_jitter.historical_update_required is False

        # Total snapshots count in DB MUST still be exactly 6!
        snaps_after_dups = e2e_db.execute(
            select(ProjectSnapshot).where(ProjectSnapshot.project_id == pid)
        ).scalars().all()
        assert len(snaps_after_dups) == 6
        e2e_db.commit()

        # ---------------------------------------------------------------------
        # Step 11: Chronological Verification via API Endpoints
        # ---------------------------------------------------------------------
        # A. GET /projects/{id}/history?sort_order=asc
        r_hist_asc = client.get(f"/projects/{pid}/history?sort_order=asc")

        assert r_hist_asc.status_code == 200
        hist_asc_data = r_hist_asc.json()
        assert len(hist_asc_data) == 6
        assert [s["snapshot_id"] for s in hist_asc_data] == [snap1_id, snap2_id, snap3_id, snap4_id, snap5_id, snap6_id]

        # B. GET /projects/{id}/history?sort_order=desc
        r_hist_desc = client.get(f"/projects/{pid}/history?sort_order=desc")
        assert r_hist_desc.status_code == 200
        hist_desc_data = r_hist_desc.json()
        assert len(hist_desc_data) == 6
        assert [s["snapshot_id"] for s in hist_desc_data] == [snap6_id, snap5_id, snap4_id, snap3_id, snap2_id, snap1_id]

        # C. GET /projects/{id}/risk-history?sort_order=asc
        r_risk = client.get(f"/projects/{pid}/risk-history?sort_order=asc")
        assert r_risk.status_code == 200
        risk_data = r_risk.json()
        assert len(risk_data) == 6
        for r_item in risk_data:
            assert "detector_scores" in r_item
            assert "cost_anomaly" in r_item["detector_scores"]
            assert "delay_detection" in r_item["detector_scores"]
            assert "progress_mismatch" in r_item["detector_scores"]
            assert "fund_utilization" in r_item["detector_scores"]
            assert "duplicate_detection" in r_item["detector_scores"]
            assert "agency_pattern" in r_item["detector_scores"]

        # D. GET /projects/{id}/changes?sort_order=asc
        r_changes = client.get(f"/projects/{pid}/changes?sort_order=asc")
        assert r_changes.status_code == 200
        changes_data = r_changes.json()
        assert len(changes_data) == 6
        assert changes_data[0]["previous_snapshot_id"] is None
        assert changes_data[0]["changes_count"] == 1  # Initial baseline
        assert changes_data[5]["previous_snapshot_id"] == snap5_id
        assert changes_data[5]["changes_count"] > 0

        # E. POST /projects/{id}/updates (Ingestion API Endpoint)
        # Test updating via the new HTTP ingestion endpoint
        http_update = {
            "physical_progress_pct": 65.0,
            "financial_progress_pct": 100.0,
            "days_delayed": 420,
            "milestone_status": "Critical"
        }
        r_post_update = client.post(f"/projects/{pid}/updates", json=http_update)
        assert r_post_update.status_code == 200
        post_res = r_post_update.json()
        assert post_res["project_id"] == pid
        assert post_res["updated"] is True
        assert post_res["historical_update_required"] is True
        assert post_res["snapshot_id"] > snap6_id


class TestHistoricalTrackingEdgeCases:
    """Tests for edge cases: missing values, API errors, and rollback behavior."""

    def test_missing_values_and_partial_update(self, e2e_db):
        """Verifies that missing or omitted fields cleanly coalesce with existing data."""
        pid = "MPLADS-E2E-TEST-001"

        # Create base project
        create_in = ProjectCreate(
            project_id=pid,
            project_code="E2E-CODE-002",
            project_title="Partial Values Test Project",
            sector="Education",
            state_id=34,
            constituency_id=532,
            district_name="Maldaha Uttar District",
            implementing_agency="District Rural Development Agency (DRDA)",
            mp_name="Test MP",
            house_of_parliament="Lok Sabha",
            current_status="Sanctioned",
            financial_year="2024-25",
            recommendation_date=date(2024, 1, 15),
            recommended_amount=Decimal("1000000.00")
        )
        ProjectService.create_project(db=e2e_db, project_in=create_in)

        # First ingestion with only a subset of fields
        partial_initial = {
            "expenditure_amount": Decimal("200000.00"),
            "physical_progress_pct": Decimal("10.00")
        }
        res_initial = historical_risk_integration_service.process_project_update_transactional(
            db=e2e_db,
            project_id=pid,
            update_payload=partial_initial
        )
        assert res_initial.is_initial is True
        assert res_initial.historical_update_required is True

        # Incremental update with ONLY physical_progress_pct specified
        partial_next = {
            "physical_progress_pct": Decimal("25.00")
        }
        res_next = historical_risk_integration_service.process_project_update_transactional(
            db=e2e_db,
            project_id=pid,
            update_payload=partial_next
        )
        assert res_next.historical_update_required is True
        snap_next = e2e_db.get(ProjectSnapshot, res_next.snapshot_id)
        # Expenditure should have coalesced from the financial record (200,000.00)
        assert snap_next.expenditure_amount == Decimal("200000.00")
        assert snap_next.physical_progress_pct == Decimal("25.00")

    def test_api_errors_and_edge_cases(self):
        """Verifies 404, 422, and empty-state error responses across all historical endpoints."""
        # 1. 404 for unknown project
        assert client.get("/projects/NON-EXISTENT-ID/history").status_code == 404
        assert client.get("/projects/NON-EXISTENT-ID/risk-history").status_code == 404
        assert client.get("/projects/NON-EXISTENT-ID/changes").status_code == 404
        assert client.post("/projects/NON-EXISTENT-ID/updates", json={"physical_progress_pct": 50}).status_code == 404

        # 2. 422 for invalid sort_order
        r_invalid_sort = client.get("/projects/MPLADS-2024-0002/history?sort_order=invalid_sort")
        assert r_invalid_sort.status_code == 422

        # 3. Project with 0 snapshots returns 200 with []
        r_empty = client.get("/projects/MPLADS-2024-0011/history")
        assert r_empty.status_code == 200
        assert r_empty.json() == []

    def test_transactional_rollback_on_calculation_fault(self, e2e_db):
        """
        Verifies that any unexpected error during risk calculation or snapshot persistence
        completely rolls back the database transaction, leaving zero partial or orphan records.
        """
        pid = "MPLADS-E2E-TEST-001"

        # Create base project
        create_in = ProjectCreate(
            project_id=pid,
            project_code="E2E-CODE-003",
            project_title="Rollback Test Project",
            sector="Health",
            state_id=34,
            constituency_id=532,
            district_name="Maldaha Uttar District",
            implementing_agency="District Rural Development Agency (DRDA)",
            mp_name="Test MP",
            house_of_parliament="Lok Sabha",
            current_status="Sanctioned",
            financial_year="2024-25",
            recommendation_date=date(2024, 1, 15),
            recommended_amount=Decimal("2000000.00")
        )
        ProjectService.create_project(db=e2e_db, project_in=create_in)


        # Create initial snapshot
        historical_risk_integration_service.process_project_update_transactional(
            db=e2e_db,
            project_id=pid,
            update_payload={"expenditure_amount": Decimal("100000.00"), "physical_progress_pct": Decimal("5.00")}
        )

        orig_snaps_count = len(e2e_db.execute(select(ProjectSnapshot).where(ProjectSnapshot.project_id == pid)).scalars().all())
        orig_risk_count = len(e2e_db.execute(select(RiskHistory).where(RiskHistory.project_id == pid)).scalars().all())
        assert orig_snaps_count == 1
        assert orig_risk_count == 1

        # Simulate a faulty risk engine that raises an unhandled exception
        class FaultyRiskEngine:
            def evaluate(self, *args, **kwargs):
                raise RuntimeError("Simulated catastrophic failure in risk aggregation calculation!")

        faulty_service = HistoricalRiskIntegrationService(risk_engine=FaultyRiskEngine())

        # Attempt to process update with faulty engine
        with pytest.raises(RuntimeError, match="Simulated catastrophic failure"):
            faulty_service.process_project_update_transactional(
                db=e2e_db,
                project_id=pid,
                update_payload={
                    "current_status": "In Progress",
                    "expenditure_amount": Decimal("800000.00"),
                    "physical_progress_pct": Decimal("40.00")
                }
            )

        # Verify transaction was completely rolled back:
        # 1. No new snapshot was committed
        snaps_after = e2e_db.execute(select(ProjectSnapshot).where(ProjectSnapshot.project_id == pid)).scalars().all()
        assert len(snaps_after) == orig_snaps_count

        # 2. No new risk history was committed
        risk_after = e2e_db.execute(select(RiskHistory).where(RiskHistory.project_id == pid)).scalars().all()
        assert len(risk_after) == orig_risk_count

        # 3. Project status was NOT mutated
        p = e2e_db.get(Project, pid)
        assert p.current_status == "Sanctioned"
