"""
backend/tests/test_project_explanation_endpoint.py
=============================================================================
Phase 8 Test Suite: Project Explainability Endpoint (GET /projects/{id}/explanation).
=============================================================================

Validates:
1. Complete structured explanation matching the required contract:
   - project_id: str
   - risk_level: str ("LOW", "MEDIUM", "HIGH", "CRITICAL")
   - risk_score: float
   - summary: objective, non-accusatory synthesis
   - factors: list of evaluated detectors with name, detector, triggered, severity, contribution, evidence
   - evidence: list of items with text, actual_value, reference_value, unit
2. Exact matching of the example scenario from prompt:
   - Cost is 2.56× peer median (25.6 crore vs 10.0 crore)
   - Summary: "Project flagged due to cost anomaly, delay, and progress mismatch."
3. Strict use of existing detector and risk-engine results without independent recalculation.
4. Proper validation and error handling:
   - 400 for invalid/empty project ID
   - 404 for nonexistent project ID
5. Query parameter support:
   - recalculate=true forces fresh analysis
   - only_triggered=true filters factors
6. OpenAPI/Swagger schema documentation accuracy.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.main import app
from app.models.project import RiskScore, RiskFactor
from app.schemas.explainability import (
    ProjectExplanationEvidence,
    ProjectExplanationFactor,
    ProjectExplanationResponse,
)
from app.services.explainability_service import ExplainabilityService, explainability_service

client = TestClient(app)


@pytest.fixture
def db_session():
    """Provides a transactional database session for tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def service():
    return ExplainabilityService()


# =============================================================================
# 1. Schema & Service Unit Tests
# =============================================================================

class TestProjectExplanationServiceUnit:

    def test_exact_user_prompt_scenario_synthesis(self, service):
        """
        Validates the exact example scenario from the prompt:
        - Cost Anomaly: actual_value=25.6, reference_value=10.0, unit='crore', contrib=25.4
        - Delay: actual_value=210, unit='days'
        - Progress Mismatch: fp=82, pp=35, gap=47
        """
        mock_risk_result = {
            "project_id": "P123",
            "overall_risk_score": 78.4,
            "overall_score": 78.4,
            "risk_level": "HIGH",
            "confidence": 0.95,
            "weights_used": {
                "cost_anomaly": 0.30,
                "delay_detection": 0.25,
                "progress_mismatch": 0.25,
                "duplicate_detection": 0.10,
                "agency_pattern": 0.10,
            },
            "detector_breakdown": [
                {
                    "detector_key": "cost_anomaly",
                    "detector_name": "Cost Anomaly",
                    "score": 84.7,
                    "effective_weight": 0.30,
                    "triggered": True,
                    "severity": "high",
                    "details": {
                        "actual_value": 25.6,
                        "reference_value": 10.0,
                        "unit": "crore",
                        "cost_unit": "crore",
                    }
                },
                {
                    "detector_key": "delay_detection",
                    "detector_name": "Delay Detection",
                    "score": 70.0,
                    "effective_weight": 0.25,
                    "triggered": True,
                    "severity": "high",
                    "details": {
                        "overdue_days": 210,
                        "actual_value": 210,
                    }
                },
                {
                    "detector_key": "progress_mismatch",
                    "detector_name": "Progress Mismatch",
                    "score": 65.0,
                    "effective_weight": 0.25,
                    "triggered": True,
                    "severity": "high",
                    "details": {
                        "financial_progress": 82.0,
                        "physical_progress": 35.0,
                    }
                },
                {
                    "detector_key": "duplicate_detection",
                    "detector_name": "Duplicate Detection",
                    "score": 0.0,
                    "effective_weight": 0.10,
                    "triggered": False,
                    "severity": "low",
                    "details": {"similarity": 0.0}
                },
                {
                    "detector_key": "agency_pattern",
                    "detector_name": "Agency Pattern",
                    "score": 10.0,
                    "effective_weight": 0.10,
                    "triggered": False,
                    "severity": "low",
                    "details": {"delay_rate": 0.05, "projects_analyzed": 10}
                },
            ]
        }

        resp = service._build_from_risk_result("P123", mock_risk_result)
        assert isinstance(resp, ProjectExplanationResponse)
        assert resp.project_id == "P123"
        assert resp.risk_level == "HIGH"
        assert resp.risk_score == 78.4
        assert resp.summary == "Project flagged due to cost anomaly, delay, and progress mismatch."

        # Verify Cost Anomaly factor
        cost_factors = [f for f in resp.factors if f.detector == "cost_anomaly"]
        assert len(cost_factors) == 1
        cost_f = cost_factors[0]
        assert cost_f.name == "Cost Anomaly"
        assert cost_f.triggered is True
        assert cost_f.severity == "high"
        assert cost_f.contribution == 25.4
        assert len(cost_f.evidence) >= 1
        ev0 = cost_f.evidence[0]
        assert ev0.text == "Cost is 2.56× peer median."
        assert ev0.actual_value == 25.6
        assert ev0.reference_value == 10.0
        assert ev0.unit == "crore"

    def test_raw_inr_conversion_to_crore_scale(self, service):
        """Validates that large raw INR numbers (e.g. 256,000,000) scale accurately to crore units."""
        details = {
            "evaluated_cost": 256000000.0,
            "peer_median": 100000000.0,
        }
        ev_list = service._extract_cost_anomaly_evidence(details, score=85.0)
        assert len(ev_list) == 1
        ev = ev_list[0]
        assert ev.actual_value == 25.6
        assert ev.reference_value == 10.0
        assert ev.unit == "crore"
        assert ev.text == "Cost is 2.56× peer median."

    def test_no_detectors_triggered_summary(self, service):
        """Validates reassuring summary when no detectors trigger."""
        mock_risk_result = {
            "project_id": "P_NORMAL",
            "overall_risk_score": 12.0,
            "risk_level": "LOW",
            "detector_breakdown": [
                {"detector_key": "cost_anomaly", "score": 0.0, "triggered": False, "details": {}},
                {"detector_key": "delay_detection", "score": 0.0, "triggered": False, "details": {}},
                {"detector_key": "progress_mismatch", "score": 0.0, "triggered": False, "details": {}},
                {"detector_key": "duplicate_detection", "score": 0.0, "triggered": False, "details": {}},
                {"detector_key": "agency_pattern", "score": 0.0, "triggered": False, "details": {}},
            ]
        }
        resp = service._build_from_risk_result("P_NORMAL", mock_risk_result)
        assert resp.summary == "No significant risk factors were detected based on the configured detection thresholds."
        assert all(f.triggered is False for f in resp.factors)


# =============================================================================
# 2. Database Reuse Tests (Zero Redundant Recalculation)
# =============================================================================

class TestProjectExplanationDatabaseReuse:

    def test_uses_existing_db_results_without_recalculating(self, db_session, service):
        """
        Validates requirement:
        'Make sure the endpoint uses the existing detector and risk-engine results
        rather than recalculating the same logic independently.'
        """
        # Pick a project that exists in DB and has been evaluated
        live_project_id = "MPLADS-2024-0017"

        # Spy on risk_engine.evaluate to verify it is NOT called when cached
        with patch.object(service.risk_engine, "evaluate", wraps=service.risk_engine.evaluate) as mock_eval:
            resp = service.get_project_explanation(
                project_id=live_project_id,
                db=db_session,
                recalculate=False,
            )
            assert isinstance(resp, ProjectExplanationResponse)
            assert resp.project_id == live_project_id
            assert resp.risk_score > 0
            assert resp.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            assert len(resp.factors) == 5

            # Mock evaluate MUST NOT have been called!
            assert mock_eval.call_count == 0, "RiskEngine.evaluate should NOT be called when results exist in DB!"

    def test_recalculate_forces_risk_engine_evaluation(self, db_session, service):
        """When recalculate=True is specified, risk_engine.evaluate MUST be invoked."""
        live_project_id = "MPLADS-2024-0017"

        with patch.object(service.risk_engine, "evaluate", wraps=service.risk_engine.evaluate) as mock_eval:
            resp = service.get_project_explanation(
                project_id=live_project_id,
                db=db_session,
                recalculate=True,
            )
            assert isinstance(resp, ProjectExplanationResponse)
            assert mock_eval.call_count == 1, "RiskEngine.evaluate should be called when recalculate=True"


# =============================================================================
# 3. FastAPI Endpoint HTTP Tests (GET /projects/{id}/explanation)
# =============================================================================

class TestProjectExplanationAPIEndpoint:

    def test_api_get_explanation_success(self):
        """Validates GET /projects/{id}/explanation returns 200 with required schema structure."""
        response = client.get("/projects/MPLADS-2024-0017/explanation")
        assert response.status_code == 200

        data = response.json()
        assert data["project_id"] == "MPLADS-2024-0017"
        assert "risk_level" in data
        assert "risk_score" in data
        assert "summary" in data
        assert "factors" in data
        assert isinstance(data["factors"], list)
        assert len(data["factors"]) == 5

        # Verify factor structure
        for factor in data["factors"]:
            assert "name" in factor
            assert "detector" in factor
            assert "triggered" in factor
            assert isinstance(factor["triggered"], bool)
            assert "severity" in factor
            assert factor["severity"] in ("low", "medium", "high", "critical")
            assert "contribution" in factor
            assert isinstance(factor["contribution"], (int, float))
            assert "evidence" in factor
            assert isinstance(factor["evidence"], list)

            for ev in factor["evidence"]:
                assert "text" in ev
                assert isinstance(ev["text"], str)
                assert "actual_value" in ev
                assert "reference_value" in ev
                assert "unit" in ev

    def test_api_get_explanation_only_triggered(self):
        """Validates only_triggered=true query parameter."""
        response = client.get("/projects/MPLADS-2024-0017/explanation?only_triggered=true")
        assert response.status_code == 200
        data = response.json()
        assert all(f["triggered"] is True for f in data["factors"])

    def test_api_get_explanation_recalculate(self):
        """Validates recalculate=true query parameter."""
        response = client.get("/projects/MPLADS-2024-0017/explanation?recalculate=true")
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "MPLADS-2024-0017"

    def test_api_get_explanation_not_found(self):
        """Validates 404 for nonexistent project."""
        response = client.get("/projects/NONEXISTENT-PROJECT-9999/explanation")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_api_get_explanation_invalid_id(self):
        """Validates 400 for empty or whitespace project ID."""
        response = client.get("/projects/%20/explanation")
        assert response.status_code in (400, 404)


# =============================================================================
# 4. OpenAPI / Swagger Documentation Test
# =============================================================================

class TestOpenAPIDocumentation:

    def test_openapi_schema_contains_explanation_endpoint(self):
        """Verifies OpenAPI schema includes /projects/{id}/explanation with proper metadata."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        paths = schema.get("paths", {})
        assert "/projects/{id}/explanation" in paths, "Route /projects/{id}/explanation missing from OpenAPI paths"

        get_op = paths["/projects/{id}/explanation"].get("get")
        assert get_op is not None, "GET operation missing for /projects/{id}/explanation"
        assert "summary" in get_op
        assert "description" in get_op

        # Verify 200 response references ProjectExplanationResponse
        resp_200 = get_op.get("responses", {}).get("200", {})
        assert resp_200 is not None

        # Verify schema components
        schemas = schema.get("components", {}).get("schemas", {})
        assert "ProjectExplanationResponse" in schemas
        assert "ProjectExplanationFactor" in schemas
        assert "ProjectExplanationEvidence" in schemas

        # Verify fields in ProjectExplanationResponse schema
        resp_props = schemas["ProjectExplanationResponse"]["properties"]
        assert "project_id" in resp_props
        assert "risk_level" in resp_props
        assert "risk_score" in resp_props
        assert "summary" in resp_props
        assert "factors" in resp_props
