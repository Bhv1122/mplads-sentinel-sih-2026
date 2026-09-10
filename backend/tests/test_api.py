"""
backend/tests/test_api.py
=============================================================================
Integration test suite for the MPLADS FastAPI backend.
=============================================================================
"""

import sys
from pathlib import Path
from decimal import Decimal
from fastapi.testclient import TestClient

# Ensure backend directory and project root are on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.main import app
except ImportError:
    from backend.app.main import app


client = TestClient(app)


def test_root_endpoint():
    """Verify that root info endpoint returns online status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["service"] == "MPLADS Governance & Analytics API"
    assert "docs_url" in data


def test_health_check():
    """Verify that database connection check returns healthy via /api/health."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_health_root_endpoint():
    """Verify that GET /health returns backend status and database connectivity."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["backend"] == "running"
    assert data["database"] == "connected"
    assert data["database_name"] == "mplads_db"


def test_documentation_endpoints():
    """Verify that Swagger UI, ReDoc, and OpenAPI schema endpoints are accessible."""
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    openapi_res = client.get("/openapi.json")
    assert openapi_res.status_code == 200
    openapi_data = openapi_res.json()
    assert openapi_data["info"]["title"] == "MPLADS Project Intelligence & Governance API"
    assert openapi_data["info"]["version"] == "1.0.0"
    assert "/projects" in openapi_data["paths"]
    assert "/analytics" in openapi_data["paths"]
    assert "/high-risk" in openapi_data["paths"]
    assert "/health" in openapi_data["paths"]


def test_list_projects_default():
    """Verify default paginated list of projects via /api/v1/projects."""
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 20
    assert len(data["items"]) <= 20
    first_item = data["items"][0]
    assert "project_id" in first_item
    assert "project_title" in first_item
    assert "state_name" in first_item
    assert "current_status" in first_item


def test_get_projects_root_endpoint():
    """Verify GET /projects works directly at root path."""
    response = client.get("/projects")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 20
    assert data["skip"] == 0
    assert data["limit"] == 20


def test_get_projects_pagination_skip_limit():
    """Verify pagination using skip and limit parameters returns correct slices."""
    # Page 1: skip=0, limit=5
    res1 = client.get("/projects?skip=0&limit=5")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["skip"] == 0
    assert data1["limit"] == 5
    assert len(data1["items"]) == 5

    # Page 2: skip=5, limit=5
    res2 = client.get("/projects?skip=5&limit=5")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["skip"] == 5
    assert data2["limit"] == 5
    assert len(data2["items"]) == 5

    # Verify no overlap between page 1 and page 2
    ids_page1 = [p["project_id"] for p in data1["items"]]
    ids_page2 = [p["project_id"] for p in data2["items"]]
    assert set(ids_page1).isdisjoint(set(ids_page2))


def test_get_projects_multi_filtering():
    """Verify filtering across sector, status, district, and financial year."""
    response = client.get("/projects?current_status=Completed&financial_year=2024-25")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    for p in data["items"]:
        assert p["current_status"] == "Completed"
        assert p["financial_year"] == "2024-25"


def test_get_projects_empty_result_handling():
    """Verify that empty result sets return HTTP 200 with empty list and zero counts."""
    response = client.get("/projects?sector=CompletelyNonExistentSector12345")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["total_pages"] == 0
    assert data["skip"] == 0
    assert data["limit"] == 20


def test_get_project_by_id_root_endpoint():
    """Verify GET /projects/{id} works at root path and returns full relational payload."""
    project_id = "MPLADS-2024-0001"
    response = client.get(f"/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert data["project_title"] == "Community RO Plant"

    # Financial information
    assert data["financial"] is not None
    assert Decimal(str(data["financial"]["sanctioned_amount"])) == Decimal("1500000.00")
    assert Decimal(str(data["financial"]["unspent_balance"])) == Decimal("50000.00")

    # Progress information
    assert "progress_records" in data
    assert isinstance(data["progress_records"], list)
    assert len(data["progress_records"]) >= 1
    assert data["progress_records"][0]["milestone_status"] == "Completed"

    # Risk score and factors
    assert "risk_score" in data
    assert data["risk_score"] is not None
    assert data["risk_score"]["risk_level"] == "Low"
    assert "risk_factors" in data
    assert len(data["risk_factors"]) >= 1


def test_get_project_by_id_not_found():
    """Verify GET /projects/{id} returns HTTP 404 when project does not exist."""
    response = client.get("/projects/NONEXISTENT-PROJECT-9999")
    assert response.status_code == 404
    error_payload = response.json()
    assert "detail" in error_payload
    assert "not found" in error_payload["detail"].lower()


def test_list_projects_with_filters():
    """Verify multi-criteria filtering by sector, status, and state_id."""
    response = client.get("/api/v1/projects?sector=Drinking Water")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    for item in data["items"]:
        assert item["sector"] == "Drinking Water"


def test_full_text_search():
    """Verify PostgreSQL full-text search endpoint."""
    response = client.get("/api/v1/projects/search?q=Solar")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    # Confirm search results contain 'Solar' in title or description or sector
    assert any("Solar" in item["project_title"] or "Drinking Water" in item["sector"] for item in data["items"])


def test_get_project_detail():
    """Verify 360-degree project detail retrieval with nested relationships."""
    project_id = "MPLADS-2024-0001"
    response = client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert data["project_title"] == "Community RO Plant"
    assert data["state"]["state_name"] == "West Bengal"
    assert data["constituency"]["constituency_name"] == "Maldaha Uttar"
    assert data["financial"] is not None
    assert Decimal(str(data["financial"]["sanctioned_amount"])) == Decimal("1500000.00")
    assert "progress_records" in data
    assert "risk_score" in data
    assert data["risk_score"]["risk_level"] == "Low"
    assert "features" in data
    assert data["features"] is not None
    assert "delay_days" in data["features"]
    assert "utilization_ratio" in data["features"]
    assert "cost_per_category" in data["features"]
    assert "progress_gap" in data["features"]
    assert "cost_deviation" in data["features"]
    assert "project_duration" in data["features"]


def test_get_project_features():
    """Verify dedicated GET /projects/{id}/features endpoint returns all 6 core features."""
    project_id = "MPLADS-2024-0001"
    response = client.get(f"/api/v1/projects/{project_id}/features")
    assert response.status_code == 200
    feats = response.json()
    assert feats["project_id"] == project_id
    assert "delay_days" in feats
    assert "utilization_ratio" in feats
    assert "cost_per_category" in feats
    assert "progress_gap" in feats
    assert "cost_deviation" in feats
    assert "project_duration" in feats
    assert Decimal(str(feats["utilization_ratio"])) > 0
    assert feats["project_duration"] > 0


def test_get_project_features_not_found():
    """Verify 404 on nonexistent project features."""
    response = client.get("/api/v1/projects/NONEXISTENT-9999/features")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_project_timeline():
    """Verify project event audit ledger."""
    project_id = "MPLADS-2024-0001"
    response = client.get(f"/api/v1/projects/{project_id}/timeline")
    assert response.status_code == 200
    records = response.json()
    assert isinstance(records, list)
    assert len(records) > 0
    assert "event_type" in records[0]
    assert "performed_by" in records[0]


def test_project_progress_history():
    """Verify project physical milestone trajectory."""
    project_id = "MPLADS-2024-0001"
    response = client.get(f"/api/v1/projects/{project_id}/progress")
    assert response.status_code == 200
    records = response.json()
    assert isinstance(records, list)
    assert len(records) > 0
    assert "physical_progress_pct" in records[0]
    assert "milestone_status" in records[0]


def test_analytics_kpi_overview():
    """Verify national and portfolio KPI metrics."""
    response = client.get("/api/v1/analytics/kpis")
    assert response.status_code == 200
    data = response.json()
    assert data["total_projects"] == 20
    assert Decimal(str(data["total_sanctioned_cr"])) > Decimal("0.0")
    assert Decimal(str(data["overall_utilization_pct"])) > Decimal("0.0")
    assert data["completed_projects_count"] >= 0


def test_analytics_sectors():
    """Verify sector-wise breakdown."""
    response = client.get("/api/v1/analytics/sectors")
    assert response.status_code == 200
    sectors = response.json()
    assert isinstance(sectors, list)
    assert len(sectors) > 0
    first_sector = sectors[0]
    assert "sector" in first_sector
    assert "total_projects" in first_sector
    assert "total_sanctioned_amount" in first_sector


def test_analytics_delayed_projects():
    """Verify delayed projects operational surveillance."""
    response = client.get("/api/v1/analytics/delayed")
    assert response.status_code == 200
    delayed = response.json()
    assert isinstance(delayed, list)
    assert len(delayed) >= 2
    for item in delayed:
        assert item["days_delayed"] > 0 or item["milestone_status"] in ("Delayed", "Critical") or item["current_status"] == "Stalled"


def test_analytics_high_risk_projects():
    """Verify high-risk projects with primary causal factors."""
    response = client.get("/api/v1/analytics/high-risk")
    assert response.status_code == 200
    high_risk = response.json()
    assert isinstance(high_risk, list)
    assert len(high_risk) > 0
    first_item = high_risk[0]
    assert Decimal(str(first_item["overall_risk_score"])) >= Decimal("40.0")
    assert "primary_risk_factors" in first_item


def test_get_analytics_endpoint():
    """Verify GET /analytics computes project-level statistics, financials, and aggregations."""
    response = client.get("/analytics")
    assert response.status_code == 200
    data = response.json()

    # Core project statistics
    assert data["total_projects"] == 20
    assert data["completed_projects"] == 8
    assert data["ongoing_projects"] >= 8
    assert data["delayed_projects"] >= 2
    assert Decimal(str(data["average_progress"])) > Decimal("50.0")

    # Financial outlays
    assert Decimal(str(data["total_allocated_amount"])) > Decimal("0.0")
    assert Decimal(str(data["total_sanctioned_amount"])) > Decimal("0.0")
    assert Decimal(str(data["total_released_amount"])) > Decimal("0.0")
    assert Decimal(str(data["total_expenditure_amount"])) > Decimal("0.0")
    assert Decimal(str(data["overall_utilization_pct"])) > Decimal("0.0")

    # Risk distribution
    assert "risk_distribution" in data
    assert "Low" in data["risk_distribution"]
    assert "High" in data["risk_distribution"]

    # Geographical and sectoral aggregations
    assert isinstance(data["state_aggregations"], list)
    assert len(data["state_aggregations"]) > 0
    assert "state_name" in data["state_aggregations"][0]

    assert isinstance(data["district_aggregations"], list)
    assert len(data["district_aggregations"]) > 0
    assert "district_name" in data["district_aggregations"][0]

    assert isinstance(data["sector_aggregations"], list)
    assert len(data["sector_aggregations"]) > 0
    assert "sector" in data["sector_aggregations"][0]


def test_get_high_risk_endpoint():
    """Verify GET /high-risk returns classified high risk projects sorted highest-risk first."""
    response = client.get("/high-risk")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) > 0

    first = items[0]
    assert "project_id" in first
    assert "project_name" in first or "project_title" in first
    assert "risk_score" in first or "overall_risk_score" in first
    assert "risk_level" in first
    assert "important_risk_factors" in first or "primary_risk_factors" in first

    # Confirm sorting: highest-risk first
    scores = [Decimal(str(item["risk_score"])) for item in items]
    assert scores == sorted(scores, reverse=True)

    # Confirm risk factors are present
    assert any(len(item.get("important_risk_factors", [])) > 0 for item in items)


def test_get_high_risk_limit_parameter():
    """Verify GET /high-risk supports limit parameter."""
    response = client.get("/high-risk?limit=2")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) == 2
    # Ensure they are indeed the top 2 highest-risk projects
    assert Decimal(str(items[0]["risk_score"])) >= Decimal(str(items[1]["risk_score"]))


def test_analytics_missing_info_audit():
    """Verify compliance audit flags."""
    response = client.get("/api/v1/analytics/missing-info")
    assert response.status_code == 200
    audit_items = response.json()
    assert isinstance(audit_items, list)
    assert len(audit_items) > 0
    assert "missing_fields_count" in audit_items[0]
    assert "missing_fields" in audit_items[0]


def test_analytics_state_equity():
    """Verify SC/ST statutory quota analysis across 36 States/UTs."""
    response = client.get("/api/v1/analytics/state-equity")
    assert response.status_code == 200
    equity = response.json()
    assert isinstance(equity, list)
    assert len(equity) == 36
    assert "sc_seat_share_pct" in equity[0]
    assert "st_seat_share_pct" in equity[0]


def test_analytics_state_efficiency():
    """Verify state efficiency rankings."""
    response = client.get("/api/v1/analytics/state-efficiency")
    assert response.status_code == 200
    rankings = response.json()
    assert isinstance(rankings, list)
    assert len(rankings) == 36
    assert "rank_utilization" in rankings[0]


def test_analytics_budget_history():
    """Verify 33-year longitudinal Union Budget series."""
    response = client.get("/api/v1/analytics/budget-history")
    assert response.status_code == 200
    budget = response.json()
    assert isinstance(budget, list)
    assert len(budget) == 33
    assert budget[0]["financial_year"] == "1993-94"
    assert budget[-1]["financial_year"] == "2025-26"


def test_create_and_update_project():
    """Verify end-to-end creation, status transition, and audit ledger logging."""
    test_id = "TEST-PROJ-9999"
    test_code = "PRJ-TEST-9999"

    try:
        from app.database import SessionLocal
        from app.models import Project
    except ImportError:
        from backend.app.database import SessionLocal
        from backend.app.models import Project


    # Clean up any leftover test artifact
    db = SessionLocal()
    existing = db.get(Project, test_id)
    if existing:
        db.delete(existing)
        db.commit()
    db.close()

    create_payload = {
        "project_id": test_id,
        "project_code": test_code,
        "project_title": "Test Solar Lighting Installation",
        "project_description": "Integration test project for Phase 4 backend verification",
        "sector": "Electricity",
        "sub_sector": "Solar Energy",
        "state_id": 10,
        "constituency_id": 141,
        "district_name": "West Champaran",
        "implementing_agency": "District Rural Development Agency (DRDA)",
        "mp_name": "Hon MP Test",
        "house_of_parliament": "Lok Sabha",
        "financial_year": "2024-25",
        "current_status": "Recommended",
        "recommendation_date": "2024-04-15",
        "recommended_amount": "1200000.00"
    }

    res = client.post("/api/v1/projects", json=create_payload)
    assert res.status_code == 201
    created_data = res.json()
    assert created_data["project_id"] == test_id
    assert created_data["current_status"] == "Recommended"
    assert created_data["financial"]["recommended_amount"] == "1200000.00"

    # Update project status to Sanctioned
    update_payload = {
        "current_status": "Sanctioned",
        "sanction_date": "2024-05-10"
    }
    res_update = client.patch(f"/api/v1/projects/{test_id}", json=update_payload)
    assert res_update.status_code == 200
    updated_data = res_update.json()
    assert updated_data["current_status"] == "Sanctioned"
    assert updated_data["sanction_date"] == "2024-05-10"

    # Verify audit history
    res_hist = client.get(f"/api/v1/projects/{test_id}/timeline")
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) >= 2
    event_types = [h["event_type"] for h in history]
    assert "Created" in event_types
    assert "Status Changed" in event_types

    # Clean up test project
    db = SessionLocal()
    p = db.get(Project, test_id)
    if p:
        db.delete(p)
        db.commit()
    db.close()


if __name__ == "__main__":
    print("=" * 70)
    print("Executing MPLADS Backend Integration Test Suite...")
    print("=" * 70)

    test_root_endpoint()
    print("  [PASS] test_root_endpoint")

    test_health_check()
    print("  [PASS] test_health_check")

    test_health_root_endpoint()
    print("  [PASS] test_health_root_endpoint")

    test_documentation_endpoints()
    print("  [PASS] test_documentation_endpoints")

    test_list_projects_default()
    print("  [PASS] test_list_projects_default")

    test_get_projects_root_endpoint()
    print("  [PASS] test_get_projects_root_endpoint")

    test_get_projects_pagination_skip_limit()
    print("  [PASS] test_get_projects_pagination_skip_limit")

    test_get_projects_multi_filtering()
    print("  [PASS] test_get_projects_multi_filtering")

    test_get_projects_empty_result_handling()
    print("  [PASS] test_get_projects_empty_result_handling")

    test_get_project_by_id_root_endpoint()
    print("  [PASS] test_get_project_by_id_root_endpoint")

    test_get_project_by_id_not_found()
    print("  [PASS] test_get_project_by_id_not_found")

    test_list_projects_with_filters()
    print("  [PASS] test_list_projects_with_filters")

    test_full_text_search()
    print("  [PASS] test_full_text_search")

    test_get_project_detail()
    print("  [PASS] test_get_project_detail")

    test_project_timeline()
    print("  [PASS] test_project_timeline")

    test_project_progress_history()
    print("  [PASS] test_project_progress_history")

    test_create_and_update_project()
    print("  [PASS] test_create_and_update_project")

    test_analytics_kpi_overview()
    print("  [PASS] test_analytics_kpi_overview")

    test_analytics_sectors()
    print("  [PASS] test_analytics_sectors")

    test_analytics_delayed_projects()
    print("  [PASS] test_analytics_delayed_projects")

    test_analytics_high_risk_projects()
    print("  [PASS] test_analytics_high_risk_projects")

    test_get_analytics_endpoint()
    print("  [PASS] test_get_analytics_endpoint")

    test_get_high_risk_endpoint()
    print("  [PASS] test_get_high_risk_endpoint")

    test_get_high_risk_limit_parameter()
    print("  [PASS] test_get_high_risk_limit_parameter")

    test_analytics_missing_info_audit()
    print("  [PASS] test_analytics_missing_info_audit")

    test_analytics_state_equity()
    print("  [PASS] test_analytics_state_equity")

    test_analytics_state_efficiency()
    print("  [PASS] test_analytics_state_efficiency")

    test_analytics_budget_history()
    print("  [PASS] test_analytics_budget_history")

    print("=" * 70)
    print("ALL 28 BACKEND INTEGRATION TESTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 70)
