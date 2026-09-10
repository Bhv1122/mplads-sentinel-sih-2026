"""
backend/tests/test_delay_detection_engine.py
=============================================================================
Comprehensive Test Suite for Engine 3: Delay Detection Engine.
=============================================================================

Tests:
1. Exact Schema & Return Contract (engine, score, risk_level, reason, details, confidence)
2. Mandatory Details Fields (overdue_days, delay_percentage, status)
3. Completed on time (actual <= expected -> overdue_days=0, score=0, LOW risk)
4. Completed late (actual > expected -> overdue_days > 0, score > 0, schedule overrun)
5. Ongoing on schedule (current date <= expected -> overdue_days=0, score=0, LOW risk)
6. Ongoing overdue (current date > expected -> overdue_days > 0, score normalized)
7. Missing dates (expected_completion_date is None -> score=0, confidence=0.0)
8. Invalid dates (reverse timeline where expected < start -> safe fallback)
9. Cancelled / Dropped projects (score=0, LOW risk, NOT_APPLICABLE)
10. Configurable thresholds (custom low, medium, high, critical days)
11. Live database project evaluation
12. Non-existent project handling
"""

import os
import sys
from datetime import date
from unittest.mock import MagicMock
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.models.project import Project
from app.schemas.risk_engine import RiskLevel, EngineResult
from app.services.risk.delay_detection_engine import DelayDetectionEngine


@pytest.fixture
def db_session():
    """Provides an active database session against PostgreSQL."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def delay_engine():
    """DelayDetectionEngine instance with standard thresholds."""
    return DelayDetectionEngine(
        low_days=30,
        medium_days=90,
        high_days=180,
        critical_days=365,
    )


# =============================================================================
# 1. Output Schema & Conformance Tests
# =============================================================================

class TestDelayDetectionSchema:

    def test_schema_keys_and_structure(self, db_session, delay_engine):
        """EngineResult must output the exact requested JSON keys and structure."""
        result = delay_engine.evaluate("MPLADS-2024-0001", db=db_session)
        assert isinstance(result, EngineResult)
        d = result.to_dict()

        expected_keys = {"engine", "score", "risk_level", "reason", "details", "confidence"}
        assert set(d.keys()) == expected_keys
        assert d["engine"] == "delay_detection"
        assert 0 <= d["score"] <= 100
        assert d["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert isinstance(d["reason"], str) and len(d["reason"]) > 0
        assert isinstance(d["details"], dict)
        assert 0.0 <= d["confidence"] <= 1.0

    def test_mandatory_details_fields_present(self, db_session, delay_engine):
        """Details must contain overdue_days, delay_percentage, and status as specified."""
        result = delay_engine.evaluate("MPLADS-2024-0001", db=db_session)
        details = result.details

        assert "overdue_days" in details
        assert "delay_percentage" in details
        assert "status" in details
        assert isinstance(details["overdue_days"], int)
        assert isinstance(details["delay_percentage"], (int, float))
        assert isinstance(details["status"], str)


# =============================================================================
# 2. Core Delay Scenarios
# =============================================================================

class TestDelayDetectionScenarios:

    def test_completed_on_time(self, delay_engine):
        """
        Completed on time: Actual completion date <= Expected completion date.
        Must result in overdue_days=0, score=0, and LOW risk level.
        """
        mock_db = MagicMock()
        target = Project(
            project_id="P-COMP-ONTIME",
            current_status="Completed",
            sanction_date=date(2024, 1, 1),
            work_order_date=date(2024, 1, 15),
            expected_completion_date=date(2024, 6, 30),
            actual_completion_date=date(2024, 6, 15), # 15 days ahead of schedule
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = delay_engine.evaluate("P-COMP-ONTIME", db=mock_db)

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.details["overdue_days"] == 0
        assert res.details["delay_percentage"] == 0
        assert res.details["status"] == "completed"
        assert res.details["completion_status"] == "COMPLETED_ON_TIME"
        assert res.details["early_days"] == 15
        assert res.confidence >= 0.90
        assert "on schedule" in res.reason.lower()

    def test_completed_late(self, delay_engine):
        """
        Completed late: Actual completion date > Expected completion date.
        Must accurately calculate overdue days, delay percentage, and normalized risk score.
        """
        mock_db = MagicMock()
        # Planned duration: 180 days (Jan 1 to Jun 29)
        # Actual: Oct 27 (120 days late) -> in medium-to-high band (90-180 days)
        target = Project(
            project_id="P-COMP-LATE",
            current_status="Completed",
            sanction_date=date(2024, 1, 1),
            work_order_date=date(2024, 1, 1),
            expected_completion_date=date(2024, 6, 29),
            actual_completion_date=date(2024, 10, 27), # 120 days overdue
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = delay_engine.evaluate("P-COMP-LATE", db=mock_db)

        assert res.details["overdue_days"] == 120
        assert res.details["delay_percentage"] > 50.0
        assert res.details["status"] == "completed"
        assert res.details["completion_status"] == "COMPLETED_LATE"
        assert 60 <= res.score <= 79
        assert res.risk_level == RiskLevel.HIGH.value
        assert "120 days behind" in res.reason

    def test_ongoing_on_schedule(self, delay_engine):
        """
        Ongoing on schedule: Reference date <= Expected completion date.
        Do NOT flag an ongoing project as delayed if its expected completion date has not passed!
        Must return score=0, overdue_days=0, and LOW risk level.
        """
        mock_db = MagicMock()
        target = Project(
            project_id="P-ONGOING-GOOD",
            current_status="In Progress",
            sanction_date=date(2024, 1, 1),
            work_order_date=date(2024, 2, 1),
            expected_completion_date=date(2024, 12, 31),
            actual_completion_date=None,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        # Reference date is August 1, 2024 (well before Dec 31)
        res = delay_engine.evaluate(
            "P-ONGOING-GOOD",
            db=mock_db,
            context={"as_of_date": "2024-08-01"}
        )

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.details["overdue_days"] == 0
        assert res.details["delay_percentage"] == 0
        assert res.details["status"] == "in progress"
        assert res.details["completion_status"] == "ONGOING_ON_SCHEDULE"
        assert res.details["days_remaining"] == 152
        assert "on schedule" in res.reason.lower()

    def test_ongoing_overdue(self, delay_engine):
        """
        Ongoing overdue: Reference date > Expected completion date.
        Must flag project as overdue, compute delay percentage, and assign escalated score.
        """
        mock_db = MagicMock()
        # Expected completion was June 30, 2024.
        # Reference date is November 15, 2024 (138 days overdue).
        target = Project(
            project_id="P-ONGOING-LATE",
            current_status="In Progress",
            sanction_date=date(2024, 1, 1),
            work_order_date=date(2024, 1, 15),
            expected_completion_date=date(2024, 6, 30),
            actual_completion_date=None,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = delay_engine.evaluate(
            "P-ONGOING-LATE",
            db=mock_db,
            context={"as_of_date": "2024-11-15"}
        )

        assert res.details["overdue_days"] == 138
        assert res.details["delay_percentage"] > 70.0
        assert res.details["status"] == "in progress"
        assert res.details["completion_status"] == "ONGOING_OVERDUE"
        assert 60 <= res.score <= 79
        assert res.risk_level == RiskLevel.HIGH.value
        assert "138 days overdue" in res.reason

    def test_chronic_delay_critical_risk(self, delay_engine):
        """Overdue days exceeding 365 days must produce CRITICAL risk level (80-100)."""
        mock_db = MagicMock()
        target = Project(
            project_id="P-CHRONIC",
            current_status="In Progress",
            sanction_date=date(2022, 1, 1),
            work_order_date=date(2022, 1, 15),
            expected_completion_date=date(2022, 12, 31),
            actual_completion_date=None,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        # As of Sept 2024 (> 600 days overdue)
        res = delay_engine.evaluate(
            "P-CHRONIC",
            db=mock_db,
            context={"as_of_date": "2024-09-01"}
        )

        assert res.details["overdue_days"] > 600
        assert res.score >= 80
        assert res.risk_level == RiskLevel.CRITICAL.value


# =============================================================================
# 3. Missing Dates, Invalid Dates & Edge Cases
# =============================================================================

class TestDelayEdgeCases:

    def test_missing_expected_completion_date(self, delay_engine):
        """Missing expected completion date should return score 0 and confidence 0.0."""
        mock_db = MagicMock()
        target = Project(
            project_id="P-NO-EXP",
            current_status="In Progress",
            sanction_date=date(2024, 1, 1),
            work_order_date=date(2024, 1, 15),
            expected_completion_date=None,
            actual_completion_date=None,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = delay_engine.evaluate("P-NO-EXP", db=mock_db)

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.confidence == 0.0
        assert res.details["missing_dates"] is True
        assert res.details["overdue_days"] == 0
        assert "not recorded" in res.reason.lower()

    def test_invalid_reverse_dates(self, delay_engine):
        """
        Invalid data entry where expected completion is before start date.
        Must handle gracefully with safety fallback without crashing.
        """
        mock_db = MagicMock()
        target = Project(
            project_id="P-REVERSE",
            current_status="In Progress",
            sanction_date=date(2024, 6, 1),
            work_order_date=date(2024, 6, 1),
            expected_completion_date=date(2024, 1, 1), # Before start!
            actual_completion_date=None,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = delay_engine.evaluate(
            "P-REVERSE",
            db=mock_db,
            context={"as_of_date": "2024-07-01"}
        )

        assert res.details["invalid_timeline"] is True
        assert res.details["overdue_days"] > 0
        assert isinstance(res.score, int)

    def test_cancelled_project_zero_risk(self, delay_engine):
        """Cancelled or dropped projects should return 0 score and NOT_APPLICABLE status."""
        mock_db = MagicMock()
        target = Project(
            project_id="P-CANCELLED",
            current_status="Cancelled",
            sanction_date=date(2024, 1, 1),
            expected_completion_date=date(2024, 3, 1),
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = delay_engine.evaluate(
            "P-CANCELLED",
            db=mock_db,
            context={"as_of_date": "2024-09-01"}
        )

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.details["completion_status"] == "NOT_APPLICABLE"
        assert res.details["overdue_days"] == 0

    def test_nonexistent_project_not_found(self, delay_engine):
        """Non-existent project should return score 0 and error details."""
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        res = delay_engine.evaluate("NONEXISTENT-PROJ", db=mock_db)

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.confidence == 0.0
        assert res.details["error"] == "not_found"

    def test_configurable_thresholds(self):
        """Engine should respect custom configurable delay day thresholds."""
        engine = DelayDetectionEngine(
            low_days=15,
            medium_days=45,
            high_days=90,
            critical_days=180,
        )
        assert engine.low_days == 15
        assert engine.medium_days == 45
        assert engine.high_days == 90
        assert engine.critical_days == 180


# =============================================================================
# 4. Live Database Evaluation Tests
# =============================================================================

class TestDelayLiveDatabase:

    def test_evaluate_live_database_project(self, db_session, delay_engine):
        """Evaluates delay detection engine on live PostgreSQL project."""
        result = delay_engine.evaluate("MPLADS-2024-0001", db=db_session)
        assert result.engine == "delay_detection"
        assert isinstance(result.score, int)
        assert 0 <= result.score <= 100
        assert result.risk_level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert result.confidence > 0.0
        assert "overdue_days" in result.details
        assert "delay_percentage" in result.details
        assert "status" in result.details


# =============================================================================
# 5. Audit & Boundary Condition Tests
# =============================================================================

class TestDelayAuditAndBoundaries:

    def test_iso_and_timezone_parsing(self, delay_engine):
        """Validates that ISO-8601 strings with Z, offsets, and datetimes are parsed accurately."""
        from datetime import datetime, timezone
        from app.services.risk.delay_detection_engine import parse_date_safe

        # ISO with Z
        d1 = parse_date_safe("2024-07-10T00:00:00Z")
        assert d1 == date(2024, 7, 10)

        # ISO with Indian timezone offset (+05:30)
        d2 = parse_date_safe("2024-07-10T14:30:00+05:30")
        assert d2 == date(2024, 7, 10)

        # UTC datetime late evening (20:00 UTC = 01:30 next morning in IST)
        utc_dt = datetime(2025, 1, 15, 20, 0, tzinfo=timezone.utc)
        d3 = parse_date_safe(utc_dt)
        assert d3 == date(2025, 1, 16)

        # Indian date format strings
        d4 = parse_date_safe("15/01/2025")
        assert d4 == date(2025, 1, 15)

        d5 = parse_date_safe("15-Jan-2025")
        assert d5 == date(2025, 1, 15)

        # Null / Empty / NaT
        assert parse_date_safe(None) is None
        assert parse_date_safe("") is None
        assert parse_date_safe("NaT") is None
        assert parse_date_safe("null") is None

    def test_day_one_mild_delay_score(self, delay_engine):
        """
        1 day overdue should yield score 1 (LOW), providing a continuous
        monotonic scale instead of an abrupt 15-point step.
        """
        mock_db = MagicMock()
        target = Project(
            project_id="P-DAY-ONE",
            current_status="In Progress",
            sanction_date=date(2024, 1, 1),
            work_order_date=date(2024, 1, 1),
            expected_completion_date=date(2024, 6, 30),
            actual_completion_date=None,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        # 1 day overdue (July 1, 2024)
        res = delay_engine.evaluate(
            "P-DAY-ONE",
            db=mock_db,
            context={"as_of_date": "2024-07-01"}
        )

        assert res.details["overdue_days"] == 1
        assert res.score == 1
        assert res.risk_level == RiskLevel.LOW.value
        assert "1 days overdue" in res.reason or "1 day" in res.reason

    def test_due_today_on_schedule(self, delay_engine):
        """
        When reference date matches expected completion date exactly (0 days remaining),
        it must be strictly on schedule with score 0 and LOW risk.
        """
        mock_db = MagicMock()
        target = Project(
            project_id="P-DUE-TODAY",
            current_status="In Progress",
            sanction_date=date(2024, 1, 1),
            work_order_date=date(2024, 1, 1),
            expected_completion_date=date(2024, 6, 30),
            actual_completion_date=None,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = delay_engine.evaluate(
            "P-DUE-TODAY",
            db=mock_db,
            context={"as_of_date": "2024-06-30"}
        )

        assert res.details["overdue_days"] == 0
        assert res.details["days_remaining"] == 0
        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert "due today" in res.reason.lower()

    def test_context_reference_date_alias(self, delay_engine):
        """Validates that context keys 'reference_date' or 'current_date' are recognized."""
        mock_db = MagicMock()
        target = Project(
            project_id="P-ALIAS",
            current_status="In Progress",
            sanction_date=date(2024, 1, 1),
            work_order_date=date(2024, 1, 1),
            expected_completion_date=date(2024, 6, 30),
            actual_completion_date=None,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = delay_engine.evaluate(
            "P-ALIAS",
            db=mock_db,
            context={"reference_date": "2024-08-15"}
        )

        assert res.details["overdue_days"] == 46
        assert res.details["as_of_date"] == "2024-08-15"

    def test_actual_before_start_date_invalid(self, delay_engine):
        """
        Completed project with actual completion before start date (corrupted record)
        must flag invalid_timeline=True safely.
        """
        mock_db = MagicMock()
        target = Project(
            project_id="P-CORRUPT",
            current_status="Completed",
            sanction_date=date(2024, 6, 1),
            work_order_date=date(2024, 6, 1),
            expected_completion_date=date(2024, 12, 31),
            actual_completion_date=date(2023, 1, 1), # Before start!
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = target

        res = delay_engine.evaluate("P-CORRUPT", db=mock_db)

        assert res.details["invalid_timeline"] is True
        assert res.details["actual_duration"] == 1

