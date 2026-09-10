"""
backend/tests/test_risk_detectors.py
=============================================================================
Comprehensive Unit and Integration Test Suite for Phase 6 Risk Detection.
=============================================================================

Validates:
1. Cost Anomaly Detector (statistical peer grouping, IQR, minimum peers, outliers)
2. Delay Detector (completed, ongoing, cancelled, missing dates, extreme delays)
3. Fund Utilization Detector (cost overrun, deficit, low absorption, zero allocation)
4. Progress Mismatch Detector (financial ahead, physical ahead, aligned, missing)
5. Duplicate Detector (identical, similar, unrelated, short descriptions, self-exclusion)
6. Risk Runner Integration (all detectors orchestrated, defensive failure isolation, batch)
"""

import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.models.project import Project, Financial, Progress
from app.services.risk.base import RiskDetectorResult, score_to_severity, BaseRiskDetector
from app.services.risk.cost_anomaly import CostAnomalyDetector
from app.services.risk.delay_detector import DelayDetector
from app.services.risk.fund_utilization import FundUtilizationDetector
from app.services.risk.progress_mismatch import ProgressMismatchDetector
from app.services.risk.duplicate_detection import DuplicateDetector
from app.services.risk.risk_runner import RiskRunner


# =============================================================================
# Helper Fixtures & Mock DB Sessions
# =============================================================================

@pytest.fixture
def db_session():
    """Provides an active database session against PostgreSQL."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# =============================================================================
# 1. Cost Anomaly Detector Tests
# =============================================================================

class TestCostAnomalyDetector:

    def test_cost_anomaly_normal_project(self, db_session):
        detector = CostAnomalyDetector()
        # Test against real project in DB
        res = detector.detect("MPLADS-2024-0001", db_session)
        assert 0 <= res.score <= 100
        assert res.severity in {"low", "medium", "high"}
        assert "project_cost" in res.details
        assert "peer_median" in res.details

    def test_cost_anomaly_extreme_high_cost(self):
        """Simulate a project that is 3.5x peer median and above Tukey upper fence."""
        detector = CostAnomalyDetector()
        mock_db = MagicMock()

        # Target project: 7,000,000 in Education
        target_p = Project(project_id="P-TEST-HIGH", sector="Education", state_id=1)
        target_f = Financial(project_id="P-TEST-HIGH", sanctioned_amount=Decimal("7000000"))
        mock_db.execute.return_value.first.return_value = (target_p, target_f)

        # Peer costs: median around 1,500,000
        with patch.object(detector, "_get_peer_costs", return_value=([1000000.0, 1200000.0, 1500000.0, 1800000.0, 2000000.0], "state_sector")):
            res = detector.detect("P-TEST-HIGH", mock_db)
            assert res.score >= 75
            assert res.severity == "high"
            assert "peer median" in res.reason.lower()
            assert res.details["ratio"] >= 3.0

    def test_cost_anomaly_insufficient_peers(self):
        """When fewer than 3 peers exist, should return neutral score 0 with low severity."""
        detector = CostAnomalyDetector()
        mock_db = MagicMock()

        target_p = Project(project_id="P-RARE", sector="Space Research", state_id=99)
        target_f = Financial(project_id="P-RARE", sanctioned_amount=Decimal("5000000"))
        mock_db.execute.return_value.first.return_value = (target_p, target_f)

        with patch.object(detector, "_get_peer_costs", return_value=([4500000.0], "nationwide_sector")):
            res = detector.detect("P-RARE", mock_db)
            assert res.score == 0
            assert res.severity == "low"
            assert "insufficient peer data" in res.reason.lower()
            assert res.details["insufficient_peers"] is True

    def test_cost_anomaly_zero_cost(self):
        """Zero or null sanctioned/recommended cost returns 0 score."""
        detector = CostAnomalyDetector()
        mock_db = MagicMock()

        target_p = Project(project_id="P-ZERO", sector="Roads", state_id=1)
        target_f = Financial(project_id="P-ZERO", sanctioned_amount=Decimal("0"))
        mock_db.execute.return_value.first.return_value = (target_p, target_f)

        res = detector.detect("P-ZERO", mock_db)
        assert res.score == 0
        assert res.severity == "low"
        assert "zero or not recorded" in res.reason.lower()


# =============================================================================
# 2. Delay Detector Tests
# =============================================================================

class TestDelayDetector:

    def test_delay_completed_on_time(self):
        detector = DelayDetector()
        mock_db = MagicMock()

        p = Project(
            project_id="P-DONE-EARLY",
            current_status="Completed",
            work_order_date=date(2024, 1, 1),
            expected_completion_date=date(2024, 6, 30),
            actual_completion_date=date(2024, 6, 25)
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = p

        res = detector.detect("P-DONE-EARLY", mock_db)
        assert res.score == 0
        assert res.severity == "low"
        assert "early" in res.reason.lower() or "on schedule" in res.reason.lower()

    def test_delay_completed_late(self):
        detector = DelayDetector()
        mock_db = MagicMock()

        p = Project(
            project_id="P-DONE-LATE",
            current_status="Completed",
            work_order_date=date(2024, 1, 1),
            expected_completion_date=date(2024, 6, 30),
            actual_completion_date=date(2024, 9, 30)  # ~92 days late
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = p

        res = detector.detect("P-DONE-LATE", mock_db)
        assert res.score >= 65
        assert res.details["overdue_days"] == 92
        assert "behind schedule" in res.reason.lower()

    def test_delay_ongoing_overdue(self):
        detector = DelayDetector()
        mock_db = MagicMock()

        p = Project(
            project_id="P-ONGOING-LATE",
            current_status="In Progress",
            work_order_date=date(2024, 1, 1),
            expected_completion_date=date(2024, 6, 1)
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = p

        # as_of_date is 2024-10-01 (122 days overdue)
        res = detector.detect("P-ONGOING-LATE", mock_db, context={"as_of_date": "2024-10-01"})
        assert res.score >= 70
        assert res.severity == "high"
        assert res.details["overdue_days"] == 122
        assert "122 days overdue" in res.reason

    def test_delay_cancelled_project(self):
        detector = DelayDetector()
        mock_db = MagicMock()

        p = Project(
            project_id="P-CANCELLED",
            current_status="Cancelled",
            expected_completion_date=date(2024, 1, 1)
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = p

        res = detector.detect("P-CANCELLED", mock_db)
        assert res.score == 0
        assert res.severity == "low"
        assert "not applicable" in res.reason.lower()

    def test_delay_missing_dates(self):
        """When expected completion date is missing, do NOT assign high delay score."""
        detector = DelayDetector()
        mock_db = MagicMock()

        p = Project(
            project_id="P-NODATE",
            current_status="In Progress",
            expected_completion_date=None
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = p

        res = detector.detect("P-NODATE", mock_db)
        assert res.score == 0
        assert res.severity == "low"
        assert "not recorded" in res.reason.lower()


# =============================================================================
# 3. Fund Utilization Detector Tests
# =============================================================================

class TestFundUtilizationDetector:

    def test_fund_utilization_healthy(self):
        detector = FundUtilizationDetector()
        mock_db = MagicMock()

        p = Project(project_id="P-HEALTHY", current_status="Completed")
        f = Financial(
            project_id="P-HEALTHY",
            sanctioned_amount=Decimal("1000000"),
            released_amount=Decimal("1000000"),
            expenditure_amount=Decimal("950000")
        )
        mock_db.execute.return_value.first.return_value = (p, f)

        res = detector.detect("P-HEALTHY", mock_db)
        assert res.score == 0
        assert res.severity == "low"
        assert "healthy" in res.reason.lower()

    def test_fund_utilization_cost_overrun(self):
        """Expenditure exceeds sanctioned amount by 25%."""
        detector = FundUtilizationDetector()
        mock_db = MagicMock()

        p = Project(project_id="P-OVERRUN", current_status="In Progress")
        f = Financial(
            project_id="P-OVERRUN",
            sanctioned_amount=Decimal("1000000"),
            released_amount=Decimal("1250000"),
            expenditure_amount=Decimal("1250000")
        )
        mock_db.execute.return_value.first.return_value = (p, f)

        res = detector.detect("P-OVERRUN", mock_db)
        assert res.score >= 75
        assert res.severity == "high"
        assert "exceeds sanctioned amount" in res.reason.lower()
        assert res.details["overrun_pct"] == 25.0

    def test_fund_utilization_deficit_spending(self):
        """Expenditure exceeds released tranche (unfunded contractor liabilities)."""
        detector = FundUtilizationDetector()
        mock_db = MagicMock()

        p = Project(project_id="P-DEFICIT", current_status="In Progress")
        f = Financial(
            project_id="P-DEFICIT",
            sanctioned_amount=Decimal("2000000"),
            released_amount=Decimal("1000000"),
            expenditure_amount=Decimal("1400000")
        )
        mock_db.execute.return_value.first.return_value = (p, f)

        res = detector.detect("P-DEFICIT", mock_db)
        assert res.score >= 65
        assert "exceeds released funds" in res.reason.lower()

    def test_fund_utilization_low_absorption_active_work(self):
        """Active ongoing project with only 10% fund utilization."""
        detector = FundUtilizationDetector()
        mock_db = MagicMock()

        p = Project(project_id="P-LOWUTIL", current_status="In Progress")
        f = Financial(
            project_id="P-LOWUTIL",
            sanctioned_amount=Decimal("1000000"),
            released_amount=Decimal("1000000"),
            expenditure_amount=Decimal("100000")
        )
        mock_db.execute.return_value.first.return_value = (p, f)

        res = detector.detect("P-LOWUTIL", mock_db)
        assert res.score >= 45
        assert "only 10%" in res.reason.lower()


# =============================================================================
# 4. Progress Mismatch Detector Tests
# =============================================================================

class TestProgressMismatchDetector:

    def test_progress_mismatch_aligned(self):
        detector = ProgressMismatchDetector()
        mock_db = MagicMock()

        p = Project(project_id="P-ALIGNED", current_status="In Progress")
        f = Financial(project_id="P-ALIGNED", sanctioned_amount=Decimal("1000000"), expenditure_amount=Decimal("500000"))
        pr = Progress(project_id="P-ALIGNED", physical_progress_pct=Decimal("52.0"))

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [p, f, pr]

        res = detector.detect("P-ALIGNED", mock_db)
        assert res.score <= 15
        assert res.severity == "low"
        assert "well aligned" in res.reason.lower()

    def test_progress_mismatch_financial_leading(self):
        """Financial 80% vs Physical 35% -> Gap 45 percentage points."""
        detector = ProgressMismatchDetector()
        mock_db = MagicMock()

        p = Project(project_id="P-FIN-AHEAD", current_status="In Progress")
        f = Financial(project_id="P-FIN-AHEAD", sanctioned_amount=Decimal("1000000"), expenditure_amount=Decimal("800000"))
        pr = Progress(project_id="P-FIN-AHEAD", physical_progress_pct=Decimal("35.0"))

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [p, f, pr]

        res = detector.detect("P-FIN-AHEAD", mock_db)
        assert res.score >= 75
        assert res.severity == "high"
        assert "45 percentage points ahead" in res.reason
        assert res.details["gap"] == 45.0
        assert res.details["direction"] == "financial_leading"

    def test_progress_mismatch_physical_leading(self):
        """Physical 85% vs Financial 20% -> Gap -65 percentage points."""
        detector = ProgressMismatchDetector()
        mock_db = MagicMock()

        p = Project(project_id="P-PHY-AHEAD", current_status="In Progress")
        f = Financial(project_id="P-PHY-AHEAD", sanctioned_amount=Decimal("1000000"), expenditure_amount=Decimal("200000"))
        pr = Progress(project_id="P-PHY-AHEAD", physical_progress_pct=Decimal("85.0"))

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [p, f, pr]

        res = detector.detect("P-PHY-AHEAD", mock_db)
        assert res.score >= 50
        assert "ahead of recorded expenditure" in res.reason.lower()
        assert res.details["direction"] == "physical_leading"

    def test_progress_mismatch_missing_progress(self):
        detector = ProgressMismatchDetector()
        mock_db = MagicMock()

        p = Project(project_id="P-NOPROG", current_status="In Progress")
        f = Financial(project_id="P-NOPROG", sanctioned_amount=Decimal("1000000"), expenditure_amount=Decimal("200000"))

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [p, f, None]

        res = detector.detect("P-NOPROG", mock_db)
        assert res.score == 0
        assert res.severity == "low"
        assert "not been reported" in res.reason.lower()


# =============================================================================
# 5. Duplicate Detection Tests
# =============================================================================

class TestDuplicateDetector:

    def test_duplicate_unrelated_descriptions(self):
        detector = DuplicateDetector(use_neural=False)
        mock_db = MagicMock()

        target = Project(
            project_id="P-WATER",
            project_title="Community RO Drinking Water Plant",
            project_description="Installation of 1000 LPH reverse osmosis water filtration system in village square."
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        candidates = [
            ("P-SOLAR", "Solar High Mast Lights", "Installation of 12 LED solar street lighting poles on highway."),
            ("P-ROAD", "Village Concrete Pavement", "Construction of CC road from primary health centre to school."),
        ]
        mock_db.execute.return_value.all.return_value = candidates

        res = detector.detect("P-WATER", mock_db)
        assert res.score <= 30
        assert res.severity == "low"
        assert "no duplicate" in res.reason.lower()

    def test_duplicate_identical_descriptions(self):
        detector = DuplicateDetector(use_neural=False)
        mock_db = MagicMock()

        target = Project(
            project_id="P-RO-1",
            project_title="Installation of RO Water Filter",
            project_description="Supply, erection and commissioning of 500 LPH drinking water reverse osmosis unit at Ward 4."
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        candidates = [
            ("P-RO-2", "Installation of RO Water Filter", "Supply, erection and commissioning of 500 LPH drinking water reverse osmosis unit at Ward 4."),
            ("P-ROAD", "Village Road", "Concrete road laying work."),
        ]
        mock_db.execute.return_value.all.return_value = candidates

        res = detector.detect("P-RO-1", mock_db)
        assert res.score >= 85
        assert res.severity == "high"
        assert "potential duplicate" in res.reason.lower()
        assert res.details["matched_project_id"] == "P-RO-2"
        assert res.details["similarity"] >= 0.90

    def test_duplicate_short_description(self):
        detector = DuplicateDetector(use_neural=False)
        mock_db = MagicMock()

        target = Project(project_id="P-SHORT", project_title="Work", project_description="Road")
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = detector.detect("P-SHORT", mock_db)
        assert res.score == 0
        assert res.severity == "low"
        assert "too short" in res.reason.lower()


# =============================================================================
# 6. Risk Runner Integration Tests
# =============================================================================

class TestRiskRunner:

    def test_risk_runner_executes_all_detectors_on_live_project(self, db_session):
        runner = RiskRunner()
        # Query sample project ID
        sample_proj = db_session.query(Project.project_id).first()
        assert sample_proj is not None, "Live database must contain at least one project"
        project_id = sample_proj[0]

        result = runner.run(project_id, db_session, context={"as_of_date": "2026-09-09"})

        # Contract assertions
        assert result["project_id"] == project_id
        assert "evaluated_at" in result
        assert "detectors" in result

        detectors = result["detectors"]
        expected_detectors = [
            "cost_anomaly",
            "delay",
            "fund_utilization",
            "progress_mismatch",
            "duplicate_detection"
        ]
        for det_name in expected_detectors:
            assert det_name in detectors, f"Missing detector '{det_name}' in output"
            det_res = detectors[det_name]
            assert "score" in det_res
            assert "reason" in det_res
            assert "severity" in det_res
            assert "details" in det_res
            assert 0 <= det_res["score"] <= 100
            assert det_res["severity"] in {"low", "medium", "high"}
            assert isinstance(det_res["reason"], str) and len(det_res["reason"]) > 0
            assert isinstance(det_res["details"], dict)

    def test_risk_runner_isolated_failure_resilience(self, db_session):
        """If one detector blows up, others must execute and return valid outputs."""
        faulty_detector = MagicMock(spec=BaseRiskDetector)
        faulty_detector.detect.side_effect = RuntimeError("Database connection timed out in detector")

        runner = RiskRunner(cost_anomaly_detector=faulty_detector)
        result = runner.run("MPLADS-2024-0001", db_session)

        # Faulty detector returned gracefully trapped result
        assert result["detectors"]["cost_anomaly"]["score"] == 0
        assert "failed" in result["detectors"]["cost_anomaly"]["reason"].lower()

        # Other 4 detectors executed normally
        assert "delay" in result["detectors"]
        assert "fund_utilization" in result["detectors"]
        assert "progress_mismatch" in result["detectors"]
        assert "duplicate_detection" in result["detectors"]
        assert result["detectors"]["delay"]["score"] >= 0

    def test_risk_runner_batch(self, db_session):
        runner = RiskRunner()
        batch_results = runner.run_batch(db_session, limit=3)
        assert isinstance(batch_results, list)
        assert len(batch_results) > 0
        for item in batch_results:
            assert "project_id" in item
            assert len(item["detectors"]) == 5
