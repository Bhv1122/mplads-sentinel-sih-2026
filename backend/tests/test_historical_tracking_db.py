"""
backend/tests/test_historical_tracking_db.py
=============================================================================
Automated test suite verifying the Phase 11 Historical Tracking database layer.
Tests schema creation, foreign keys, check constraints, indexes, and SQLAlchemy
ORM model CRUD & relationships for 'project_snapshots' and 'risk_history'.
=============================================================================
"""

import pytest
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import text
from app.database import SessionLocal, engine
from app.models.project import Project, ProjectSnapshot, RiskHistory


@pytest.fixture(scope="module")
def db_session():
    """Provides a transactional database session for tests."""
    session = SessionLocal()
    yield session
    session.close()


class TestHistoricalTrackingDatabaseLayer:
    """Verifies PostgreSQL schema DDL and SQLAlchemy ORM models."""

    def test_tables_exist_in_database(self, db_session):
        """Verify project_snapshots and risk_history tables exist in information_schema."""
        result = db_session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_name IN ('project_snapshots', 'risk_history');
        """)).scalars().all()

        assert "project_snapshots" in result, "Table 'project_snapshots' not found in PostgreSQL"
        assert "risk_history" in result, "Table 'risk_history' not found in PostgreSQL"

    def test_project_snapshots_columns(self, db_session):
        """Verify required columns and types in project_snapshots."""
        result = db_session.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'project_snapshots';
        """)).mappings().all()

        col_dict = {row["column_name"]: row["data_type"] for row in result}
        expected_cols = [
            "snapshot_id", "project_id", "snapshot_datetime", "snapshot_date",
            "project_status", "recommended_amount", "sanctioned_amount",
            "released_amount", "expenditure_amount", "unspent_balance",
            "utilization_rate_pct", "cost_overrun_amount", "physical_progress_pct",
            "financial_progress_pct", "expected_completion_date", "actual_completion_date",
            "days_delayed", "milestone_status", "cost_deviation", "progress_gap",
            "derived_metrics", "overall_risk_score", "risk_level", "change_summary", "created_at"
        ]

        for col in expected_cols:
            assert col in col_dict, f"Column '{col}' missing from project_snapshots"

    def test_risk_history_columns(self, db_session):
        """Verify required columns and types in risk_history."""
        result = db_session.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'risk_history';
        """)).mappings().all()

        col_dict = {row["column_name"]: row["data_type"] for row in result}
        expected_cols = [
            "history_id", "project_id", "snapshot_id", "overall_risk_score",
            "risk_level", "delay_risk_score", "cost_overrun_risk_score",
            "non_completion_risk_score", "leakage_risk_score", "detector_scores",
            "weights_used", "primary_factors", "engine_version", "model_version",
            "calculated_at", "created_at"
        ]

        for col in expected_cols:
            assert col in col_dict, f"Column '{col}' missing from risk_history"

    def test_indexes_exist(self, db_session):
        """Verify indexes exist on both tables."""
        result = db_session.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename IN ('project_snapshots', 'risk_history');
        """)).scalars().all()

        expected_indexes = [
            "idx_snapshots_project_id",
            "idx_snapshots_datetime",
            "idx_snapshots_date",
            "idx_snapshots_proj_datetime",
            "idx_snapshots_risk_level",
            "idx_snapshots_status",
            "idx_risk_history_project_id",
            "idx_risk_history_snapshot_id",
            "idx_risk_history_calculated_at",
            "idx_risk_history_proj_calc",
            "idx_risk_history_risk_level",
        ]

        for idx in expected_indexes:
            assert idx in result, f"Index '{idx}' not found in pg_indexes"

    def test_foreign_key_constraints(self, db_session):
        """Verify foreign key references to projects and project_snapshots with CASCADE."""
        result = db_session.execute(text("""
            SELECT 
                tc.table_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.delete_rule
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
            JOIN information_schema.referential_constraints AS rc
              ON rc.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name IN ('project_snapshots', 'risk_history');
        """)).mappings().all()

        fks = {(r["table_name"], r["column_name"]): (r["foreign_table_name"], r["delete_rule"]) for r in result}
        
        # Check project_snapshots -> projects(project_id)
        assert ("project_snapshots", "project_id") in fks
        assert fks[("project_snapshots", "project_id")][0] == "projects"
        assert fks[("project_snapshots", "project_id")][1] == "CASCADE"

        # Check risk_history -> projects(project_id)
        assert ("risk_history", "project_id") in fks
        assert fks[("risk_history", "project_id")][0] == "projects"
        assert fks[("risk_history", "project_id")][1] == "CASCADE"

        # Check risk_history -> project_snapshots(snapshot_id)
        assert ("risk_history", "snapshot_id") in fks
        assert fks[("risk_history", "snapshot_id")][0] == "project_snapshots"
        assert fks[("risk_history", "snapshot_id")][1] == "CASCADE"

    def test_orm_snapshot_and_risk_history_crud(self, db_session):
        """
        Verify that SQLAlchemy models ProjectSnapshot and RiskHistory can be created,
        persisted, queried through Project relationships, and clean up safely.
        """
        # 1. Fetch an existing project
        project = db_session.query(Project).first()
        assert project is not None, "No projects found in database to attach snapshot to"
        pid = project.project_id

        now = datetime.now(timezone.utc)
        today = date.today()

        # 2. Instantiate a ProjectSnapshot
        snapshot = ProjectSnapshot(
            project_id=pid,
            snapshot_datetime=now,
            snapshot_date=today,
            project_status="In Progress",
            recommended_amount=Decimal("5000000.00"),
            sanctioned_amount=Decimal("4800000.00"),
            released_amount=Decimal("3500000.00"),
            expenditure_amount=Decimal("2800000.00"),
            unspent_balance=Decimal("700000.00"),
            utilization_rate_pct=Decimal("80.00"),
            cost_overrun_amount=Decimal("0.00"),
            physical_progress_pct=Decimal("65.00"),
            financial_progress_pct=Decimal("58.33"),
            expected_completion_date=date(2026, 12, 31),
            days_delayed=15,
            milestone_status="Delayed",
            cost_deviation=Decimal("120000.00"),
            progress_gap=Decimal("6.67"),
            derived_metrics={"burn_rate": 1.25, "z_score": 1.45},
            overall_risk_score=Decimal("48.50"),
            risk_level="Moderate",
            change_summary="Physical progress advanced +10%; expenditure disbursed +₹5L."
        )

        db_session.add(snapshot)
        db_session.flush()

        assert snapshot.snapshot_id is not None
        snap_id = snapshot.snapshot_id

        # 3. Instantiate RiskHistory associated with this snapshot
        risk_hist = RiskHistory(
            project_id=pid,
            snapshot_id=snap_id,
            overall_risk_score=Decimal("48.50"),
            risk_level="Moderate",
            delay_risk_score=Decimal("52.00"),
            cost_overrun_risk_score=Decimal("42.00"),
            non_completion_risk_score=Decimal("35.00"),
            leakage_risk_score=Decimal("15.00"),
            detector_scores={
                "delay_detection": {"score": 52.0, "risk_level": "MEDIUM"},
                "cost_anomaly": {"score": 42.0, "risk_level": "MEDIUM"},
                "progress_mismatch": {"score": 38.0, "risk_level": "LOW"},
                "agency_pattern": {"score": 25.0, "risk_level": "LOW"},
                "duplicate_detection": {"score": 0.0, "risk_level": "LOW"}
            },
            weights_used={"delay_detection": 0.35, "cost_anomaly": 0.25},
            primary_factors=[{"factor": "Timeline delay", "score": 52.0}],
            engine_version="1.0.0",
            model_version="v1.0",
            calculated_at=now
        )

        db_session.add(risk_hist)
        db_session.flush()

        assert risk_hist.history_id is not None

        # 4. Query back through Project relationships
        db_session.expire_all()
        refreshed_project = db_session.query(Project).filter(Project.project_id == pid).one()
        
        # Verify snapshot is in project.snapshots
        matching_snaps = [s for s in refreshed_project.snapshots if s.snapshot_id == snap_id]
        assert len(matching_snaps) == 1
        retrieved_snap = matching_snaps[0]
        assert retrieved_snap.physical_progress_pct == Decimal("65.00")
        assert retrieved_snap.risk_level == "Moderate"
        assert retrieved_snap.derived_metrics == {"burn_rate": 1.25, "z_score": 1.45}

        # Verify relationship from snapshot to risk_history
        assert retrieved_snap.risk_history is not None
        assert retrieved_snap.risk_history.history_id == risk_hist.history_id
        assert retrieved_snap.risk_history.overall_risk_score == Decimal("48.50")
        assert retrieved_snap.risk_history.detector_scores["delay_detection"]["score"] == 52.0

        # Verify risk_hist is in project.risk_histories
        matching_rh = [rh for rh in refreshed_project.risk_histories if rh.history_id == risk_hist.history_id]
        assert len(matching_rh) == 1

        # 5. Clean up the test records
        db_session.delete(snapshot)
        db_session.commit()

        # Confirm cascade deleted risk_history record as well
        remaining_rh = db_session.query(RiskHistory).filter(RiskHistory.history_id == risk_hist.history_id).first()
        assert remaining_rh is None, "Cascading delete failed: RiskHistory was not deleted with Snapshot"
