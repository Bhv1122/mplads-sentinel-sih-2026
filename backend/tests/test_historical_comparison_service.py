"""
backend/tests/test_historical_comparison_service.py
=============================================================================
Unit Test Suite for Historical Comparison Service (Phase 11).
Tests:
- First ingestion (baseline creation)
- Meaningful changes across all fields
- Unchanged data (idempotency / no-op)
- Insignificant numeric differences (floating-point tolerance)
- Missing and null values handling
- Structured summary generation
=============================================================================
"""

import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from app.database import SessionLocal
from app.models.project import Project, ProjectSnapshot
from app.services.historical_comparison_service import (
    HistoricalComparisonService,
    ComparisonTolerances,
    ComparisonResult,
    FieldChange
)


@pytest.fixture(scope="module")
def db_session():
    """Provides a transactional database session for tests."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_snapshot():
    """Generates an in-memory ProjectSnapshot instance for isolated testing."""
    return ProjectSnapshot(
        snapshot_id=101,
        project_id="TEST-PROJ-001",
        snapshot_datetime=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        snapshot_date=date(2026, 1, 15),
        project_status="Sanctioned",
        recommended_amount=Decimal("5000000.00"),
        sanctioned_amount=Decimal("4800000.00"),
        released_amount=Decimal("2000000.00"),
        expenditure_amount=Decimal("1500000.00"),
        unspent_balance=Decimal("500000.00"),
        utilization_rate_pct=Decimal("75.00"),
        cost_overrun_amount=Decimal("0.00"),
        physical_progress_pct=Decimal("30.00"),
        financial_progress_pct=Decimal("31.25"),
        expected_completion_date=date(2026, 12, 31),
        actual_completion_date=None,
        days_delayed=0,
        milestone_status="On Track",
        cost_deviation=Decimal("0.00"),
        progress_gap=Decimal("1.25"),
        derived_metrics={"burn_rate": 1.0},
        overall_risk_score=Decimal("25.50"),
        risk_level="Low",
        change_summary="Initial baseline snapshot."
    )


class TestFirstEverIngestion:
    """Tests handling of first-ever project ingestion when no prior snapshot exists."""

    def test_first_ingestion_creates_baseline(self):
        incoming = {
            "project_status": "Sanctioned",
            "sanctioned_amount": Decimal("5000000.00"),
            "physical_progress_pct": Decimal("10.00"),
            "overall_risk_score": Decimal("20.00")
        }

        result = HistoricalComparisonService.compare_data(None, incoming)

        assert result.is_initial is True
        assert result.has_meaningful_changes is True
        assert result.changes_count == 1
        assert "Initial baseline" in result.change_summary_text
        assert result.structured_summary["event"] == "initial_baseline"


class TestMeaningfulChanges:
    """Tests detection of real, concrete modifications across various dimensions."""

    def test_status_transition_detected(self, mock_snapshot):
        incoming = {
            "project_status": "In Progress"
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is True
        assert result.changes_count == 1
        change = result.field_changes[0]
        assert change.field_name == "project_status"
        assert change.previous_value == "Sanctioned"
        assert change.new_value == "In Progress"
        assert "changed from 'Sanctioned' to 'In Progress'" in change.summary

    def test_financial_expenditure_and_released_changes(self, mock_snapshot):
        incoming = {
            "released_amount": Decimal("3000000.00"),     # +1,000,000
            "expenditure_amount": Decimal("2200000.00"),  # +700,000
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is True
        assert result.changes_count == 2
        fields = {c.field_name: c for c in result.field_changes}
        
        assert "released_amount" in fields
        assert fields["released_amount"].delta == 1000000.0
        assert fields["released_amount"].delta_pct == 50.0

        assert "expenditure_amount" in fields
        assert fields["expenditure_amount"].delta == 700000.0
        assert fields["expenditure_amount"].delta_pct == pytest.approx(46.67, 0.01)

    def test_physical_and_financial_progress_advance(self, mock_snapshot):
        incoming = {
            "physical_progress_pct": Decimal("45.00"),   # +15.0%
            "financial_progress_pct": Decimal("45.83")   # +14.58%
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is True
        assert result.changes_count == 2
        fields = {c.field_name: c for c in result.field_changes}

        assert fields["physical_progress_pct"].delta == 15.0
        assert "changed from 30.0% to 45.0%" in fields["physical_progress_pct"].summary

    def test_timeline_and_delay_changes(self, mock_snapshot):
        incoming = {
            "expected_completion_date": date(2027, 3, 31), # Extension
            "days_delayed": 45,
            "milestone_status": "Delayed"
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is True
        assert result.changes_count == 3
        fields = {c.field_name: c for c in result.field_changes}

        assert fields["expected_completion_date"].new_value == "2027-03-31"
        assert fields["days_delayed"].delta == 45
        assert fields["milestone_status"].new_value == "Delayed"

    def test_risk_score_escalation(self, mock_snapshot):
        incoming = {
            "overall_risk_score": Decimal("65.20"), # +39.7
            "risk_level": "High"
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is True
        assert result.changes_count == 2
        fields = {c.field_name: c for c in result.field_changes}

        assert fields["overall_risk_score"].delta == pytest.approx(39.7, 0.01)
        assert fields["risk_level"].previous_value == "Low"
        assert fields["risk_level"].new_value == "High"


class TestUnchangedData:
    """Tests that identical incoming data produces no changes and no new snapshot."""

    def test_identical_data_produces_no_changes(self, mock_snapshot):
        incoming = {
            "project_status": "Sanctioned",
            "recommended_amount": Decimal("5000000.00"),
            "sanctioned_amount": Decimal("4800000.00"),
            "released_amount": Decimal("2000000.00"),
            "expenditure_amount": Decimal("1500000.00"),
            "physical_progress_pct": Decimal("30.00"),
            "financial_progress_pct": Decimal("31.25"),
            "expected_completion_date": date(2026, 12, 31),
            "days_delayed": 0,
            "milestone_status": "On Track",
            "overall_risk_score": Decimal("25.50"),
            "risk_level": "Low"
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is False
        assert result.changes_count == 0
        assert len(result.field_changes) == 0
        assert "No meaningful project changes detected" in result.change_summary_text


class TestInsignificantNumericDifferences:
    """Tests that floating-point jitter and sub-tolerance deltas are ignored."""

    def test_monetary_sub_rupee_jitter_ignored(self, mock_snapshot):
        # Difference of ₹0.40 is below the ₹1.00 tolerance
        incoming = {
            "expenditure_amount": Decimal("1500000.40")
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is False
        assert result.changes_count == 0

    def test_progress_pct_sub_tenth_percent_jitter_ignored(self, mock_snapshot):
        # Difference of 0.02% is below the 0.10% tolerance
        incoming = {
            "physical_progress_pct": Decimal("30.02")
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is False
        assert result.changes_count == 0

    def test_risk_score_sub_tenth_point_jitter_ignored(self, mock_snapshot):
        # Difference of 0.04 is below the 0.10 risk score tolerance
        incoming = {
            "overall_risk_score": Decimal("25.54")
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is False
        assert result.changes_count == 0

    def test_float_representation_micro_jitter_ignored(self, mock_snapshot):
        # Floating point conversion artifacts like 30.000000001
        incoming = {
            "physical_progress_pct": 30.000000001,
            "expenditure_amount": 1500000.0000001
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is False
        assert result.changes_count == 0


class TestMissingAndNullValues:
    """Tests resilient handling of None, missing keys, and transitions to/from None."""

    def test_null_transition_to_value_is_meaningful(self, mock_snapshot):
        # actual_completion_date was None, now set to date
        incoming = {
            "actual_completion_date": date(2026, 11, 15)
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is True
        assert result.changes_count == 1
        change = result.field_changes[0]
        assert change.field_name == "actual_completion_date"
        assert change.previous_value is None
        assert change.new_value == "2026-11-15"

    def test_both_null_produces_no_change(self, mock_snapshot):
        incoming = {
            "actual_completion_date": None
        }
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is False
        assert result.changes_count == 0

    def test_missing_keys_in_incoming_dict_are_ignored(self, mock_snapshot):
        # Empty payload or subset payload without the other keys
        incoming = {}
        result = HistoricalComparisonService.compare_data(mock_snapshot, incoming)

        assert result.has_meaningful_changes is False
        assert result.changes_count == 0


class TestDatabaseSnapshotPersistence:
    """Tests create_or_update_snapshot against live PostgreSQL session."""

    def test_create_snapshot_flow(self, db_session):
        project = db_session.query(Project).first()
        assert project is not None
        pid = project.project_id

        # 1. First-ever or forced snapshot
        snap1, res1 = HistoricalComparisonService.create_or_update_snapshot(
            db_session,
            project_id=pid,
            incoming_data={
                "project_status": "Sanctioned",
                "sanctioned_amount": Decimal("2500000.00"),
                "physical_progress_pct": Decimal("20.00"),
                "overall_risk_score": Decimal("15.00"),
                "risk_level": "Low"
            },
            force_snapshot=True
        )
        assert snap1 is not None
        assert snap1.snapshot_id is not None
        snap1_id = snap1.snapshot_id

        # 2. Identical data call should NOT create a new snapshot
        snap2, res2 = HistoricalComparisonService.create_or_update_snapshot(
            db_session,
            project_id=pid,
            incoming_data={
                "project_status": "Sanctioned",
                "sanctioned_amount": Decimal("2500000.00"),
                "physical_progress_pct": Decimal("20.00"),
                "overall_risk_score": Decimal("15.00"),
                "risk_level": "Low"
            }
        )
        assert snap2 is None
        assert res2.has_meaningful_changes is False

        # 3. Meaningful change call SHOULD create snap3
        snap3, res3 = HistoricalComparisonService.create_or_update_snapshot(
            db_session,
            project_id=pid,
            incoming_data={
                "project_status": "In Progress",
                "physical_progress_pct": Decimal("35.00")  # +15%
            }
        )
        assert snap3 is not None
        assert snap3.snapshot_id != snap1_id
        assert snap3.physical_progress_pct == Decimal("35.00")
        assert "Physical Progress changed from 20.0% to 35.0%" in snap3.change_summary

        # Clean up created test snapshots
        db_session.delete(snap3)
        db_session.delete(snap1)
        db_session.commit()
