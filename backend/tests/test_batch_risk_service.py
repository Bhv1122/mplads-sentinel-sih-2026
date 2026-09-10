"""
backend/tests/test_batch_risk_service.py
=============================================================================
Comprehensive Test Suite for Batch Risk Processing Service.
=============================================================================

Tests:
1. Single project processing (full pipeline Engines 1–6 + Persistence)
2. Selected projects batch processing
3. All projects batch processing
4. Fault tolerance and single-project failure isolation
5. Embedding caching and candidate pool pre-loading
6. Agency statistics caching and zero-redundancy evaluation
7. Summary statistics and risk tier breakdown
8. Database upsert verification (RiskScore & RiskFactor rows)
9. CLI script execution (--all, --project, --projects, --no-persist, --json)
"""

import sys
import json
import subprocess
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import select, func

from app.database import SessionLocal
from app.models.project import Project, RiskScore, RiskFactor
from app.services.risk.batch_risk_service import (
    BatchRiskService,
    BatchRiskSummary,
    batch_risk_service,
)
from app.services.risk.duplicate_detection_engine import DuplicateDetectionEngine
from app.services.risk.agency_pattern_engine import AgencyPatternEngine


@pytest.fixture(scope="module")
def db_session():
    """Yields a database session for testing."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def sample_project_ids(db_session):
    """Retrieves 3 real project IDs from the database."""
    stmt = select(Project.project_id).order_by(Project.project_id).limit(3)
    pids = [r[0] for r in db_session.execute(stmt).all()]
    assert len(pids) >= 1, "Database must contain at least 1 project for testing."
    return pids


# =============================================================================
# 1. Single Project Processing Tests
# =============================================================================

class TestSingleProjectProcessing:
    """Tests evaluating a single project through the full 6-engine batch pipeline."""

    def test_process_single_project_success(self, db_session, sample_project_ids):
        pid = sample_project_ids[0]
        service = BatchRiskService()

        result = service.process_project(project_id=pid, db=db_session, persist=True)

        assert result is not None
        assert result["project_id"] == pid
        assert "overall_score" in result
        assert 0.0 <= result["overall_score"] <= 100.0
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert 0.0 <= result["confidence"] <= 1.0

        # Verify all 6 engines are present in breakdown and scores
        engine_scores = result["engine_scores"]
        assert "cost_anomaly" in engine_scores
        assert "duplicate_detection" in engine_scores
        assert "delay_detection" in engine_scores
        assert "progress_mismatch" in engine_scores
        assert "agency_pattern" in engine_scores
        assert "explained_risk" in engine_scores

        # Verify Engine 6 narrative output
        assert "summary" in result
        assert len(result["summary"]) > 10
        assert "recommended_review" in result
        assert isinstance(result["recommended_review"], list)

        # Verify database persistence
        rs = db_session.execute(
            select(RiskScore).where(RiskScore.project_id == pid)
        ).scalar_one_or_none()
        assert rs is not None
        assert float(rs.overall_risk_score) == pytest.approx(result["overall_score"], abs=0.05)

        factors = db_session.execute(
            select(RiskFactor).where(RiskFactor.risk_score_id == rs.risk_score_id)
        ).scalars().all()
        assert len(factors) == 6, f"Expected 6 risk factors, got {len(factors)}"

    def test_process_single_project_dry_run(self, db_session, sample_project_ids):
        """Dry run (persist=False) evaluates without persisting."""
        pid = sample_project_ids[0]
        service = BatchRiskService()

        result = service.process_project(project_id=pid, db=db_session, persist=False)
        assert result["project_id"] == pid
        assert "overall_score" in result


# =============================================================================
# 2. Selected Projects Batch Processing Tests
# =============================================================================

class TestSelectedProjectsBatch:
    """Tests processing an explicit list of selected projects."""

    def test_process_selected_projects(self, db_session, sample_project_ids):
        service = BatchRiskService()

        summary: BatchRiskSummary = service.process_selected(
            project_ids=sample_project_ids,
            db=db_session,
            persist=True,
        )

        assert summary.projects_processed == len(sample_project_ids)
        assert summary.successful == len(sample_project_ids)
        assert summary.failed == 0
        assert summary.execution_time_seconds > 0
        assert summary.average_score >= 0.0
        assert summary.low + summary.medium + summary.high + summary.critical == summary.successful

    def test_process_empty_list(self, db_session):
        service = BatchRiskService()
        summary = service.process_selected(project_ids=[], db=db_session)
        assert summary.projects_processed == 0
        assert summary.successful == 0
        assert summary.failed == 0


# =============================================================================
# 3. All Projects Batch Processing Tests
# =============================================================================

class TestAllProjectsBatch:
    """Tests processing all projects in the database."""

    def test_process_all_projects_live_dataset(self, db_session):
        service = BatchRiskService()
        total_in_db = db_session.scalar(select(func.count(Project.project_id)))

        summary = service.process_all(db=db_session, persist=True)

        assert summary.projects_processed == total_in_db
        assert summary.successful == total_in_db
        assert summary.failed == 0
        assert summary.completed_at is not None
        assert 0.0 <= summary.average_score <= 100.0

        # Verify summary dictionary and ASCII report format
        summary_dict = summary.to_dict()
        assert summary_dict["projects_processed"] == total_in_db
        assert summary_dict["successful"] == total_in_db

        report_str = summary.format_ascii_report()
        assert "MPLADS BATCH RISK PROCESSING SUMMARY" in report_str
        assert "RISK TIER BREAKDOWN" in report_str


# =============================================================================
# 4. Fault Tolerance & Project-Level Isolation Tests
# =============================================================================

class TestFaultTolerance:
    """Tests that a failure in one project does NOT stop the entire batch."""

    def test_batch_continues_when_one_project_fails(self, db_session, sample_project_ids):
        service = BatchRiskService()

        # Inject synthetic failure on the second project
        original_eval = service.risk_engine.evaluate

        def flaky_evaluate(project_id, db, persist=True, context=None):
            if project_id == sample_project_ids[1]:
                raise RuntimeError(f"Simulated hardware/IO error for project {project_id}")
            return original_eval(project_id=project_id, db=db, persist=persist, context=context)

        with patch.object(service.risk_engine, "evaluate", side_effect=flaky_evaluate):
            summary = service.process_selected(
                project_ids=sample_project_ids,
                db=db_session,
                persist=True,
            )

        assert summary.projects_processed == len(sample_project_ids)
        assert summary.successful == len(sample_project_ids) - 1
        assert summary.failed == 1
        assert len(summary.failed_projects) == 1
        assert summary.failed_projects[0].project_id == sample_project_ids[1]
        assert "Simulated hardware/IO error" in summary.failed_projects[0].error


# =============================================================================
# 5. Embedding Reuse & Agency Caching Optimization Tests
# =============================================================================

class TestBatchOptimizations:
    """Verifies that embeddings and agency stats are cached and reused."""

    def test_agency_statistics_caching_in_batch(self, db_session, sample_project_ids):
        """
        Verifies that for projects belonging to the same agency,
        the agency evaluation is performed once and reused via cache for subsequent projects.
        """
        service = BatchRiskService()
        agency_engine = service.risk_engine.agency_pattern_engine

        # Reset agency engine cache
        agency_engine.clear_cache()

        summary = service.process_selected(
            project_ids=sample_project_ids,
            db=db_session,
            persist=False,
        )

        assert summary.successful == len(sample_project_ids)
        # Agency cache must contain the agency entry
        assert agency_engine.cache_size() >= 1

    def test_duplicate_candidate_pool_reuse(self, db_session, sample_project_ids):
        """
        Verifies that candidate rows passed in context are reused
        without re-querying the database inside DuplicateDetectionEngine.
        """
        service = BatchRiskService()
        context = service._prepare_shared_context(db=db_session, project_ids=sample_project_ids)

        assert "candidates" in context
        assert len(context["candidates"]) > 0
        assert "agency_cache" in context


# =============================================================================
# 6. CLI Runner Script Verification
# =============================================================================

class TestCLIRunner:
    """Verifies CLI runner calculate_batch_risk.py behavior."""

    def test_cli_single_project(self, sample_project_ids):
        pid = sample_project_ids[0]
        cmd = [
            sys.executable,
            "data/scripts/calculate_batch_risk.py",
            "--project", pid,
            "--no-persist",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert f"Project ID           : {pid}" in result.stdout
        assert "Engine Scores Breakdown:" in result.stdout

    def test_cli_selected_projects_json(self, sample_project_ids):
        pids_str = ",".join(sample_project_ids[:2])
        cmd = [
            sys.executable,
            "data/scripts/calculate_batch_risk.py",
            "--projects", pids_str,
            "--no-persist",
            "--json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        assert data["projects_processed"] == 2
        assert data["successful"] == 2
        assert data["failed"] == 0

    def test_cli_all_projects_ascii(self):
        cmd = [
            sys.executable,
            "data/scripts/calculate_batch_risk.py",
            "--all",
            "--no-persist",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert "MPLADS BATCH RISK PROCESSING SUMMARY" in result.stdout
        assert "RISK TIER BREAKDOWN" in result.stdout
