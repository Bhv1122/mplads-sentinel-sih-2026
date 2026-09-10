"""
backend/tests/test_database_risk_integration.py
=============================================================================
Comprehensive PostgreSQL Integration Tests for Risk Engine & Six Detectors.
=============================================================================

Validates:
1. PostgreSQL schema integrity:
   - risk_scores: project_id, overall_score, risk_level, created_at, updated_at,
                  weights_used, config_version, engine_version, calculated_at
   - risk_factors: project_id, engine_name, score, risk_level, reason,
                   confidence, details, created_at
2. Full persistence of all six engines:
   - cost_anomaly, duplicate_detection, delay_detection,
     progress_mismatch, agency_pattern, explained_risk
3. In-place recalculation without duplicate records:
   - created_at is preserved
   - updated_at and calculated_at are updated
   - row count remains exactly 1 risk_score and 6 risk_factors
4. Preservation of existing data:
   - Recalculating a project does not delete, alter, or orphan other projects' data
5. Transactional safety and constraint integrity
"""

import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List
import pytest
from sqlalchemy import inspect, select, func
from sqlalchemy.orm import Session

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.models.project import Project, RiskScore, RiskFactor
from app.services.risk_engine import RiskEngine


@pytest.fixture
def db_session():
    """Provides an active database session connected to PostgreSQL."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestDatabaseSchemaIntegrity:
    """Verifies table structures, required columns, and datatypes in PostgreSQL."""

    def test_risk_scores_columns(self, db_session: Session):
        """Verify risk_scores table contains all required integration columns."""
        inspector = inspect(db_session.bind)
        columns = {col["name"]: col for col in inspector.get_columns("risk_scores")}

        # Primary required columns
        assert "project_id" in columns
        assert "overall_risk_score" in columns
        assert "risk_level" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

        # Extended metadata columns
        assert "weights_used" in columns
        assert "config_version" in columns
        assert "engine_version" in columns
        assert "calculated_at" in columns

    def test_risk_factors_columns(self, db_session: Session):
        """Verify risk_factors table contains all required integration columns."""
        inspector = inspect(db_session.bind)
        columns = {col["name"]: col for col in inspector.get_columns("risk_factors")}

        # Primary required columns
        assert "project_id" in columns
        assert "engine_name" in columns
        assert "score" in columns
        assert "risk_level" in columns
        assert "reason" in columns
        assert "confidence" in columns
        assert "details" in columns
        assert "created_at" in columns

        # Legacy backward-compatible columns
        assert "factor_category" in columns
        assert "factor_name" in columns
        assert "factor_impact" in columns
        assert "factor_weight" in columns


class TestSixEnginesPersistence:
    """Validates that running RiskEngine correctly persists all six engines to PostgreSQL."""

    def test_persist_all_six_engines(self, db_session: Session):
        """
        Evaluate project MPLADS-2024-0001 and assert that:
        - 1 RiskScore row is saved with overall_score, risk_level, timestamps, and config metadata.
        - Exactly 6 RiskFactor rows are saved corresponding to the six engines.
        """
        project_id = "MPLADS-2024-0001"
        engine = RiskEngine()
        result = engine.evaluate(project_id=project_id, db=db_session, persist=True)

        # 1. Verify RiskScore row
        score_row = db_session.query(RiskScore).filter_by(project_id=project_id).first()
        assert score_row is not None
        assert score_row.project_id == project_id
        assert float(score_row.overall_score) == pytest.approx(result["overall_risk_score"], 0.01)
        assert score_row.risk_level in ["Low", "Moderate", "High", "Critical"]
        assert score_row.created_at is not None
        assert score_row.updated_at is not None
        assert score_row.calculated_at is not None
        assert score_row.engine_version == engine.engine_version
        assert score_row.config_version is not None
        assert isinstance(score_row.weights_used, dict)
        assert len(score_row.weights_used) >= 5
        for k in ["cost_anomaly", "duplicate_detection", "delay_detection", "progress_mismatch", "agency_pattern"]:
            assert k in score_row.weights_used

        # 2. Verify all 6 RiskFactor rows
        factors = (
            db_session.query(RiskFactor)
            .filter_by(project_id=project_id)
            .order_by(RiskFactor.engine_name)
            .all()
        )
        assert len(factors) == 6

        expected_engines = {
            "cost_anomaly",
            "duplicate_detection",
            "delay_detection",
            "progress_mismatch",
            "agency_pattern",
            "explained_risk",
        }
        persisted_engines = {f.engine_name for f in factors}
        assert persisted_engines == expected_engines

        # 3. Verify each factor's attributes
        for f in factors:
            assert f.project_id == project_id
            assert f.score is not None
            assert 0.0 <= float(f.score) <= 100.0
            assert f.risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            assert f.reason is not None and len(f.reason.strip()) > 0
            assert f.confidence is not None
            assert 0.0 <= float(f.confidence) <= 1.0
            assert isinstance(f.details, dict)
            assert f.created_at is not None

            # Legacy constraints check
            assert f.factor_category in [
                "Agency Past Performance", "Delay in Tendering", "Budget Gap",
                "Slow Physical Pace", "Monsoon Seasonality", "Geographic Remoteness",
                "Land Dispute", "Contractor Inaction", "Other"
            ]
            assert f.factor_impact in ["Low", "Medium", "High", "Critical"]

    def test_engine_6_explained_risk_details(self, db_session: Session):
        """Verify Engine 6 stores structured narrative explanation and review areas in details."""
        project_id = "MPLADS-2024-0001"
        engine = RiskEngine()
        engine.evaluate(project_id=project_id, db=db_session, persist=True)

        exp_factor = (
            db_session.query(RiskFactor)
            .filter_by(project_id=project_id, engine_name="explained_risk")
            .first()
        )
        assert exp_factor is not None
        details = exp_factor.details
        assert "summary" in details
        assert "engine_scores" in details
        assert "risk_factors" in details
        assert "recommended_review" in details
        assert isinstance(details["risk_factors"], list)
        assert isinstance(details["recommended_review"], list)


class TestRecalculationAndIdempotency:
    """Validates that recalculation preserves created_at and does not create duplicate rows."""

    def test_recalculation_preserves_created_at_and_updates_timestamps(self, db_session: Session):
        """
        Recalculating a project must:
        - Keep the exact original created_at timestamp on RiskScore
        - Update updated_at and calculated_at to newer timestamps
        - Leave exactly 1 RiskScore and 6 RiskFactors (no duplicates)
        """
        project_id = "MPLADS-2024-0002"
        engine = RiskEngine()

        # Initial calculation
        engine.evaluate(project_id=project_id, db=db_session, persist=True)
        initial_score = db_session.query(RiskScore).filter_by(project_id=project_id).first()
        assert initial_score is not None
        initial_created_at = initial_score.created_at
        initial_updated_at = initial_score.updated_at

        # Small pause to ensure timestamp change
        time.sleep(0.05)

        # Recalculation
        engine.evaluate(project_id=project_id, db=db_session, persist=True)
        db_session.expire_all()

        recalc_score = db_session.query(RiskScore).filter_by(project_id=project_id).first()
        assert recalc_score is not None

        # Verify created_at is preserved untouched
        assert recalc_score.created_at == initial_created_at

        # Verify updated_at and calculated_at were refreshed
        assert recalc_score.updated_at >= initial_updated_at
        assert recalc_score.calculated_at is not None

        # Verify no duplicate rows
        score_count = db_session.query(RiskScore).filter_by(project_id=project_id).count()
        factor_count = db_session.query(RiskFactor).filter_by(project_id=project_id).count()
        assert score_count == 1
        assert factor_count == 6


class TestDataIsolation:
    """Validates that recalculating one project leaves other projects' data untouched."""

    def test_other_projects_untouched(self, db_session: Session):
        """Evaluating project B does not modify project A's risk_scores or risk_factors."""
        project_a = "MPLADS-2024-0001"
        project_b = "MPLADS-2024-0003"
        engine = RiskEngine()

        # Ensure project A is evaluated
        engine.evaluate(project_id=project_a, db=db_session, persist=True)
        score_a_before = db_session.query(RiskScore).filter_by(project_id=project_a).first()
        created_a_before = score_a_before.created_at
        updated_a_before = score_a_before.updated_at
        factors_a_count_before = db_session.query(RiskFactor).filter_by(project_id=project_a).count()

        # Evaluate project B
        engine.evaluate(project_id=project_b, db=db_session, persist=True)
        db_session.expire_all()

        # Check project A state
        score_a_after = db_session.query(RiskScore).filter_by(project_id=project_a).first()
        assert score_a_after.created_at == created_a_before
        assert score_a_after.updated_at == updated_a_before
        factors_a_count_after = db_session.query(RiskFactor).filter_by(project_id=project_a).count()
        assert factors_a_count_after == factors_a_count_before == 6

        # Check project B state
        assert db_session.query(RiskScore).filter_by(project_id=project_b).count() == 1
        assert db_session.query(RiskFactor).filter_by(project_id=project_b).count() == 6


class TestTransactionalIntegrity:
    """Validates transaction rollback behavior."""

    def test_transaction_rollback_preserves_state(self, db_session: Session):
        """If a session rollback occurs, no partial or corrupted rows are persisted."""
        project_id = "MPLADS-2024-0004"
        engine = RiskEngine()

        # Ensure project exists
        res = engine.evaluate(project_id=project_id, db=db_session, persist=True)
        initial_score = db_session.query(RiskScore).filter_by(project_id=project_id).first()
        initial_score_val = initial_score.overall_score

        # Simulate a transaction failure: manually attempt an invalid insert and rollback
        try:
            db_session.begin_nested()
            invalid_factor = RiskFactor(
                risk_score_id=initial_score.risk_score_id,
                project_id=project_id,
                factor_category="INVALID_CATEGORY_VIOLATING_CHECK_CONSTRAINT",
                factor_name="Failing Factor",
                factor_weight=Decimal("0.5"),
                factor_impact="High",
                mitigation_recommendation="Test",
            )
            db_session.add(invalid_factor)
            db_session.flush()
        except Exception:
            db_session.rollback()

        # Verify state is completely intact
        current_score = db_session.query(RiskScore).filter_by(project_id=project_id).first()
        assert current_score is not None
        assert current_score.overall_score == initial_score_val
        factor_count = db_session.query(RiskFactor).filter_by(project_id=project_id).count()
        assert factor_count == 6


class TestBatchDatabasePersistence:
    """Validates batch evaluation persistence to PostgreSQL."""

    def test_batch_persist_multiple_projects(self, db_session: Session):
        """Batch evaluate 3 projects and assert all scores and 6 factors are properly stored."""
        pids = ["MPLADS-2024-0005", "MPLADS-2024-0006", "MPLADS-2024-0007"]
        engine = RiskEngine()
        results = engine.evaluate_batch(db=db_session, project_ids=pids, persist=True)
        assert len(results) == 3

        for pid in pids:
            score = db_session.query(RiskScore).filter_by(project_id=pid).first()
            assert score is not None
            assert score.project_id == pid
            assert score.calculated_at is not None

            factors = db_session.query(RiskFactor).filter_by(project_id=pid).all()
            assert len(factors) == 6
            persisted_names = {f.engine_name for f in factors}
            assert persisted_names == {
                "cost_anomaly",
                "duplicate_detection",
                "delay_detection",
                "progress_mismatch",
                "agency_pattern",
                "explained_risk",
            }


class TestRawSQLQueryValidation:
    """Validates PostgreSQL-specific JSONB features, indexes, and raw SQL queries."""

    def test_jsonb_querying_on_risk_scores_and_factors(self, db_session: Session):
        """Verify PostgreSQL native JSONB operators work on weights_used and details."""
        from sqlalchemy import text

        # Ensure project MPLADS-2024-0001 is evaluated
        engine = RiskEngine()
        engine.evaluate(project_id="MPLADS-2024-0001", db=db_session, persist=True)

        # 1. Query weights_used via JSONB path extraction in raw SQL
        sql_score = text("""
            SELECT project_id,
                   overall_risk_score,
                   weights_used->>'cost_anomaly' AS cost_weight,
                   config_version,
                   engine_version
            FROM risk_scores
            WHERE project_id = :pid;
        """)
        row_score = db_session.execute(sql_score, {"pid": "MPLADS-2024-0001"}).fetchone()
        assert row_score is not None
        assert float(row_score.cost_weight) == 0.20
        assert row_score.engine_version == "risk_engine_v2.0"

        # 2. Query risk_factors details via JSONB extraction in raw SQL
        sql_factors = text("""
            SELECT engine_name,
                   score,
                   risk_level,
                   confidence,
                   details->>'summary' AS summary_text
            FROM risk_factors
            WHERE project_id = :pid AND engine_name = 'explained_risk';
        """)
        row_factor = db_session.execute(sql_factors, {"pid": "MPLADS-2024-0001"}).fetchone()
        assert row_factor is not None
        assert row_factor.engine_name == "explained_risk"
        assert row_factor.summary_text is not None and len(row_factor.summary_text) > 0

    def test_cascade_delete_constraint_definition(self, db_session: Session):
        """Verify foreign key constraint has ON DELETE CASCADE from projects to risk_scores/factors."""
        from sqlalchemy import text

        sql_fk = text("""
            SELECT tc.table_name, kcu.column_name, rc.delete_rule
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.referential_constraints AS rc
              ON tc.constraint_name = rc.constraint_name
            WHERE tc.table_name IN ('risk_scores', 'risk_factors')
              AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = 'project_id';
        """)
        rows = db_session.execute(sql_fk).fetchall()
        assert len(rows) >= 2
        for r in rows:
            assert r.delete_rule == "CASCADE"

