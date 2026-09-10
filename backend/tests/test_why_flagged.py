"""
backend/tests/test_why_flagged.py
=============================================================================
Phase 8: "Why Was This Flagged?" Explanation Generator Test Suite.
=============================================================================

Validates:
1. Structured explanation generated based ONLY on triggered detectors.
2. Complete exclusion of non-triggered detectors from risks.
3. Strict segregation of:
   - detected anomaly
   - supporting evidence
   - risk contribution
4. Conceptual text format matching:
   WHY WAS THIS FLAGGED?
   Triggered factors:
   ✓ Cost anomaly
   ✓ Delay
   ✓ Progress mismatch
   Evidence:
   • Cost is 2.56× peer median
   • Delayed by 210 days
   • Financial progress exceeds physical progress by 47 percentage points
   Risk contribution:
   • Cost anomaly: 17.2 points
   • Delay: 16.0 points
   • Progress mismatch: 14.0 points
   Overall risk:
   HIGH
5. Clean handling when no detectors trigger:
   "No significant risk factors were detected based on the configured detection thresholds."
6. Strict rejection of vague language ("suspicious", "unusual behavior") in favor of measurable facts.
7. Database integration and FastAPI endpoint:
   - GET /projects/{id}/why-flagged
"""

import os
import sys
import pytest
from typing import Dict, Any
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.main import app
from app.schemas.explainability import WhyFlaggedExplanation, RiskContributionItem
from app.services.explainability_service import ExplainabilityService, explainability_service


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
    return ExplainabilityService()


# =============================================================================
# 1. Triggered Anomaly & Conceptual Formatting Tests
# =============================================================================

class TestWhyFlaggedConceptualStructure:

    def test_three_triggered_detectors_exact_structure(self, service):
        """
        Validates the exact example scenario from the prompt:
        - Cost anomaly (score=86, weight=0.20 -> 17.2 points)
        - Delay (score=80, weight=0.20 -> 16.0 points)
        - Progress mismatch (score=70, weight=0.20 -> 14.0 points)
        - Duplicate detection and Agency pattern are NOT triggered.
        """
        synthetic_result = {
            "project_id": "MPLADS-2024-TEST-FLAGGED",
            "overall_score": 78.4,
            "risk_level": "HIGH",
            "weights_used": {
                "cost_anomaly": 0.20,
                "delay_detection": 0.20,
                "progress_mismatch": 0.20,
                "duplicate_detection": 0.20,
                "agency_pattern": 0.20,
            },
            "detector_breakdown": [
                {
                    "detector_key": "cost_anomaly",
                    "score": 86.0,
                    "triggered": True,
                    "weight": 0.20,
                    "details": {
                        "evaluated_cost": 25.6,
                        "peer_median": 10.0,
                        "deviation_percentage": 156.0,
                    }
                },
                {
                    "detector_key": "delay_detection",
                    "score": 80.0,
                    "triggered": True,
                    "weight": 0.20,
                    "details": {
                        "overdue_days": 210,
                        "delay_percentage": 57.5,
                    }
                },
                {
                    "detector_key": "progress_mismatch",
                    "score": 70.0,
                    "triggered": True,
                    "weight": 0.20,
                    "details": {
                        "financial_progress": 82.0,
                        "physical_progress": 35.0,
                        "progress_gap": 47.0,
                    }
                },
                {
                    "detector_key": "duplicate_detection",
                    "score": 10.0,
                    "triggered": False,
                    "weight": 0.20,
                    "details": {
                        "similarity": 0.12,
                        "threshold": 0.60,
                        "matched_project_id": "NONE",
                    }
                },
                {
                    "detector_key": "agency_pattern",
                    "score": 15.0,
                    "triggered": False,
                    "weight": 0.20,
                    "details": {
                        "agency_name": "Reliable Works Dept",
                        "projects_analyzed": 10,
                        "delay_rate": 0.10,
                    }
                },
            ]
        }

        exp: WhyFlaggedExplanation = service.generate_why_flagged(
            project_id="MPLADS-2024-TEST-FLAGGED",
            risk_result=synthetic_result,
        )

        assert exp.is_flagged is True
        assert exp.overall_risk == "HIGH"
        assert exp.overall_score == 78.4

        # 1. Triggered factors ONLY
        assert len(exp.triggered_factors) == 3
        assert "Cost anomaly" in exp.triggered_factors
        assert "Delay" in exp.triggered_factors
        assert "Progress mismatch" in exp.triggered_factors

        # Non-triggered factors must NOT appear
        assert "Duplicate detection" not in exp.triggered_factors
        assert "Agency pattern" not in exp.triggered_factors

        # 2. Supporting evidence (measurable and factual)
        assert len(exp.evidence) >= 3
        evidence_str = "\n".join(exp.evidence)
        assert "Cost is 2.56× peer median" in evidence_str
        assert "Delayed by 210 days" in evidence_str
        assert "Financial progress exceeds physical progress by 47 percentage points" in evidence_str

        # 3. Risk contribution points
        assert len(exp.risk_contributions) == 3
        contrib_map = {rc.factor: rc.points for rc in exp.risk_contributions}
        assert contrib_map["Cost anomaly"] == 17.2
        assert contrib_map["Delay"] == 16.0
        assert contrib_map["Progress mismatch"] == 14.0

        # 4. Formatted text matches conceptual layout
        text = exp.formatted_text
        assert "WHY WAS THIS FLAGGED?" in text
        assert "Triggered factors:" in text
        assert "✓ Cost anomaly" in text
        assert "✓ Delay" in text
        assert "✓ Progress mismatch" in text
        assert "Evidence:" in text
        assert "• Cost is 2.56× peer median" in text
        assert "• Delayed by 210 days" in text
        assert "• Financial progress exceeds physical progress by 47 percentage points" in text
        assert "Risk contribution:" in text
        assert "• Cost anomaly: 17.2 points" in text
        assert "• Delay: 16.0 points" in text
        assert "• Progress mismatch: 14.0 points" in text
        assert "Overall risk:\nHIGH" in text

        # Reassurance that non-triggered are completely excluded from text
        assert "Duplicate" not in text
        assert "Agency" not in text

    def test_no_detectors_triggered_reassurance(self, service):
        """
        Validates output when no detectors trigger an anomaly.
        """
        synthetic_result = {
            "project_id": "MPLADS-2024-CLEAN",
            "overall_score": 8.5,
            "risk_level": "LOW",
            "detector_breakdown": [
                {"detector_key": "cost_anomaly", "score": 10.0, "triggered": False},
                {"detector_key": "delay_detection", "score": 5.0, "triggered": False},
                {"detector_key": "progress_mismatch", "score": 0.0, "triggered": False},
                {"detector_key": "duplicate_detection", "score": 8.0, "triggered": False},
                {"detector_key": "agency_pattern", "score": 12.0, "triggered": False},
            ]
        }

        exp: WhyFlaggedExplanation = service.generate_why_flagged(
            project_id="MPLADS-2024-CLEAN",
            risk_result=synthetic_result,
        )

        assert exp.is_flagged is False
        assert exp.overall_risk == "LOW"
        assert len(exp.triggered_factors) == 0
        assert len(exp.evidence) == 0
        assert len(exp.risk_contributions) == 0
        assert exp.message == "No significant risk factors were detected based on the configured detection thresholds."

        text = exp.formatted_text
        assert "WHY WAS THIS FLAGGED?" in text
        assert "No significant risk factors were detected based on the configured detection thresholds." in text
        assert "Overall risk:\nLOW" in text
        assert "Triggered factors:" not in text

    def test_strict_absence_of_vague_language(self, service):
        """
        Ensures that explanations do not use subjective, ungrounded, or vague terms.
        """
        synthetic_result = {
            "project_id": "MPLADS-2024-TEST-FACTS",
            "overall_score": 65.0,
            "risk_level": "HIGH",
            "detector_breakdown": [
                {
                    "detector_key": "cost_anomaly",
                    "score": 75.0,
                    "triggered": True,
                    "weight": 0.20,
                    "details": {"evaluated_cost": 5000000.0, "peer_median": 2000000.0}
                }
            ]
        }

        exp = service.generate_why_flagged(risk_result=synthetic_result)
        combined_text = (exp.formatted_text + " " + " ".join(exp.evidence)).lower()

        vague_terms = [
            "suspicious",
            "unusual behavior",
            "looks strange",
            "shady",
            "fraudulent activity",
            "corrupt",
            "dirty",
        ]
        for term in vague_terms:
            assert term not in combined_text, f"Found forbidden vague term '{term}' in explanation."


# =============================================================================
# 2. Database Integration Tests
# =============================================================================

class TestWhyFlaggedDatabaseIntegration:

    def test_get_why_flagged_for_live_project(self, db_session, service):
        """Tests live database evaluation and why-flagged generation."""
        exp = service.get_why_flagged(
            project_id="MPLADS-2024-0017",
            db=db_session,
            recalculate=False,
        )

        assert exp.project_id == "MPLADS-2024-0017"
        assert exp.overall_risk in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert exp.header == "WHY WAS THIS FLAGGED?"
        assert isinstance(exp.is_flagged, bool)
        assert isinstance(exp.formatted_text, str)
        assert len(exp.formatted_text) > 0


# =============================================================================
# 3. FastAPI API Endpoint Tests
# =============================================================================

class TestWhyFlaggedAPI:

    def test_api_get_why_flagged_success(self):
        """Validates GET /projects/{id}/why-flagged endpoint response."""
        response = client.get("/projects/MPLADS-2024-0017/why-flagged")
        assert response.status_code == 200

        data = response.json()
        assert data["project_id"] == "MPLADS-2024-0017"
        assert "overall_risk" in data
        assert "overall_score" in data
        assert "is_flagged" in data
        assert "header" in data
        assert data["header"] == "WHY WAS THIS FLAGGED?"
        assert "triggered_factors" in data
        assert "evidence" in data
        assert "risk_contributions" in data
        assert "formatted_text" in data

    def test_api_get_why_flagged_recalculate(self):
        """Validates recalculate query parameter."""
        response = client.get("/projects/MPLADS-2024-0017/why-flagged?recalculate=true")
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "MPLADS-2024-0017"

    def test_api_get_why_flagged_not_found(self):
        """Validates 404 for nonexistent project."""
        response = client.get("/projects/NONEXISTENT-PROJECT-9999/why-flagged")
        assert response.status_code == 404

    def test_api_get_why_flagged_invalid_id(self):
        """Validates 400 for empty or whitespace project ID."""
        response = client.get("/projects/%20/why-flagged")
        assert response.status_code in (400, 404)
