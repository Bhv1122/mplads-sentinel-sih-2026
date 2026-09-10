"""
backend/tests/verify_live_server.py
=============================================================================
End-to-end verification script for the live FastAPI development server.
Tests all endpoints, schemas, status codes, and error conditions.
=============================================================================
"""

import sys
import json
import httpx
from decimal import Decimal
from typing import Dict, Any, List

# Ensure backend directory is in sys.path
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.project import (
    ProjectSummary,
    ProjectDetail,
    PaginatedResponse,
    AnalyticsSummaryResponse,
    HighRiskProjectItem,
    ProjectFeatureRead,
    RiskEngineResult
)

BASE_URL = "http://127.0.0.1:8000"


def print_banner(text: str):
    print("\n" + "=" * 75)
    print(f"  {text}")
    print("=" * 75)


def run_all_tests():
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)
    failures = []
    successes = []

    def record_pass(test_name: str, detail: str = ""):
        successes.append(test_name)
        print(f"  [PASS] {test_name}" + (f": {detail}" if detail else ""))

    def record_fail(test_name: str, error: str):
        failures.append((test_name, error))
        print(f"  [FAIL] {test_name}: {error}")

    print_banner("1. Testing GET /health and Database Connectivity")
    try:
        r = client.get("/health")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("status") == "healthy", f"Status not healthy: {data}"
        assert data.get("backend") == "running", f"Backend not running: {data}"
        assert data.get("database") == "connected", f"Database not connected: {data}"
        assert data.get("database_name") == "mplads_db", f"Unexpected DB name: {data}"
        record_pass("GET /health", f"Status={data['status']}, DB={data['database']} ({data['database_name']})")
    except Exception as e:
        record_fail("GET /health", str(e))

    print_banner("2. Testing GET /projects (Pagination & Schema Validation)")
    valid_id = None
    try:
        r = client.get("/projects?limit=10&skip=0")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "items" in data, "Response missing 'items'"
        assert "total" in data, "Response missing 'total'"
        assert data["total"] > 0, f"Expected total > 0, got {data['total']}"
        assert len(data["items"]) > 0, "Items list is empty"
        assert data["limit"] == 10, f"Expected limit 10, got {data['limit']}"

        # Validate with Pydantic model
        validated = PaginatedResponse[ProjectSummary].model_validate(data)
        record_pass(
            "GET /projects",
            f"Total={validated.total}, Items returned={len(validated.items)}, Pydantic validation passed"
        )
        valid_id = validated.items[0].project_id
    except Exception as e:
        record_fail("GET /projects", str(e))

    print_banner(f"3. Testing GET /projects/{{valid_id}} with ID: {valid_id}")
    if valid_id:
        try:
            r = client.get(f"/projects/{valid_id}")
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
            data = r.json()
            assert data["project_id"] == valid_id, f"ID mismatch: {data['project_id']} vs {valid_id}"
            
            # Pydantic schema validation
            detail = ProjectDetail.model_validate(data)
            st_name = detail.state.state_name if detail.state else "N/A"
            record_pass(
                f"GET /projects/{valid_id}",
                f"Title='{detail.project_title}', State='{st_name}', Status='{detail.current_status}'"
            )
            sanc = detail.financial.sanctioned_amount if detail.financial else None
            exp = detail.financial.expenditure_amount if detail.financial else None
            print(f"         - Sanctioned: INR {sanc:,.2f}" if sanc else "         - Sanctioned: N/A")
            print(f"         - Expenditure: INR {exp:,.2f}" if exp else "         - Expenditure: N/A")
            print(f"         - Progress Records: {len(detail.progress_records)}")
            r_score = detail.risk_score.overall_risk_score if detail.risk_score else "N/A"
            r_level = detail.risk_score.risk_level if detail.risk_score else "N/A"
            print(f"         - Risk Score: {r_score} ({r_level})")
        except Exception as e:
            record_fail(f"GET /projects/{valid_id}", str(e))
    else:
        record_fail("GET /projects/{valid_id}", "Skipped because no valid_id found")

    print_banner("4. Testing GET /projects/{invalid_id} (Expected HTTP 404)")
    invalid_ids = ["NONEXISTENT-PROJECT-9999", "INVALID-ID-XYZ", "0000-UNKNOWN"]
    for inv_id in invalid_ids:
        try:
            r = client.get(f"/projects/{inv_id}")
            assert r.status_code == 404, f"Expected 404 for {inv_id}, got {r.status_code}: {r.text}"
            err_data = r.json()
            assert "detail" in err_data, "Error response missing 'detail'"
            record_pass(f"GET /projects/{inv_id}", f"HTTP 404 correctly returned: {err_data['detail']}")
        except Exception as e:
            record_fail(f"GET /projects/{inv_id}", str(e))

    print_banner("5. Testing Malformed Parameters & Validation (Expected HTTP 422)")
    malformed_cases = [
        ("/projects?limit=-1", "Negative limit"),
        ("/projects?limit=not_an_int", "Non-integer limit"),
        ("/projects?limit=500", "Limit exceeding max 100"),
        ("/projects?skip=-5", "Negative skip"),
        ("/projects?sort_order=invalid_dir", "Invalid sort direction regex"),
        ("/projects?min_sanctioned=abc", "Non-decimal min_sanctioned"),
        ("/projects/search", "Missing required 'q' search query"),
        ("/high-risk?limit=-10", "Negative high-risk limit"),
        ("/high-risk?limit=999", "High-risk limit exceeding max 200")
    ]
    for url, desc in malformed_cases:
        try:
            r = client.get(url)
            assert r.status_code == 422, f"Expected 422 for '{desc}' ({url}), got {r.status_code}: {r.text}"
            err = r.json()
            assert "detail" in err, "Validation error response missing 'detail'"
            record_pass(f"Malformed: {desc}", f"HTTP 422 correctly caught invalid parameter")
        except Exception as e:
            record_fail(f"Malformed: {desc}", str(e))

    print_banner("6. Testing GET /analytics (Governance & Portfolio Analytics)")
    try:
        r = client.get("/analytics")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        validated = AnalyticsSummaryResponse.model_validate(data)
        record_pass(
            "GET /analytics",
            f"Total Projects={validated.total_projects}, "
            f"Sanctioned=INR {validated.total_sanctioned_amount:,.2f}, "
            f"Completed={validated.completed_projects}, "
            f"Delayed Count={validated.delayed_projects}"
        )
        print(f"         - Status Breakdown: {validated.status_distribution}")
        print(f"         - Risk Distribution: {validated.risk_distribution}")
        print(f"         - Average Progress: {validated.average_progress}%")
        print(f"         - State Aggregations: {len(validated.state_aggregations)} states")
        print(f"         - Sector Aggregations: {len(validated.sector_aggregations)} sectors")
    except Exception as e:
        record_fail("GET /analytics", str(e))


    print_banner("7. Testing GET /high-risk (Predictive Risk Escalation)")
    try:
        r = client.get("/high-risk?limit=10")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert isinstance(data, list), f"Expected list response, got {type(data)}"
        assert len(data) > 0, "Expected at least one high risk project"

        # Validate with Pydantic model
        validated_items = [HighRiskProjectItem.model_validate(item) for item in data]
        
        # Verify sorting: highest risk first
        scores = [item.overall_risk_score for item in validated_items]
        is_sorted = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        assert is_sorted, f"High risk projects not sorted descending: {scores}"

        record_pass(
            "GET /high-risk",
            f"Returned {len(validated_items)} high-risk projects. Scores sorted descending: "
            f"Top score = {scores[0]}, Lowest = {scores[-1]}"
        )
        top = validated_items[0]
        print(f"         - Top High-Risk Project: [{top.project_id}] '{top.project_title}'")
        print(f"           Score: {top.overall_risk_score} ({top.risk_level})")
        print(f"           Key Risk Factors: {top.risk_factors}")
    except Exception as e:
        record_fail("GET /high-risk", str(e))

    print_banner("8. Testing Swagger & OpenAPI Documentation Endpoints")
    try:
        # 1. /docs (Swagger UI)
        r_docs = client.get("/docs")
        assert r_docs.status_code == 200, f"Expected 200 for /docs, got {r_docs.status_code}"
        assert "swagger-ui" in r_docs.text.lower(), "Swagger UI HTML not found in /docs"
        record_pass("GET /docs", "Swagger UI HTML rendered successfully")

        # 2. /redoc (ReDoc UI)
        r_redoc = client.get("/redoc")
        assert r_redoc.status_code == 200, f"Expected 200 for /redoc, got {r_redoc.status_code}"
        assert "redoc" in r_redoc.text.lower(), "ReDoc HTML not found in /redoc"
        record_pass("GET /redoc", "ReDoc UI HTML rendered successfully")

        # 3. /openapi.json (OpenAPI 3.1 schema)
        r_openapi = client.get("/openapi.json")
        assert r_openapi.status_code == 200, f"Expected 200 for /openapi.json, got {r_openapi.status_code}"
        schema = r_openapi.json()
        assert "paths" in schema, "OpenAPI schema missing 'paths'"
        paths = schema["paths"]
        
        required_paths = [
            "/health",
            "/projects",
            "/projects/{id}",
            "/analytics",
            "/high-risk"
        ]
        for p in required_paths:
            assert p in paths, f"OpenAPI schema missing required endpoint path '{p}'"

        record_pass(
            "GET /openapi.json",
            f"Verified all required endpoints are documented in OpenAPI schema ({len(paths)} total routes mapped)"
        )
    except Exception as e:
        record_fail("Swagger / OpenAPI", str(e))

    print_banner("TEST SUMMARY")
    print(f"  Total Passed: {len(successes)}")
    print(f"  Total Failed: {len(failures)}")
    if failures:
        print("\n  FAILURES DETAIL:")
        for name, err in failures:
            print(f"    - {name}: {err}")
        return False
    else:
        print("\n  >>> ALL TESTS PASSED SUCCESSFULLY WITH ZERO ERRORS! <<<")
        return True


# =============================================================================
# Pytest Test Functions (Allows running via pytest tests/verify_live_server.py)
# =============================================================================

import pytest

@pytest.fixture(scope="module")
def http_client():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        yield client


def test_live_health_endpoint(http_client):
    r = http_client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["backend"] == "running"
    assert data["database"] == "connected"
    assert data["database_name"] == "mplads_db"


def test_live_projects_list(http_client):
    r = http_client.get("/projects?limit=10&skip=0")
    assert r.status_code == 200
    data = r.json()
    validated = PaginatedResponse[ProjectSummary].model_validate(data)
    assert validated.total > 0
    assert len(validated.items) > 0


def test_live_project_valid_id(http_client):
    r = http_client.get("/projects?limit=1")
    items = r.json()["items"]
    assert len(items) > 0
    valid_id = items[0]["project_id"]

    r_det = http_client.get(f"/projects/{valid_id}")
    assert r_det.status_code == 200
    detail = ProjectDetail.model_validate(r_det.json())
    assert detail.project_id == valid_id
    assert detail.features is not None, "Project features should be populated in detail"
    assert detail.features.delay_days is not None


def test_live_project_features(http_client):
    r = http_client.get("/projects?limit=1")
    valid_id = r.json()["items"][0]["project_id"]

    r_feat = http_client.get(f"/projects/{valid_id}/features")
    assert r_feat.status_code == 200
    feat = ProjectFeatureRead.model_validate(r_feat.json())
    assert feat.project_id == valid_id
    assert feat.utilization_ratio >= 0
    assert feat.cost_per_category > 0
    assert feat.project_duration >= 0


def test_live_project_features_not_found(http_client):
    r = http_client.get("/projects/NONEXISTENT-PROJECT-9999/features")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()



@pytest.mark.parametrize("invalid_id", [
    "NONEXISTENT-PROJECT-9999",
    "INVALID-ID-XYZ",
    "0000-UNKNOWN"
])
def test_live_project_invalid_id(http_client, invalid_id):
    r = http_client.get(f"/projects/{invalid_id}")
    assert r.status_code == 404
    assert "detail" in r.json()


@pytest.mark.parametrize("url", [
    "/projects?limit=-1",
    "/projects?limit=not_an_int",
    "/projects?limit=500",
    "/projects?skip=-5",
    "/projects?sort_order=invalid_dir",
    "/projects?min_sanctioned=abc",
    "/projects/search",
    "/high-risk?limit=-10",
    "/high-risk?limit=999"
])
def test_live_malformed_parameters(http_client, url):
    r = http_client.get(url)
    assert r.status_code == 422


def test_live_analytics_endpoint(http_client):
    r = http_client.get("/analytics")
    assert r.status_code == 200
    validated = AnalyticsSummaryResponse.model_validate(r.json())
    assert validated.total_projects > 0
    assert validated.average_progress >= 0


def test_live_high_risk_endpoint(http_client):
    r = http_client.get("/high-risk?limit=10")
    assert r.status_code == 200
    data = r.json()
    validated_items = [HighRiskProjectItem.model_validate(item) for item in data]
    assert len(validated_items) > 0
    scores = [item.overall_risk_score for item in validated_items]
    assert all(scores[i] >= scores[i+1] for i in range(len(scores)-1))


def test_live_project_risk_endpoint(http_client):
    r = http_client.get("/projects/MPLADS-2024-0001/risk")
    assert r.status_code == 200
    res = RiskEngineResult.model_validate(r.json())
    assert res.project_id == "MPLADS-2024-0001"
    assert 0.0 <= res.overall_risk_score <= 100.0
    assert res.risk_level in {"Low", "Moderate", "High", "Critical"}
    assert len(res.detector_breakdown) == 5


def test_live_project_risk_recalculate_endpoint(http_client):
    r = http_client.post("/projects/MPLADS-2024-0001/risk/recalculate")
    assert r.status_code == 200
    res = RiskEngineResult.model_validate(r.json())
    assert res.project_id == "MPLADS-2024-0001"
    assert len(res.detector_breakdown) == 5


def test_live_project_risk_batch_endpoint(http_client):
    payload = {"project_ids": ["MPLADS-2024-0001", "MPLADS-2024-0002"], "limit": 10}
    r = http_client.post("/projects/risk/batch", json=payload)
    assert r.status_code == 200
    items = [RiskEngineResult.model_validate(item) for item in r.json()]
    assert len(items) == 2
    assert {item.project_id for item in items} == {"MPLADS-2024-0001", "MPLADS-2024-0002"}


def test_live_documentation_endpoints(http_client):
    r_docs = http_client.get("/docs")
    assert r_docs.status_code == 200
    assert "swagger-ui" in r_docs.text.lower()

    r_redoc = http_client.get("/redoc")
    assert r_redoc.status_code == 200
    assert "redoc" in r_redoc.text.lower()

    r_openapi = http_client.get("/openapi.json")
    assert r_openapi.status_code == 200
    paths = r_openapi.json()["paths"]
    for p in ["/health", "/projects", "/projects/{id}", "/analytics", "/high-risk"]:
        assert p in paths


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

