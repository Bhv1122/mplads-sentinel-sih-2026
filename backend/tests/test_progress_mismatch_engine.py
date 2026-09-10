"""
backend/tests/test_progress_mismatch_engine.py
=============================================================================
Comprehensive Test Suite for Engine 4: Financial and Physical Progress Mismatch.
=============================================================================

Tests:
1. Exact Schema & Return Contract (engine, score, risk_level, reason, details, confidence)
2. Mandatory Details Fields (financial_progress, physical_progress, progress_gap)
3. Balanced execution (|progress_gap| <= tolerance -> score < 30, LOW risk)
4. Direction 1: Financial >> Physical (gap > tolerance -> financial_leading, score elevated)
5. Direction 2: Physical >> Financial (gap < -tolerance -> physical_leading, score elevated)
6. Non-accusatory tone verification (no fraud accusations, uses "requires verification", etc.)
7. Missing financial data handling
8. Missing physical progress data handling
9. Missing both datasets handling
10. Cancelled / dropped project handling (score=0, NOT_APPLICABLE)
11. Fallback financial calculation (expenditure / sanctioned)
12. Configurable thresholds (custom tolerance, moderate, high, critical gap)
13. Live database evaluation against real projects
"""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.models.project import Project, Financial, Progress
from app.schemas.risk_engine import RiskLevel, EngineResult
from app.services.risk.progress_mismatch_engine import ProgressMismatchEngine


@pytest.fixture
def db_session():
    """Provides an active database session against PostgreSQL."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def progress_engine():
    """ProgressMismatchEngine instance with standard thresholds."""
    return ProgressMismatchEngine(
        tolerance=15.0,
        moderate_gap=25.0,
        high_gap=40.0,
        critical_gap=60.0,
    )


# =============================================================================
# 1. Output Schema & Conformance Tests
# =============================================================================

class TestProgressMismatchSchema:

    def test_schema_keys_and_structure(self, db_session, progress_engine):
        """EngineResult must output the exact requested JSON keys and structure."""
        result = progress_engine.evaluate("MPLADS-2024-0001", db=db_session)
        assert isinstance(result, EngineResult)
        d = result.to_dict()

        expected_keys = {"engine", "score", "risk_level", "reason", "details", "confidence"}
        assert set(d.keys()) == expected_keys
        assert d["engine"] == "progress_mismatch"
        assert 0 <= d["score"] <= 100
        assert d["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert isinstance(d["reason"], str) and len(d["reason"]) > 0
        assert isinstance(d["details"], dict)
        assert 0.0 <= d["confidence"] <= 1.0

    def test_mandatory_details_fields_present(self, db_session, progress_engine):
        """Details must contain financial_progress, physical_progress, and progress_gap."""
        result = progress_engine.evaluate("MPLADS-2024-0001", db=db_session)
        details = result.details

        assert "financial_progress" in details
        assert "physical_progress" in details
        assert "progress_gap" in details
        assert isinstance(details["financial_progress"], (int, float))
        assert isinstance(details["physical_progress"], (int, float))
        assert isinstance(details["progress_gap"], (int, float))


# =============================================================================
# 2. Balanced Execution Tests (|gap| <= tolerance)
# =============================================================================

class TestBalancedProgressExecution:

    def test_perfectly_balanced_progress(self, progress_engine):
        """Zero gap must result in score 0, LOW risk level, and balanced direction."""
        mock_db = MagicMock()
        proj = Project(project_id="P-BAL-0", current_status="In Progress")
        fin = Financial(
            project_id="P-BAL-0",
            sanctioned_amount=Decimal("1000000.00"),
            released_amount=Decimal("1000000.00"),
            expenditure_amount=Decimal("500000.00"),
        )
        prog = Progress(
            project_id="P-BAL-0",
            physical_progress_pct=Decimal("50.00"),
            financial_progress_pct=Decimal("50.00"),
        )

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, fin, prog]

        res = progress_engine.evaluate("P-BAL-0", db=mock_db)

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.details["financial_progress"] == 50.0
        assert res.details["physical_progress"] == 50.0
        assert res.details["progress_gap"] == 0.0
        assert res.details["direction"] == "balanced"
        assert "perfectly aligned" in res.reason.lower()

    def test_mild_gap_within_tolerance(self, progress_engine):
        """A mild gap of 10% (within 15% tolerance) must remain LOW risk (score < 30)."""
        mock_db = MagicMock()
        proj = Project(project_id="P-MILD", current_status="In Progress")
        fin = Financial(
            project_id="P-MILD",
            sanctioned_amount=Decimal("1000000.00"),
            released_amount=Decimal("1000000.00"),
            expenditure_amount=Decimal("350000.00"),
        )
        prog = Progress(
            project_id="P-MILD",
            physical_progress_pct=Decimal("25.00"),
            financial_progress_pct=Decimal("35.00"),
        )

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, fin, prog]

        res = progress_engine.evaluate("P-MILD", db=mock_db)

        assert res.details["progress_gap"] == 10.0
        assert res.score < 30
        assert res.risk_level == RiskLevel.LOW.value
        assert res.details["direction"] == "balanced"
        assert "well aligned" in res.reason.lower()


# =============================================================================
# 3. Direction 1: Financial Leading (Financial >> Physical)
# =============================================================================

class TestFinancialLeadingMismatch:

    def test_moderate_financial_lead(self, progress_engine):
        """
        Financial progress (40%) leads physical progress (20%) by +20 points.
        Must trigger MEDIUM risk level with clear governance explanation.
        """
        mock_db = MagicMock()
        proj = Project(project_id="P-FIN-MOD", current_status="In Progress")
        fin = Financial(
            project_id="P-FIN-MOD",
            sanctioned_amount=Decimal("2000000.00"),
            released_amount=Decimal("1000000.00"),
            expenditure_amount=Decimal("400000.00"),
        )
        prog = Progress(
            project_id="P-FIN-MOD",
            physical_progress_pct=Decimal("20.00"),
            financial_progress_pct=Decimal("40.00"),
        )

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, fin, prog]

        res = progress_engine.evaluate("P-FIN-MOD", db=mock_db)

        assert res.details["progress_gap"] == 20.0
        assert res.details["direction"] == "financial_leading"
        assert 30 <= res.score <= 59
        assert res.risk_level == RiskLevel.MEDIUM.value
        assert "significant financial/physical gap" in res.reason.lower()
        assert "requires verification" in res.reason.lower()
        # Verify non-accusatory tone
        assert "fraud" not in res.reason.lower()
        assert "corrupt" not in res.reason.lower()

    def test_critical_financial_lead(self, progress_engine):
        """
        Financial progress (90%) drastically leads physical progress (25%) by +65 points.
        Must assign CRITICAL risk level (score >= 80).
        """
        mock_db = MagicMock()
        proj = Project(project_id="P-FIN-CRIT", current_status="In Progress")
        fin = Financial(
            project_id="P-FIN-CRIT",
            sanctioned_amount=Decimal("5000000.00"),
            released_amount=Decimal("5000000.00"),
            expenditure_amount=Decimal("4500000.00"),
        )
        prog = Progress(
            project_id="P-FIN-CRIT",
            physical_progress_pct=Decimal("25.00"),
            financial_progress_pct=Decimal("90.00"),
        )

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, fin, prog]

        res = progress_engine.evaluate("P-FIN-CRIT", db=mock_db)

        assert res.details["progress_gap"] == 65.0
        assert res.details["direction"] == "financial_leading"
        assert res.score >= 80
        assert res.risk_level == RiskLevel.CRITICAL.value
        assert "requires verification" in res.reason.lower()


# =============================================================================
# 4. Direction 2: Physical Leading (Physical >> Financial)
# =============================================================================

class TestPhysicalLeadingMismatch:

    def test_moderate_physical_lead(self, progress_engine):
        """
        Physical progress (60%) leads financial progress (35%) by 25 points (gap = -25%).
        Must flag physical_leading with MEDIUM risk.
        """
        mock_db = MagicMock()
        proj = Project(project_id="P-PHY-MOD", current_status="In Progress")
        fin = Financial(
            project_id="P-PHY-MOD",
            sanctioned_amount=Decimal("2000000.00"),
            released_amount=Decimal("1000000.00"),
            expenditure_amount=Decimal("350000.00"),
        )
        prog = Progress(
            project_id="P-PHY-MOD",
            physical_progress_pct=Decimal("60.00"),
            financial_progress_pct=Decimal("35.00"),
        )

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, fin, prog]

        res = progress_engine.evaluate("P-PHY-MOD", db=mock_db)

        assert res.details["progress_gap"] == -25.0
        assert res.details["direction"] == "physical_leading"
        assert 30 <= res.score <= 59
        assert res.risk_level == RiskLevel.MEDIUM.value
        assert "contractor payment backlog" in res.reason.lower() or "delayed measurement" in res.reason.lower()

    def test_severe_physical_lead(self, progress_engine):
        """
        Physical progress (80%) drastically leads recorded expenditure (20%) by 60 points (gap = -60%).
        Must assign HIGH/CRITICAL risk (score >= 70) and report backlog/measurement delay.
        """
        mock_db = MagicMock()
        proj = Project(project_id="P-PHY-HIGH", current_status="In Progress")
        fin = Financial(
            project_id="P-PHY-HIGH",
            sanctioned_amount=Decimal("4000000.00"),
            released_amount=Decimal("2000000.00"),
            expenditure_amount=Decimal("800000.00"),
        )
        prog = Progress(
            project_id="P-PHY-HIGH",
            physical_progress_pct=Decimal("80.00"),
            financial_progress_pct=Decimal("20.00"),
        )

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, fin, prog]

        res = progress_engine.evaluate("P-PHY-HIGH", db=mock_db)

        assert res.details["progress_gap"] == -60.0
        assert res.details["direction"] == "physical_leading"
        assert res.score >= 70
        assert res.risk_level in {RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}
        assert "requires verification" in res.reason.lower()


# =============================================================================
# 5. Missing Values & Edge Cases
# =============================================================================

class TestProgressMismatchEdgeCases:

    def test_missing_both_datasets(self, progress_engine):
        """Missing both financial and progress records returns score 0 and confidence 0.0."""
        mock_db = MagicMock()
        proj = Project(project_id="P-NO-DATA", current_status="In Progress")
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, None, None]

        res = progress_engine.evaluate("P-NO-DATA", db=mock_db)

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.confidence == 0.0
        assert res.details["missing_data"] is True
        assert res.details["missing_type"] == "both"
        assert "requires verification" in res.reason.lower()

    def test_missing_financial_data(self, progress_engine):
        """Missing financial record returns score 0 and reduced confidence 0.30."""
        mock_db = MagicMock()
        proj = Project(project_id="P-NO-FIN", current_status="In Progress")
        prog = Progress(project_id="P-NO-FIN", physical_progress_pct=Decimal("45.00"))
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, None, prog]

        res = progress_engine.evaluate("P-NO-FIN", db=mock_db)

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.confidence == 0.30
        assert res.details["missing_type"] == "financial"
        assert "financial expenditure records are not documented" in res.reason.lower()

    def test_missing_physical_data(self, progress_engine):
        """Missing physical milestone returns score 0 and reduced confidence 0.30."""
        mock_db = MagicMock()
        proj = Project(project_id="P-NO-PHY", current_status="In Progress")
        fin = Financial(
            project_id="P-NO-PHY",
            sanctioned_amount=Decimal("1000000.00"),
            expenditure_amount=Decimal("200000.00"),
        )
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, fin, None]

        res = progress_engine.evaluate("P-NO-PHY", db=mock_db)

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.confidence == 0.30
        assert res.details["missing_type"] == "physical"
        assert "physical progress milestones have not been reported" in res.reason.lower()

    def test_cancelled_project_zero_risk(self, progress_engine):
        """Cancelled or dropped project should return score 0 and NOT_APPLICABLE."""
        mock_db = MagicMock()
        proj = Project(project_id="P-CANCELLED", current_status="Cancelled")
        mock_db.execute.return_value.scalar_one_or_none.return_value = proj

        res = progress_engine.evaluate("P-CANCELLED", db=mock_db)

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.details["completion_status"] == "NOT_APPLICABLE"
        assert res.confidence == 1.0

    def test_financial_progress_fallback_calculation(self, progress_engine):
        """
        When financial_progress_pct is not recorded in Progress table,
        engine must accurately compute it from expenditure / sanctioned.
        """
        mock_db = MagicMock()
        proj = Project(project_id="P-FALLBACK", current_status="In Progress")
        # Sanctioned: 2,000,000 | Exp: 800,000 -> 40.0%
        fin = Financial(
            project_id="P-FALLBACK",
            sanctioned_amount=Decimal("2000000.00"),
            released_amount=Decimal("1000000.00"),
            expenditure_amount=Decimal("800000.00"),
        )
        # Progress table has physical_progress_pct but null financial_progress_pct
        prog = Progress(
            project_id="P-FALLBACK",
            physical_progress_pct=Decimal("40.00"),
            financial_progress_pct=None,
        )

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, fin, prog]

        res = progress_engine.evaluate("P-FALLBACK", db=mock_db)

        assert res.details["financial_progress"] == 40.0
        assert res.details["physical_progress"] == 40.0
        assert res.details["progress_gap"] == 0.0
        assert res.score == 0
        assert res.details["direction"] == "balanced"

    def test_configurable_thresholds(self):
        """Validates custom thresholds and runtime context overrides."""
        engine = ProgressMismatchEngine(
            tolerance=10.0,
            moderate_gap=20.0,
            high_gap=35.0,
            critical_gap=50.0,
        )
        assert engine.tolerance == 10.0
        assert engine.moderate_gap == 20.0
        assert engine.high_gap == 35.0
        assert engine.critical_gap == 50.0


# =============================================================================
# 6. Live Database Evaluation Tests
# =============================================================================

class TestProgressMismatchLiveDatabase:

    def test_evaluate_live_database_project(self, db_session, progress_engine):
        """Evaluates progress mismatch engine on live PostgreSQL project."""
        result = progress_engine.evaluate("MPLADS-2024-0001", db=db_session)
        assert result.engine == "progress_mismatch"
        assert isinstance(result.score, int)
        assert 0 <= result.score <= 100
        assert result.risk_level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert result.confidence > 0.0
        assert "financial_progress" in result.details
        assert "physical_progress" in result.details
        assert "progress_gap" in result.details

    def test_live_high_mismatch_financial_leading(self, db_session, progress_engine):
        """MPLADS-2024-0007 has 40% financial progress vs 10% physical (gap = +30%)."""
        result = progress_engine.evaluate("MPLADS-2024-0007", db=db_session)
        assert result.details["progress_gap"] == 30.0
        assert result.details["direction"] == "financial_leading"
        assert 60 <= result.score <= 79
        assert result.risk_level == RiskLevel.HIGH.value
        assert "significant financial/physical gap" in result.reason.lower()
        assert "requires verification" in result.reason.lower()

    def test_live_high_mismatch_physical_leading(self, db_session, progress_engine):
        """MPLADS-2024-0010 has 20% financial progress vs 65% physical (gap = -45%)."""
        result = progress_engine.evaluate("MPLADS-2024-0010", db=db_session)
        assert result.details["progress_gap"] == -45.0
        assert result.details["direction"] == "physical_leading"
        assert 60 <= result.score <= 79
        assert result.risk_level == RiskLevel.HIGH.value
        assert "contractor payment backlog" in result.reason.lower() or "delayed measurement" in result.reason.lower()


# =============================================================================
# 7. Boundary Conditions & Safety Tests
# =============================================================================

class TestProgressMismatchBoundaries:

    def test_exact_tolerance_boundary(self, progress_engine):
        """At exactly gap = tolerance (15.0%), score must be 29 (top of LOW risk)."""
        mock_db = MagicMock()
        proj = Project(project_id="P-TOL-BOUND", current_status="In Progress")
        fin = Financial(project_id="P-TOL-BOUND", sanctioned_amount=Decimal("1000000.00"), expenditure_amount=Decimal("350000.00"))
        prog = Progress(project_id="P-TOL-BOUND", physical_progress_pct=Decimal("20.00"), financial_progress_pct=Decimal("35.00"))
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, fin, prog]

        res = progress_engine.evaluate("P-TOL-BOUND", db=mock_db)
        assert res.details["progress_gap"] == 15.0
        assert res.score == 29
        assert res.risk_level == RiskLevel.LOW.value
        assert res.details["direction"] == "balanced"

    def test_exact_moderate_gap_boundary(self, progress_engine):
        """At exactly gap = moderate_gap (25.0%), score must be 59 (top of MEDIUM risk)."""
        mock_db = MagicMock()
        proj = Project(project_id="P-MOD-BOUND", current_status="In Progress")
        fin = Financial(project_id="P-MOD-BOUND", sanctioned_amount=Decimal("1000000.00"), expenditure_amount=Decimal("450000.00"))
        prog = Progress(project_id="P-MOD-BOUND", physical_progress_pct=Decimal("20.00"), financial_progress_pct=Decimal("45.00"))
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, fin, prog]

        res = progress_engine.evaluate("P-MOD-BOUND", db=mock_db)
        assert res.details["progress_gap"] == 25.0
        assert res.score == 59
        assert res.risk_level == RiskLevel.MEDIUM.value
        assert res.details["direction"] == "financial_leading"

    def test_unstarted_project_zero_mismatch(self, progress_engine):
        """Unstarted project with 0% physical and 0% financial has 0 score and LOW risk."""
        mock_db = MagicMock()
        proj = Project(project_id="P-UNSTARTED", current_status="Sanctioned")
        fin = Financial(project_id="P-UNSTARTED", sanctioned_amount=Decimal("1000000.00"), expenditure_amount=Decimal("0.00"))
        prog = Progress(project_id="P-UNSTARTED", physical_progress_pct=Decimal("0.00"), financial_progress_pct=Decimal("0.00"))
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [proj, fin, prog]

        res = progress_engine.evaluate("P-UNSTARTED", db=mock_db)
        assert res.details["progress_gap"] == 0.0
        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value

    def test_inverted_thresholds_safety(self):
        """Engine should safely re-order inverted thresholds to prevent division errors."""
        engine = ProgressMismatchEngine(
            tolerance=30.0,
            moderate_gap=20.0,
            high_gap=15.0,
            critical_gap=10.0,
        )
        assert engine.tolerance == 30.0
        assert engine.moderate_gap > engine.tolerance
        assert engine.high_gap > engine.moderate_gap
        assert engine.critical_gap > engine.high_gap

