"""
backend/tests/test_fastapi_risk_integration.py
=============================================================================
Comprehensive Integration Tests for FastAPI Risk Endpoints.
=============================================================================

Validates:
1. GET /projects/{id}/risk (cached and on-demand evaluation)
2. GET /projects/{id}/risk/factors (all six modular engines)
3. POST /projects/{id}/risk/recalculate (fresh recalculation)
4. GET /high-risk (portfolio high-risk surveillance and min_score filtering)
5. GET /analytics/risk-distribution (portfolio distribution and engine averages)
6. GET /analytics/engine/{engine_name} (engine analytics and 400 for invalid engine)
7. GET /agencies/{agency_id}/risk-pattern (agency risk pattern and 404 for missing)
8. Error handling guarantees (clean JSON, zero stack trace leakage)
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.database import SessionLocal
from app.models.project import Project, RiskScore, RiskFactor


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Direct database session fixture."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# =============================================================================
# 1. Project Risk Endpoints: GET /projects/{id}/risk
# =============================================================================

class TestProjectRiskEndpoint:
    """Tests for GET /projects/{id}/risk."""

    def test_get_project_risk_success(self, client):
        """GET /projects/{id}/risk returns full risk assessment with all required fields."""
        response = client.get("/projects/MPLADS-2024-0001/risk")
        assert response.status_code == 200
        data = response.json()

        # Core identification and scores
        assert data["project_id"] == "MPLADS-2024-0001"
        assert "overall_score" in data
        assert 0.0 <= data["overall_score"] <= 100.0
        assert "overall_risk_score" in data
        assert data["risk_level"] in ["Low", "Moderate", "High", "Critical", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert 0.0 <= data["confidence"] <= 1.0

        # Extended engine scores and metadata
        assert "engine_scores" in data
        assert isinstance(data["engine_scores"], dict)
        for expected_engine in ["cost_anomaly", "duplicate_detection", "delay_detection", "progress_mismatch", "agency_pattern"]:
            assert expected_engine in data["engine_scores"]

        # Reasons and evidence
        assert "reasons" in data
        assert isinstance(data["reasons"], dict)
        assert "evidence" in data
        assert isinstance(data["evidence"], dict)

        # Engine 6 synthesis
        assert "summary" in data
        assert "recommended_review" in data
        assert isinstance(data["recommended_review"], list)

        # Weights used
        assert "weights_used" in data
        assert isinstance(data["weights_used"], dict)

        # Backward compatibility
        assert "detector_breakdown" in data
        assert len(data["detector_breakdown"]) == 5

    def test_get_project_risk_recalculate_query_param(self, client):
        """GET /projects/{id}/risk?recalculate=true triggers on-demand recalculation."""
        response = client.get("/projects/MPLADS-2024-0001/risk?recalculate=true")
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "MPLADS-2024-0001"
        assert len(data["detector_breakdown"]) == 5

    def test_get_project_risk_not_found(self, client):
        """GET /projects/{id}/risk returns 404 for nonexistent project."""
        response = client.get("/projects/MPLADS-DOES-NOT-EXIST/risk")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        # No internal stack trace or sql
        assert "Traceback" not in response.text
        assert "SELECT" not in response.text

    def test_get_project_risk_invalid_id(self, client):
        """GET /projects/{id}/risk returns 400 for empty or whitespace project ID."""
        response = client.get("/projects/%20%20/risk")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Traceback" not in response.text


# =============================================================================
# 2. Project Risk Factors Endpoint: GET /projects/{id}/risk/factors
# =============================================================================

class TestProjectRiskFactorsEndpoint:
    """Tests for GET /projects/{id}/risk/factors."""

    def test_get_project_risk_factors_all_six_engines(self, client):
        """GET /projects/{id}/risk/factors returns all 6 modular engines."""
        response = client.get("/projects/MPLADS-2024-0001/risk/factors")
        assert response.status_code == 200
        data = response.json()

        assert data["project_id"] == "MPLADS-2024-0001"
        assert "overall_score" in data
        assert "risk_level" in data
        assert "confidence" in data
        assert "factors" in data

        factors = data["factors"]
        assert len(factors) == 6

        expected_engines = {
            "cost_anomaly",
            "duplicate_detection",
            "delay_detection",
            "progress_mismatch",
            "agency_pattern",
            "explained_risk",
        }
        returned_engines = {f["engine_name"] for f in factors}
        assert returned_engines == expected_engines

        for f in factors:
            assert f["engine_name"] in expected_engines
            assert 0.0 <= f["score"] <= 100.0
            assert f["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            assert len(f["reason"]) > 0
            assert 0.0 <= f["confidence"] <= 1.0
            assert "weight" in f
            assert "contribution" in f
            assert isinstance(f["details"], dict)

    def test_get_project_risk_factors_not_found(self, client):
        """GET /projects/{id}/risk/factors returns 404 for nonexistent project."""
        response = client.get("/projects/UNKNOWN-PID-9999/risk/factors")
        assert response.status_code == 404
        assert "Traceback" not in response.text

    def test_get_project_risk_factors_invalid_id(self, client):
        """GET /projects/{id}/risk/factors returns 400 for whitespace project ID."""
        response = client.get("/projects/%20%20/risk/factors")
        assert response.status_code == 400
        assert "Traceback" not in response.text


# =============================================================================
# 3. Project Recalculate Endpoint: POST /projects/{id}/risk/recalculate
# =============================================================================

class TestProjectRecalculateEndpoint:
    """Tests for POST /projects/{id}/risk/recalculate."""

    def test_recalculate_project_risk_success(self, client):
        """POST /projects/{id}/risk/recalculate forces evaluation and persists."""
        response = client.post("/projects/MPLADS-2024-0002/risk/recalculate")
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "MPLADS-2024-0002"
        assert "overall_score" in data
        assert len(data["detector_breakdown"]) == 5

    def test_recalculate_project_risk_not_found(self, client):
        """POST /projects/{id}/risk/recalculate returns 404 for nonexistent project."""
        response = client.post("/projects/DOES-NOT-EXIST/risk/recalculate")
        assert response.status_code == 404
        assert "Traceback" not in response.text

    def test_recalculate_project_risk_invalid_id(self, client):
        """POST /projects/{id}/risk/recalculate returns 400 for invalid project ID."""
        response = client.post("/projects/%20%20/risk/recalculate")
        assert response.status_code == 400
        assert "Traceback" not in response.text


# =============================================================================
# 4. High-Risk Surveillance Endpoint: GET /high-risk
# =============================================================================

class TestHighRiskEndpoint:
    """Tests for GET /high-risk."""

    def test_get_high_risk_projects(self, client):
        """GET /high-risk returns list of high-risk projects."""
        response = client.get("/high-risk")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            first = data[0]
            assert "project_id" in first
            assert "project_title" in first
            assert "overall_risk_score" in first
            assert "risk_level" in first

    def test_get_high_risk_projects_with_min_score(self, client):
        """GET /high-risk?min_score=50 filters projects by score."""
        response = client.get("/high-risk?min_score=50")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for item in data:
            assert float(item["overall_risk_score"]) >= 50.0


# =============================================================================
# 5. Risk Distribution Endpoint: GET /analytics/risk-distribution
# =============================================================================

class TestRiskDistributionEndpoint:
    """Tests for GET /analytics/risk-distribution."""

    def test_get_risk_distribution(self, client):
        """GET /analytics/risk-distribution returns portfolio distribution and engine averages."""
        response = client.get("/analytics/risk-distribution")
        assert response.status_code == 200
        data = response.json()

        assert "total_projects" in data
        assert data["total_projects"] >= 20

        assert "distribution" in data
        for tier in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            assert tier in data["distribution"]
            assert data["distribution"][tier] >= 0

        assert "percentages" in data
        for tier in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            assert tier in data["percentages"]
            assert 0.0 <= data["percentages"][tier] <= 100.0

        assert "average_overall_score" in data
        assert 0.0 <= data["average_overall_score"] <= 100.0

        assert "engine_averages" in data
        assert isinstance(data["engine_averages"], dict)
        assert len(data["engine_averages"]) >= 5


# =============================================================================
# 6. Engine Analytics Endpoint: GET /analytics/engine/{engine_name}
# =============================================================================

class TestEngineAnalyticsEndpoint:
    """Tests for GET /analytics/engine/{engine_name}."""

    @pytest.mark.parametrize("engine_name", [
        "cost_anomaly",
        "duplicate_detection",
        "delay_detection",
        "progress_mismatch",
        "agency_pattern",
        "explained_risk",
    ])
    def test_get_engine_analytics_valid_engines(self, client, engine_name):
        """GET /analytics/engine/{engine_name} returns statistics and top flagged projects."""
        response = client.get(f"/analytics/engine/{engine_name}")
        assert response.status_code == 200
        data = response.json()

        assert data["engine_name"] == engine_name
        assert "display_name" in data
        assert "description" in data
        assert data["total_projects"] >= 0
        assert 0.0 <= data["average_score"] <= 100.0
        assert 0.0 <= data["min_score"] <= 100.0
        assert 0.0 <= data["max_score"] <= 100.0
        assert 0.0 <= data["average_confidence"] <= 1.0

        assert "risk_tier_distribution" in data
        assert "top_flagged_projects" in data
        assert isinstance(data["top_flagged_projects"], list)

    def test_get_engine_analytics_invalid_engine(self, client):
        """GET /analytics/engine/{engine_name} returns 400 for invalid engine."""
        response = client.get("/analytics/engine/invalid_engine_name")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Allowed engines" in data["detail"]
        assert "Traceback" not in response.text


# =============================================================================
# 7. Agency Risk Pattern Endpoint: GET /agencies/{agency_id}/risk-pattern
# =============================================================================

class TestAgencyRiskPatternEndpoint:
    """Tests for GET /agencies/{agency_id}/risk-pattern."""

    def test_get_agency_risk_pattern_by_acronym(self, client):
        """GET /agencies/{agency_id}/risk-pattern finds agency by acronym 'drda'."""
        response = client.get("/agencies/drda/risk-pattern")
        assert response.status_code == 200
        data = response.json()

        assert data["agency_id"] == "drda"
        assert "District Rural Development Agency" in data["agency_name"]
        assert data["projects_analyzed"] >= 1
        assert 0.0 <= data["agency_risk_score"] <= 100.0
        assert data["agency_risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert 0.0 <= data["confidence"] <= 1.0
        assert len(data["reason"]) > 0

        # Detailed metrics
        details = data["details"]
        assert "delay_rate" in details
        assert "cost_anomaly_rate" in details
        assert "mismatch_rate" in details
        assert "completion_rate" in details

        # Associated projects
        assert "projects" in data
        assert len(data["projects"]) == data["projects_analyzed"]
        assert "project_id" in data["projects"][0]

    def test_get_agency_risk_pattern_by_full_name(self, client):
        """GET /agencies/{agency_id}/risk-pattern finds agency by full name."""
        response = client.get("/agencies/District%20Rural%20Development%20Agency%20(DRDA)/risk-pattern")
        assert response.status_code == 200
        data = response.json()
        assert data["projects_analyzed"] >= 1

    def test_get_agency_risk_pattern_not_found(self, client):
        """GET /agencies/{agency_id}/risk-pattern returns 404 for unknown agency."""
        response = client.get("/agencies/nonexistent-agency-xyz-123/risk-pattern")
        assert response.status_code == 404
        assert "Traceback" not in response.text

    def test_get_agency_risk_pattern_invalid_id(self, client):
        """GET /agencies/{agency_id}/risk-pattern returns 400 for whitespace identifier."""
        response = client.get("/agencies/%20%20/risk-pattern")
        assert response.status_code == 400
        assert "Traceback" not in response.text


# =============================================================================
# 8. API Prefix Validation (/api/v1 prefix)
# =============================================================================

class TestAPIVersionPrefix:
    """Verifies that all endpoints are also accessible under /api/v1 prefix."""

    def test_api_v1_endpoints(self, client):
        r1 = client.get("/api/v1/projects/MPLADS-2024-0001/risk")
        assert r1.status_code == 200

        r2 = client.get("/api/v1/projects/MPLADS-2024-0001/risk/factors")
        assert r2.status_code == 200

        r3 = client.get("/api/v1/high-risk")
        assert r3.status_code == 200

        r4 = client.get("/api/v1/analytics/risk-distribution")
        assert r4.status_code == 200

        r5 = client.get("/api/v1/analytics/engine/delay_detection")
        assert r5.status_code == 200

        r6 = client.get("/api/v1/agencies/drda/risk-pattern")
        assert r6.status_code == 200
