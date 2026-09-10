"""
backend/tests/test_historical_tracking_api.py
=============================================================================
API Test Suite for Phase 11 Historical Tracking Endpoints:
1. GET /projects/{id}/history (chronological snapshots)
2. GET /projects/{id}/risk-history (chronological risk scores & detector decompositions)
3. GET /projects/{id}/changes (meaningful changes between consecutive updates)
4. Empty list [] handling for projects without historical records
5. HTTP 404 handling for unknown project IDs
6. Prefix aliases (/projects vs /api/v1/projects)
7. OpenAPI schema registration verification
=============================================================================
"""

import pytest
from decimal import Decimal
from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.project import Project, Financial, Progress, ProjectSnapshot, RiskHistory
from app.services.historical_risk_integration_service import historical_risk_integration_service

client = TestClient(app)


@pytest.fixture(scope="function")
def api_test_project():
    """Creates a dedicated project for API testing with 2 historical snapshots."""
    db = SessionLocal()
    pid = "MPLADS-API-HIST-01"

    # Clean up previous residues
    existing = db.get(Project, pid)
    if existing:
        db.delete(existing)
        db.commit()

    proj = Project(
        project_id=pid,
        project_code="TEST-API-HIST-01",
        project_title="API Historical Tracking Test Community Center",
        sector="Community Assets",
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
        recommended_amount=Decimal("4000000.00"),
        sanctioned_amount=Decimal("4000000.00"),
        released_amount=Decimal("2000000.00"),
        expenditure_amount=Decimal("500000.00"),
        utilization_rate_pct=Decimal("25.00")
    )
    db.add(fin)

    prog = Progress(
        project_id=pid,
        reported_date=date(2024, 8, 1),
        physical_progress_pct=Decimal("15.00"),
        financial_progress_pct=Decimal("12.50"),
        current_stage="Foundation",
        milestone_status="On Track"
    )
    db.add(prog)
    db.commit()

    # Step 1: Ingest Initial Baseline Snapshot
    historical_risk_integration_service.process_project_update_transactional(
        db=db,
        project_id=pid,
        update_payload={
            "current_status": "Sanctioned",
            "expenditure_amount": Decimal("500000.00"),
            "physical_progress_pct": Decimal("15.00")
        },
        performed_by="Baseline Ingester"
    )

    # Step 2: Ingest Meaningful Update 1
    historical_risk_integration_service.process_project_update_transactional(
        db=db,
        project_id=pid,
        update_payload={
            "current_status": "In Progress",
            "expenditure_amount": Decimal("1500000.00"),
            "physical_progress_pct": Decimal("45.00"),
            "days_delayed": 20,
            "milestone_status": "Delayed"
        },
        performed_by="Update 1 Ingester"
    )

    db.close()
    yield pid

    # Teardown
    cleanup_db = SessionLocal()
    try:
        cleanup_proj = cleanup_db.get(Project, pid)
        if cleanup_proj:
            cleanup_db.delete(cleanup_proj)
            cleanup_db.commit()
    except Exception:
        cleanup_db.rollback()
    finally:
        cleanup_db.close()


@pytest.fixture(scope="function")
def project_without_history():
    """Creates a project that exists in master tables but has zero snapshots/risk history."""
    db = SessionLocal()
    pid = "MPLADS-API-NOHIST-02"

    existing = db.get(Project, pid)
    if existing:
        db.delete(existing)
        db.commit()

    proj = Project(
        project_id=pid,
        project_code="TEST-API-NOHIST-02",
        project_title="Project Without Historical Records",
        sector="Health",
        state_id=34,
        constituency_id=532,
        district_name="Maldaha Uttar District",
        implementing_agency="Health Department",
        mp_name="Test MP",
        house_of_parliament="Lok Sabha",
        current_status="Recommended",
        financial_year="2024-25",
        recommendation_date=date(2024, 5, 1)
    )
    db.add(proj)
    db.commit()
    db.close()

    yield pid

    cleanup_db = SessionLocal()
    try:
        cleanup_proj = cleanup_db.get(Project, pid)
        if cleanup_proj:
            cleanup_db.delete(cleanup_proj)
            cleanup_db.commit()
    except Exception:
        cleanup_db.rollback()
    finally:
        cleanup_db.close()


# =============================================================================
# 1. GET /projects/{id}/history Tests
# =============================================================================

def test_get_project_history_success(api_test_project):
    """Verifies GET /projects/{id}/history returns chronological snapshots with expected fields."""
    pid = api_test_project
    resp = client.get(f"/projects/{pid}/history")
    assert resp.status_code == 200

    snapshots = resp.json()
    assert isinstance(snapshots, list)
    assert len(snapshots) == 2

    # Check ascending chronological order by default
    assert snapshots[0]["snapshot_datetime"] <= snapshots[1]["snapshot_datetime"]

    # Verify snapshot #1 (baseline)
    s1 = snapshots[0]
    assert s1["project_id"] == pid
    assert s1["project_status"] == "Sanctioned"
    assert Decimal(str(s1["expenditure_amount"])) == Decimal("500000.00")
    assert Decimal(str(s1["physical_progress_pct"])) == Decimal("15.00")
    assert "overall_risk_score" in s1
    assert "risk_level" in s1
    assert "snapshot_date" in s1
    assert "snapshot_datetime" in s1
    assert "change_summary" in s1

    # Verify snapshot #2 (update)
    s2 = snapshots[1]
    assert s2["project_status"] == "In Progress"
    assert Decimal(str(s2["expenditure_amount"])) == Decimal("1500000.00")
    assert Decimal(str(s2["physical_progress_pct"])) == Decimal("45.00")
    assert s2["days_delayed"] == 20
    assert s2["milestone_status"] == "Delayed"


def test_get_project_history_sort_order_and_limit(api_test_project):
    """Verifies sort_order=desc and limit parameters for /history."""
    pid = api_test_project
    resp = client.get(f"/projects/{pid}/history?sort_order=desc&limit=1")
    assert resp.status_code == 200

    snapshots = resp.json()
    assert len(snapshots) == 1
    # Most recent snapshot should be returned first in desc order
    assert snapshots[0]["project_status"] == "In Progress"


def test_get_project_history_empty_response(project_without_history):
    """Verifies that an existing project with no historical records returns an empty list []."""
    pid = project_without_history
    resp = client.get(f"/projects/{pid}/history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_project_history_not_found():
    """Verifies HTTP 404 for unknown project ID."""
    resp = client.get("/projects/NONEXISTENT-PROJECT-999/history")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# =============================================================================
# 2. GET /projects/{id}/risk-history Tests
# =============================================================================

def test_get_project_risk_history_success(api_test_project):
    """Verifies GET /projects/{id}/risk-history returns chronological risk assessments."""
    pid = api_test_project
    resp = client.get(f"/projects/{pid}/risk-history")
    assert resp.status_code == 200

    risks = resp.json()
    assert isinstance(risks, list)
    assert len(risks) == 2

    r1 = risks[0]
    assert r1["project_id"] == pid
    assert "overall_risk_score" in r1
    assert "risk_level" in r1
    assert "detector_scores" in r1
    assert "calculated_at" in r1
    assert r1["snapshot_id"] is not None

    # Check detector breakdown
    det = r1["detector_scores"]
    assert "cost_anomaly" in det
    assert "delay_detection" in det
    assert "fund_utilization" in det
    assert "progress_mismatch" in det


def test_get_project_risk_history_sort_and_limit(api_test_project):
    """Verifies sort_order=desc and limit for /risk-history."""
    pid = api_test_project
    resp = client.get(f"/projects/{pid}/risk-history?sort_order=desc&limit=1")
    assert resp.status_code == 200
    risks = resp.json()
    assert len(risks) == 1


def test_get_project_risk_history_empty_response(project_without_history):
    """Verifies empty list [] for project without risk history."""
    pid = project_without_history
    resp = client.get(f"/projects/{pid}/risk-history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_project_risk_history_not_found():
    """Verifies HTTP 404 for unknown project ID."""
    resp = client.get("/projects/NONEXISTENT-PROJECT-999/risk-history")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# =============================================================================
# 3. GET /projects/{id}/changes Tests
# =============================================================================

def test_get_project_changes_success(api_test_project):
    """Verifies GET /projects/{id}/changes returns structured changes between updates."""
    pid = api_test_project
    resp = client.get(f"/projects/{pid}/changes")
    assert resp.status_code == 200

    changes = resp.json()
    assert isinstance(changes, list)
    assert len(changes) == 2

    # Change 0 (baseline)
    c0 = changes[0]
    assert c0["previous_snapshot_id"] is None
    assert c0["project_status"] == "Sanctioned"
    assert "initial_baseline" in c0["modified_fields"]

    # Change 1 (update)
    c1 = changes[1]
    assert c1["previous_snapshot_id"] == c0["snapshot_id"]
    assert c1["project_status"] == "In Progress"
    assert c1["changes_count"] >= 1
    assert "project_status" in c1["modified_fields"]

    # Verify granular field_changes list
    fc_map = {fc["field_name"]: fc for fc in c1["field_changes"]}
    assert "project_status" in fc_map
    assert fc_map["project_status"]["previous_value"] == "Sanctioned"
    assert fc_map["project_status"]["new_value"] == "In Progress"

    if "expenditure_amount" in fc_map:
        assert fc_map["expenditure_amount"]["previous_value"] == 500000.0
        assert fc_map["expenditure_amount"]["new_value"] == 1500000.0
        assert fc_map["expenditure_amount"]["delta"] == 1000000.0


def test_get_project_changes_sort_order(api_test_project):
    """Verifies sort_order=desc for /changes."""
    pid = api_test_project
    resp = client.get(f"/projects/{pid}/changes?sort_order=desc")
    assert resp.status_code == 200
    changes = resp.json()
    assert len(changes) == 2
    # In desc order, the latest update comes first
    assert changes[0]["project_status"] == "In Progress"
    assert changes[1]["project_status"] == "Sanctioned"


def test_get_project_changes_empty_response(project_without_history):
    """Verifies empty list [] for project without snapshots."""
    pid = project_without_history
    resp = client.get(f"/projects/{pid}/changes")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_project_changes_not_found():
    """Verifies HTTP 404 for unknown project ID."""
    resp = client.get("/projects/NONEXISTENT-PROJECT-999/changes")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# =============================================================================
# 4. API v1 Prefix Alias Tests
# =============================================================================

def test_api_v1_prefix_aliases(api_test_project):
    """Verifies that all three endpoints work under the /api/v1 prefix alias."""
    pid = api_test_project

    # /api/v1/projects/{id}/history
    r1 = client.get(f"/api/v1/projects/{pid}/history")
    assert r1.status_code == 200
    assert len(r1.json()) == 2

    # /api/v1/projects/{id}/risk-history
    r2 = client.get(f"/api/v1/projects/{pid}/risk-history")
    assert r2.status_code == 200
    assert len(r2.json()) == 2

    # /api/v1/projects/{id}/changes
    r3 = client.get(f"/api/v1/projects/{pid}/changes")
    assert r3.status_code == 200
    assert len(r3.json()) == 2


# =============================================================================
# 5. Swagger / OpenAPI Documentation Verification
# =============================================================================

def test_openapi_schema_includes_historical_endpoints():
    """Verifies that all three endpoints are registered in OpenAPI schema."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema.get("paths", {})

    assert "/projects/{id}/history" in paths
    assert "get" in paths["projects/{id}/history".replace("projects", "/projects")]

    assert "/projects/{id}/risk-history" in paths
    assert "get" in paths["/projects/{id}/risk-history"]

    assert "/projects/{id}/changes" in paths
    assert "get" in paths["/projects/{id}/changes"]
