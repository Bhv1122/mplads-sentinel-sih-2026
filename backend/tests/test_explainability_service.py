"""
backend/tests/test_explainability_service.py
=============================================================================
Phase 8: Explainability Layer Test Suite.
=============================================================================

Tests:
1. Pydantic schema validation (StructuredExplanation, ExplanationFactor, EvidenceItem, etc.)
2. Factor extraction for all 5 detectors:
   - Cost Anomaly Factor
   - Duplicate Detection Factor
   - Delay Detection Factor
   - Progress Mismatch Factor
   - Agency Pattern Factor
3. Triggered detector identification & count accuracy
4. Ranked factor contribution ordering
5. Mathematical consistency of detector contributions
6. Actionable, non-accusatory recommendation synthesis
7. UI display helpers (cards, chips, color badges)
8. Live project evaluation on real database records
9. FastAPI API endpoint integration:
   - GET /projects/{id}/explain (200 OK)
   - Recalculate query parameter
   - Error handling (400, 404, zero stack trace leak)
"""

import os
import sys
import pytest
from decimal import Decimal
from typing import Dict, Any
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.main import app
from app.schemas.explainability import (
    SeverityLevel,
    ActionPriority,
    ActionCategory,
    EvidenceItem,
    DetectorContribution,
    ExplanationFactor,
    RecommendationAction,
    UIDisplayCard,
    StructuredExplanation,
)
from app.services.explainability_service import ExplainabilityService, explainability_service
from app.services.risk_engine import RiskEngine


client = TestClient(app)


@pytest.fixture
def db_session():
    """Provides a database session for testing."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def service():
    """Provides an instance of ExplainabilityService."""
    return ExplainabilityService()


# =============================================================================
# 1. Schema & Model Validation Tests
# =============================================================================

class TestExplainabilitySchemas:

    def test_evidence_item_schema(self):
        """Validates EvidenceItem fields, types, and serialization."""
        item = EvidenceItem(
            metric_key="overdue_days",
            label="Days Overdue",
            actual_value=527,
            formatted_value="527 days",
            reference_value=0,
            formatted_reference="0 days (On schedule)",
            unit="days",
            context="Calendar days elapsed beyond planned completion.",
        )
        data = item.model_dump()
        assert data["metric_key"] == "overdue_days"
        assert data["actual_value"] == 527
        assert data["formatted_value"] == "527 days"
        assert data["reference_value"] == 0

    def test_explanation_factor_mandatory_fields(self):
        """Verifies that ExplanationFactor contains all required fields."""
        factor = ExplanationFactor(
            factor_name="Schedule Delay Overrun",
            detector_name="delay_detection",
            severity=SeverityLevel.CRITICAL,
            triggered_status=True,
            contribution_to_risk_score=20.0,
            threshold_used="Elapsed schedule exceeding planned completion date",
            actual_value="527 days overdue (+217.8% delay)",
            expected_reference_value="Planned duration: 242 days",
            evidence=[
                EvidenceItem(
                    metric_key="overdue_days",
                    label="Days Overdue",
                    actual_value=527,
                    formatted_value="527 days",
                )
            ],
            explanation_text="Project is severely overdue.",
        )
        d = factor.model_dump()
        expected_keys = {
            "factor_name",
            "detector_name",
            "severity",
            "triggered_status",
            "contribution_to_risk_score",
            "threshold_used",
            "actual_value",
            "expected_reference_value",
            "evidence",
            "raw_evidence_dict",
            "explanation_text",
        }
        assert expected_keys.issubset(set(d.keys()))
        assert d["severity"] == "CRITICAL"
        assert d["triggered_status"] is True
        assert d["contribution_to_risk_score"] == 20.0

    def test_detector_contribution_schema(self):
        """Verifies DetectorContribution mathematical schema."""
        contrib = DetectorContribution(
            detector_name="cost_anomaly",
            display_name="Cost Anomaly Detection",
            score=44.0,
            weight=0.20,
            contribution_points=8.8,
            percentage_of_total=16.9,
        )
        assert contrib.contribution_points == 8.8
        assert contrib.percentage_of_total == 16.9


# =============================================================================
# 2. Factor Builders & Evidence Extraction Tests
# =============================================================================

class TestFactorBuilders:

    def test_cost_anomaly_factor_extraction(self, service):
        """Tests extraction of actual, reference, and evidence items for cost anomaly."""
        cost_details = {
            "evaluated_cost": 2100000.0,
            "peer_median": 1290000.0,
            "deviation_percentage": 62.79,
            "robust_z_score": 6.07,
            "cost_overrun_pct": 0.0,
            "sanctioned_amount": 4800000.0,
            "peer_scope": "sector_nationwide",
            "anomaly_type": "LEGITIMATE_HIGH_BUDGET",
        }
        factor = service._build_cost_anomaly_factor(
            details=cost_details,
            score=44.0,
            contribution=8.8,
            severity=SeverityLevel.MEDIUM,
            triggered=True,
            meta=service.DETECTOR_METADATA["cost_anomaly"],
            reason="Project expenditure is 1.6x peer median but within sanction.",
        )
        assert factor.detector_name == "cost_anomaly"
        assert factor.severity == SeverityLevel.MEDIUM
        assert factor.triggered_status is True
        assert "₹2,100,000.00" in factor.actual_value
        assert "₹1,290,000.00" in factor.expected_reference_value
        assert len(factor.evidence) >= 3

        # Verify evidence item keys
        metric_keys = {e.metric_key for e in factor.evidence}
        assert "evaluated_cost" in metric_keys
        assert "deviation_percentage" in metric_keys
        assert "robust_z_score" in metric_keys

    def test_delay_factor_extraction(self, service):
        """Tests extraction of delay duration, slippage %, and target dates."""
        delay_details = {
            "overdue_days": 527,
            "delay_percentage": 217.8,
            "planned_duration": 242,
            "expected_completion_date": "2025-03-31",
            "completion_status": "ONGOING_OVERDUE",
        }
        factor = service._build_delay_factor(
            details=delay_details,
            score=100.0,
            contribution=20.0,
            severity=SeverityLevel.CRITICAL,
            triggered=True,
            meta=service.DETECTOR_METADATA["delay_detection"],
            reason="Project is 527 days overdue.",
        )
        assert factor.detector_name == "delay_detection"
        assert factor.severity == SeverityLevel.CRITICAL
        assert "527 days overdue" in factor.actual_value
        assert "242 days" in factor.expected_reference_value
        assert "2025-03-31" in factor.expected_reference_value

        evidence_map = {e.metric_key: e for e in factor.evidence}
        assert evidence_map["overdue_days"].actual_value == 527
        assert evidence_map["delay_percentage"].actual_value == 217.8

    def test_progress_mismatch_factor_extraction(self, service):
        """Tests extraction of financial vs physical progress gap."""
        mismatch_details = {
            "financial_progress": 87.5,
            "physical_progress": 65.0,
            "progress_gap": 22.5,
            "direction": "financial_leading",
            "current_stage": "Structure",
        }
        factor = service._build_mismatch_factor(
            details=mismatch_details,
            score=63.0,
            contribution=12.6,
            severity=SeverityLevel.HIGH,
            triggered=True,
            meta=service.DETECTOR_METADATA["progress_mismatch"],
            reason="Recorded financial progress leads verified physical progress by 22.5%.",
        )
        assert factor.detector_name == "progress_mismatch"
        assert factor.severity == SeverityLevel.HIGH
        assert factor.triggered_status is True
        assert "87.5%" in factor.actual_value
        assert "65.0%" in factor.actual_value
        assert "+22.5" in factor.actual_value
        assert "±10.0%" in factor.expected_reference_value

    def test_duplicate_factor_extraction_benign(self, service):
        """Tests duplicate factor when no duplicate is detected."""
        dup_details = {
            "matched_project_id": "MPLADS-2024-0017",
            "similarity": 0.4761,
            "raw_similarity": 0.4761,
            "location_match": "different_state",
            "duplicate_classification": "NONE",
        }
        factor = service._build_duplicate_factor(
            details=dup_details,
            score=0.0,
            contribution=0.0,
            severity=SeverityLevel.LOW,
            triggered=False,
            meta=service.DETECTOR_METADATA["duplicate_detection"],
            reason="No duplicate detected.",
        )
        assert factor.triggered_status is False
        assert factor.severity == SeverityLevel.LOW
        assert "47.6%" in factor.actual_value
        assert "NONE" in [e.actual_value for e in factor.evidence]

    def test_agency_pattern_factor_small_sample(self, service):
        """Tests agency pattern factor with small sample size protection."""
        agency_details = {
            "agency_name": "New Municipal Corp",
            "projects_analyzed": 1,
            "insufficient_history": True,
        }
        factor = service._build_agency_factor(
            details=agency_details,
            score=0.0,
            contribution=0.0,
            severity=SeverityLevel.LOW,
            triggered=False,
            meta=service.DETECTOR_METADATA["agency_pattern"],
            reason="Insufficient historical projects.",
        )
        assert factor.triggered_status is False
        assert "Insufficient history" in factor.actual_value


# =============================================================================
# 3. Aggregation, Ordering & Recommendation Tests
# =============================================================================

class TestExplanationSynthesis:

    def test_factor_ranked_order_and_contributions(self, service):
        """Factors must be strictly sorted descending by contribution_to_risk_score."""
        synthetic_risk_result = {
            "overall_score": 52.2,
            "risk_level": "MEDIUM",
            "confidence": 0.95,
            "summary": "Project exhibits medium overall risk.",
            "weights_used": {
                "cost_anomaly": 0.20,
                "duplicate_detection": 0.20,
                "delay_detection": 0.20,
                "progress_mismatch": 0.20,
                "agency_pattern": 0.20,
            },
            "detector_breakdown": [
                {"detector_key": "cost_anomaly", "score": 44, "weight": 0.2, "details": {}},
                {"detector_key": "duplicate_detection", "score": 0, "weight": 0.2, "details": {}},
                {"detector_key": "delay_detection", "score": 100, "weight": 0.2, "details": {"overdue_days": 527}},
                {"detector_key": "progress_mismatch", "score": 63, "weight": 0.2, "details": {"progress_gap": 22.5}},
                {"detector_key": "agency_pattern", "score": 54, "weight": 0.2, "details": {"projects_analyzed": 20}},
            ],
        }

        explanation = service.explain_risk_result(
            project_id="TEST-SYNTH-01",
            risk_result=synthetic_risk_result,
        )

        assert isinstance(explanation, StructuredExplanation)
        assert explanation.overall_score == 52.2
        assert explanation.risk_level == "MEDIUM"

        # Check factor ordering: delay (20.0) -> mismatch (12.6) -> agency (10.8) -> cost (8.8) -> duplicate (0.0)
        contribs = [f.contribution_to_risk_score for f in explanation.explanation_factors]
        assert contribs == sorted(contribs, reverse=True)
        assert explanation.explanation_factors[0].detector_name == "delay_detection"
        assert explanation.explanation_factors[1].detector_name == "progress_mismatch"

        # Check triggered count: delay, mismatch, agency, cost -> 4 triggered
        assert explanation.triggered_detectors_count == 4
        assert explanation.total_detectors_count == 5

        # Sum of contributions must equal overall_score
        total_contrib = sum(c.contribution_points for c in explanation.detector_contributions)
        assert abs(total_contrib - 52.2) < 0.1

    def test_recommendation_action_generation(self, service):
        """Actionable recommendations must target triggered detectors."""
        synthetic_risk_result = {
            "overall_score": 75.0,
            "risk_level": "HIGH",
            "confidence": 0.95,
            "detector_breakdown": [
                {"detector_key": "delay_detection", "score": 90, "weight": 0.2, "details": {"overdue_days": 300}},
                {"detector_key": "progress_mismatch", "score": 80, "weight": 0.2, "details": {"progress_gap": 35.0}},
                {"detector_key": "cost_anomaly", "score": 70, "weight": 0.2, "details": {"deviation_percentage": 150.0}},
            ],
        }
        explanation = service.explain_risk_result(
            project_id="TEST-REC-01",
            risk_result=synthetic_risk_result,
        )

        recs = explanation.recommendations
        assert len(recs) >= 3

        target_detectors = {r.target_detector for r in recs}
        assert "delay_detection" in target_detectors
        assert "progress_mismatch" in target_detectors
        assert "cost_anomaly" in target_detectors

        # Verify no accusatory language in any recommendation
        for r in recs:
            rec_text = r.recommendation.lower()
            assert "fraud" not in rec_text
            assert "corruption" not in rec_text
            assert "illegal" not in rec_text

    def test_ui_display_payload_elements(self, service):
        """UI display payload must include cards, badge color, chips, and progress."""
        synthetic_risk_result = {
            "overall_score": 45.0,
            "risk_level": "MEDIUM",
            "detector_breakdown": [
                {"detector_key": "delay_detection", "score": 80, "weight": 0.2, "details": {}},
            ],
        }
        explanation = service.explain_risk_result(
            project_id="TEST-UI-01",
            risk_result=synthetic_risk_result,
        )
        ui = explanation.ui_display
        assert "badge_color" in ui
        assert ui["badge_color"] == "amber"
        assert "display_cards" in ui
        assert len(ui["display_cards"]) == 5
        assert "warning_chips" in ui
        assert "Overdue Schedule" in ui["warning_chips"]


# =============================================================================
# 4. Live Database & API Endpoint Tests
# =============================================================================

class TestLiveProjectExplainability:

    def test_explain_live_medium_project(self, db_session, service):
        """Evaluates live project MPLADS-2024-0011 through ExplainabilityService."""
        explanation = service.explain_project("MPLADS-2024-0011", db=db_session)
        assert isinstance(explanation, StructuredExplanation)
        assert explanation.project_id == "MPLADS-2024-0011"
        assert explanation.overall_score >= 30.0
        assert explanation.risk_level in {"MEDIUM", "MODERATE"}
        assert len(explanation.explanation_factors) == 5
        assert len(explanation.detector_contributions) == 5
        assert len(explanation.recommendations) > 0

    def test_explain_live_low_project(self, db_session, service):
        """Evaluates live project MPLADS-2024-0017 (Low risk)."""
        explanation = service.explain_project("MPLADS-2024-0017", db=db_session)
        assert explanation.overall_score < 30.0
        assert explanation.risk_level == "LOW"
        assert explanation.ui_display["badge_color"] == "emerald"

    def test_api_get_project_explain_success(self):
        """Tests GET /projects/{id}/explain returns 200 and adheres to schema."""
        resp = client.get("/projects/MPLADS-2024-0011/explain")
        assert resp.status_code == 200
        data = resp.json()

        assert data["project_id"] == "MPLADS-2024-0011"
        assert "overall_score" in data
        assert "risk_level" in data
        assert "summary" in data
        assert "explanation_factors" in data
        assert len(data["explanation_factors"]) == 5
        assert "detector_contributions" in data
        assert "recommendations" in data
        assert "ui_display" in data

    def test_api_get_project_explain_recalculate(self):
        """Tests recalculate query parameter triggers fresh evaluation."""
        resp = client.get("/projects/MPLADS-2024-0017/explain?recalculate=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "MPLADS-2024-0017"

    def test_api_get_project_explain_404_not_found(self):
        """Returns 404 for non-existent project with no stack trace."""
        resp = client.get("/projects/NONEXISTENT-PRJ-9999/explain")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert "Traceback" not in str(data)

    def test_api_get_project_explain_400_invalid_id(self):
        """Returns 400 for whitespace or invalid project ID."""
        resp = client.get("/projects/%20%20%20/explain")
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data
