"""
backend/tests/test_explained_risk_engine.py
=============================================================================
Comprehensive Test Suite for Engine 6 — Explained Risk Engine
=============================================================================

Validates:
1. Engine 6 does NOT independently calculate new signals; consumes Engines 1-5.
2. Ranking of risk factors strictly by contribution descending.
3. Accurate mathematical contribution calculation (score * weight).
4. Evidence fidelity: extracts real details without hallucinating values.
5. Strict adherence to non-accusatory governance language:
   - Contains: "potential anomaly", "unusual pattern", "possible duplicate",
               "significant deviation", "requires verification".
   - Forbids: "fraud", "corruption", "manipulation", "wrongdoing", "culpable".
6. Determinism and reproducibility across repeated executions.
7. Handling of all low, all high, mixed scores, and missing engines.
8. Accurate mapping of recommended review areas to top contributing factors.
9. Schema conformance to the requested JSON payload structure.
"""

import json
import os
import sys
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.schemas.risk_engine import (
    RiskLevel,
    EngineResult,
    RiskFactorExplanation,
    ExplainedRiskResult,
)
from app.services.risk.explained_risk_engine import ExplainedRiskEngine
from app.services.risk_engine import RiskEngine


@pytest.fixture
def explained_engine():
    return ExplainedRiskEngine()


class TestExplainedRiskEngineCore:
    """Core functionality and contract validation for Engine 6."""

    def test_does_not_calculate_new_signals(self, explained_engine):
        """Engine 6 purely consumes input scores and weights without calculating independent signals."""
        engine_results = {
            "cost_anomaly": {"score": 80, "reason": "High cost", "details": {"deviation_pct": 120}},
            "duplicate_detection": {"score": 10, "reason": "No dup", "details": {}},
            "delay_detection": {"score": 50, "reason": "Some delay", "details": {"overdue_days": 45}},
            "progress_mismatch": {"score": 20, "reason": "Minor gap", "details": {}},
            "agency_pattern": {"score": 30, "reason": "Minor pattern", "details": {}},
        }
        weights = {
            "cost_anomaly": 0.20,
            "duplicate_detection": 0.20,
            "delay_detection": 0.20,
            "progress_mismatch": 0.20,
            "agency_pattern": 0.20,
        }

        result = explained_engine.explain(
            project_id="PROJ-001",
            engine_results=engine_results,
            effective_weights=weights,
        )

        # Expected overall score: 80*0.2 + 10*0.2 + 50*0.2 + 20*0.2 + 30*0.2 = 16 + 2 + 10 + 4 + 6 = 38.0
        assert result.overall_score == 38.0
        assert result.risk_level == "MEDIUM"
        assert result.engine_scores["cost_anomaly"] == 80
        assert result.engine_scores["duplicate_detection"] == 10
        assert result.engine_scores["delay_detection"] == 50
        assert result.engine_scores["progress_mismatch"] == 20
        assert result.engine_scores["agency_pattern"] == 30

    def test_ranking_risk_factors_by_contribution(self, explained_engine):
        """Risk factors must be ranked strictly descending by their contribution."""
        engine_results = {
            "cost_anomaly": {"score": 90, "details": {}},        # 90 * 0.20 = 18.0
            "delay_detection": {"score": 75, "details": {}},     # 75 * 0.20 = 15.0
            "progress_mismatch": {"score": 50, "details": {}},   # 50 * 0.20 = 10.0
            "agency_pattern": {"score": 25, "details": {}},      # 25 * 0.20 = 5.0
            "duplicate_detection": {"score": 0, "details": {}},   # 0 * 0.20 = 0.0
        }

        result = explained_engine.explain("PROJ-RANK-01", engine_results)

        contributions = [rf.contribution for rf in result.risk_factors]
        engines_in_order = [rf.engine for rf in result.risk_factors]

        # Verify sorted strictly descending
        assert contributions == sorted(contributions, reverse=True)
        assert engines_in_order == [
            "cost_anomaly",
            "delay_detection",
            "progress_mismatch",
            "agency_pattern",
            "duplicate_detection",
        ]
        assert contributions[0] == 18.0
        assert contributions[1] == 15.0
        assert contributions[2] == 10.0
        assert contributions[3] == 5.0
        assert contributions[4] == 0.0

    def test_ranking_with_custom_weights(self, explained_engine):
        """Custom weights alter point contribution and thereby factor ranking."""
        engine_results = {
            "cost_anomaly": {"score": 60, "details": {}},        # 60 * 0.10 = 6.0
            "duplicate_detection": {"score": 50, "details": {}}, # 50 * 0.50 = 25.0
            "delay_detection": {"score": 40, "details": {}},     # 40 * 0.10 = 4.0
            "progress_mismatch": {"score": 30, "details": {}},   # 30 * 0.10 = 3.0
            "agency_pattern": {"score": 20, "details": {}},      # 20 * 0.20 = 4.0
        }
        weights = {
            "cost_anomaly": 0.10,
            "duplicate_detection": 0.50,
            "delay_detection": 0.10,
            "progress_mismatch": 0.10,
            "agency_pattern": 0.20,
        }

        result = explained_engine.explain("PROJ-WEIGHTS-01", engine_results, effective_weights=weights)

        # Duplicate detection should rank first because 25.0 > 6.0
        assert result.risk_factors[0].engine == "duplicate_detection"
        assert result.risk_factors[0].contribution == 25.0
        assert result.risk_factors[1].engine == "cost_anomaly"
        assert result.risk_factors[1].contribution == 6.0

    def test_all_low_scores_explanation(self, explained_engine):
        """All low scores produce LOW overall risk and reassuring summary."""
        engine_results = {
            "cost_anomaly": {"score": 10, "details": {"peer_median": 100000}},
            "duplicate_detection": {"score": 5, "details": {"similarity": 0.10}},
            "delay_detection": {"score": 0, "details": {"overdue_days": 0}},
            "progress_mismatch": {"score": 15, "details": {"progress_gap": 2}},
            "agency_pattern": {"score": 5, "details": {"projects_analyzed": 10}},
        }

        result = explained_engine.explain("PROJ-LOW", engine_results)

        assert result.overall_score < 30.0
        assert result.risk_level == "LOW"
        assert "low overall risk" in result.summary.lower()
        assert len(result.recommended_review) >= 1
        assert "administrative monitoring" in result.recommended_review[0].lower()

    def test_all_high_scores_explanation(self, explained_engine):
        """All high scores produce CRITICAL overall risk with elevated review recommendations."""
        engine_results = {
            "cost_anomaly": {"score": 90, "details": {"deviation_pct": 140}},
            "duplicate_detection": {"score": 85, "details": {"matched_project_id": "MPLADS-9999", "similarity": 0.95}},
            "delay_detection": {"score": 80, "details": {"overdue_days": 210, "delay_percentage": 65}},
            "progress_mismatch": {"score": 85, "details": {"financial_progress": 90, "physical_progress": 25, "progress_gap": 65}},
            "agency_pattern": {"score": 90, "details": {"agency_name": "Agency Z", "projects_analyzed": 15, "delay_rate": 80}},
        }

        result = explained_engine.explain("PROJ-HIGH", engine_results)

        assert result.overall_score >= 80.0
        assert result.risk_level == "CRITICAL"
        assert "critical overall risk" in result.summary.lower()
        # All 5 elevated areas should generate recommendations
        assert len(result.recommended_review) == 5

    def test_evidence_fidelity_no_inventions(self, explained_engine):
        """Evidence dictionary must faithfully contain actual engine outputs without fabricating data."""
        engine_results = {
            "cost_anomaly": {
                "score": 85,
                "details": {
                    "sanctioned_amount": 5000000,
                    "peer_median": 2000000,
                    "deviation_pct": 150.0,
                    "peer_group": "Roads & Bridges",
                    "sample_size": 42,
                },
            },
            "duplicate_detection": {
                "score": 75,
                "details": {
                    "matched_project_id": "MPLADS-2023-4567",
                    "similarity": 0.88,
                    "location_match": True,
                },
            },
            "delay_detection": {
                "score": 65,
                "details": {
                    "overdue_days": 120,
                    "delay_percentage": 40.0,
                    "status": "ongoing",
                },
            },
            "progress_mismatch": {
                "score": 70,
                "details": {
                    "financial_progress": 80.0,
                    "physical_progress": 30.0,
                    "progress_gap": 50.0,
                },
            },
            "agency_pattern": {
                "score": 60,
                "details": {
                    "agency_name": "Rural Works Div 1",
                    "projects_analyzed": 18,
                    "delay_rate": 55.5,
                },
            },
        }

        result = explained_engine.explain("PROJ-EVIDENCE-01", engine_results)

        factor_map = {rf.engine: rf for rf in result.risk_factors}

        # Verify exact field preservation
        assert factor_map["cost_anomaly"].evidence["sanctioned_amount"] == 5000000
        assert factor_map["cost_anomaly"].evidence["deviation_pct"] == 150.0
        assert factor_map["cost_anomaly"].evidence["peer_group"] == "Roads & Bridges"

        assert factor_map["duplicate_detection"].evidence["matched_project_id"] == "MPLADS-2023-4567"
        assert factor_map["duplicate_detection"].evidence["similarity"] == 0.88

        assert factor_map["delay_detection"].evidence["overdue_days"] == 120
        assert factor_map["delay_detection"].evidence["delay_percentage"] == 40.0

        assert factor_map["progress_mismatch"].evidence["progress_gap"] == 50.0
        assert factor_map["agency_pattern"].evidence["agency_name"] == "Rural Works Div 1"


class TestExplainedRiskEngineGovernanceLanguage:
    """Strict adherence to cautious, non-accusatory governance terminology."""

    FORBIDDEN_WORDS = [
        "fraud",
        "corrupt",
        "corruption",
        "manipulation",
        "manipulated",
        "wrongdoing",
        "guilty",
        "culpable",
        "scam",
        "embezzle",
    ]

    REQUIRED_CAUTIOUS_WORDS = [
        "potential anomaly",
        "unusual pattern",
        "possible duplicate",
        "significant deviation",
        "requires verification",
    ]

    def test_cautious_language_enforcement(self, explained_engine):
        """Output explanations must not contain forbidden words and must include cautious terms."""
        engine_results = {
            "cost_anomaly": {"score": 85, "reason": "Alleged fraud in costing", "details": {"deviation_pct": 200}},
            "duplicate_detection": {"score": 80, "reason": "Corrupt duplicate", "details": {"matched_project_id": "P-99", "similarity": 0.95}},
            "delay_detection": {"score": 75, "reason": "Willful delay", "details": {"overdue_days": 180, "delay_percentage": 50}},
            "progress_mismatch": {"score": 80, "reason": "Funds siphoned", "details": {"financial_progress": 90, "physical_progress": 20, "progress_gap": 70}},
            "agency_pattern": {"score": 85, "reason": "Corrupt agency pattern", "details": {"agency_name": "Corp X", "projects_analyzed": 10, "delay_rate": 70}},
        }

        result = explained_engine.explain("PROJ-LANGUAGE", engine_results)
        result_json = json.dumps(result.to_dict()).lower()

        # Assert no forbidden accusatory words appear in the explanation
        for word in self.FORBIDDEN_WORDS:
            assert word not in result_json, f"Prohibited accusatory word '{word}' found in explanation output!"

        # Assert cautious terms are present
        found_cautious = [term for term in self.REQUIRED_CAUTIOUS_WORDS if term in result_json]
        assert len(found_cautious) >= 3, f"Expected at least 3 cautious governance terms; found: {found_cautious}"

    def test_determinism_and_reproducibility(self, explained_engine):
        """Repeated evaluations with identical inputs yield identical output."""
        engine_results = {
            "cost_anomaly": {"score": 72, "details": {"deviation_pct": 80.5}},
            "duplicate_detection": {"score": 35, "details": {"similarity": 0.65}},
            "delay_detection": {"score": 60, "details": {"overdue_days": 90}},
            "progress_mismatch": {"score": 45, "details": {"progress_gap": 25.0}},
            "agency_pattern": {"score": 50, "details": {"delay_rate": 40.0}},
        }

        run1 = explained_engine.explain("PROJ-DET", engine_results).to_dict()
        for _ in range(25):
            run_n = explained_engine.explain("PROJ-DET", engine_results).to_dict()
            assert run1 == run_n, "Engine 6 output is not strictly deterministic!"

    def test_json_structure_matches_user_specification(self, explained_engine):
        """Output JSON schema strictly conforms to the user specification."""
        engine_results = {
            "cost_anomaly": {"score": 86, "details": {"sanctioned_amount": 1000000}},
            "duplicate_detection": {"score": 20, "details": {}},
            "delay_detection": {"score": 40, "details": {}},
            "progress_mismatch": {"score": 30, "details": {}},
            "agency_pattern": {"score": 10, "details": {}},
        }

        result = explained_engine.explain(123, engine_results, overall_score=78.4, risk_level="HIGH")
        data = result.to_dict()

        # Check required top-level keys
        assert data["project_id"] == 123
        assert data["overall_score"] == 78.4
        assert data["risk_level"] == "HIGH"
        assert isinstance(data["summary"], str)
        assert isinstance(data["risk_factors"], list)
        assert isinstance(data["recommended_review"], list)
        assert isinstance(data["engine_scores"], dict)

        # Check factor item keys
        first_factor = data["risk_factors"][0]
        assert "engine" in first_factor
        assert "score" in first_factor
        assert "contribution" in first_factor
        assert "reason" in first_factor
        assert "evidence" in first_factor


class TestExplainedRiskEngineIntegration:
    """Integration between Central RiskEngine and ExplainedRiskEngine."""

    def test_risk_engine_explain_method(self):
        """RiskEngine.explain() directly delegates to Engine 6."""
        risk_eng = RiskEngine()
        engine_results = {
            "cost_anomaly": {"score": 50, "details": {}},
            "duplicate_detection": {"score": 50, "details": {}},
            "delay_detection": {"score": 50, "details": {}},
            "progress_mismatch": {"score": 50, "details": {}},
            "agency_pattern": {"score": 50, "details": {}},
        }

        explained = risk_eng.explain("P-INT-01", engine_results)

        assert isinstance(explained, ExplainedRiskResult)
        assert explained.overall_score == 50.0
        assert explained.risk_level == "MEDIUM"
        assert len(explained.risk_factors) == 5

    def test_missing_engine_handling(self, explained_engine):
        """If an engine output is missing, it is handled safely with 0 score and note in evidence."""
        engine_results = {
            "cost_anomaly": {"score": 80, "details": {}},
            "delay_detection": {"score": 60, "details": {}},
            # duplicate_detection, progress_mismatch, agency_pattern omitted
        }

        result = explained_engine.explain("P-MISSING", engine_results)

        assert result.engine_scores["duplicate_detection"] == 0
        assert result.engine_scores["progress_mismatch"] == 0
        assert result.engine_scores["agency_pattern"] == 0
        assert len(result.risk_factors) == 5
