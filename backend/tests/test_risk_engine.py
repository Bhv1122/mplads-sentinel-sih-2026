"""
backend/tests/test_risk_engine.py
=============================================================================
Comprehensive Unit and Integration Test Suite for Phase 7 Risk Engine.
=============================================================================

Validates:
1. Configurable weight weighting & mathematical accuracy
2. Weight renormalization when one or more detectors fail
3. Edge cases (all detectors fail, single detector succeeds, zero weights)
4. Risk level threshold boundary conditions (Low, Moderate, High, Critical)
5. Confidence score calculation based on successful detector execution
6. Database persistence with PostgreSQL CHECK constraint validation on factor_category
7. Atomic upsert idempotency (evaluating twice replaces records cleanly)
8. Batch evaluation logic
9. FastAPI endpoints (/projects/{id}/risk, recalculate, and batch endpoints)
"""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models.project import Project, RiskScore, RiskFactor
from app.schemas.risk_engine import RiskLevel, EngineResult
from app.services.risk_engine import (
    RiskEngine,
    DETECTOR_KEY_TO_FACTOR_CATEGORY,
    _score_to_impact,
)
from app.services.risk.risk_runner import RiskRunner


@pytest.fixture
def db_session():
    """Provides an active database session against PostgreSQL."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client():
    """FastAPI TestClient instance."""
    return TestClient(app)


# =============================================================================
# 1. Scoring & Weight Calculation Tests
# =============================================================================

class TestRiskEngineScoring:

    def test_default_weights_sum_to_one(self):
        """Default configured active engine weights must be 20% each and sum to 1.0."""
        weights = settings.risk_weights
        assert len(weights) == 5
        assert pytest.approx(sum(weights.values()), rel=1e-5) == 1.0
        assert weights["cost_anomaly"] == 0.20
        assert weights["duplicate_detection"] == 0.20
        assert weights["delay"] == 0.20
        assert weights["progress_mismatch"] == 0.20
        assert weights["agency_pattern"] == 0.20

    def test_weighted_score_all_successful(self):
        """Calculates exact weighted score when all 5 configured engines succeed (20% each)."""
        engine = RiskEngine()
        detector_results = {
            "cost_anomaly": {"score": 80, "severity": "high", "reason": "High cost", "details": {}},
            "delay": {"score": 60, "severity": "medium", "reason": "Moderate delay", "details": {}},
            "agency_pattern": {"score": 40, "severity": "medium", "reason": "Agency defaults", "details": {}},
            "progress_mismatch": {"score": 50, "severity": "medium", "reason": "Pace divergence", "details": {}},
            "duplicate_detection": {"score": 70, "severity": "high", "reason": "Text overlap", "details": {}},
        }
        # Expected: 80*0.20 (16) + 60*0.20 (12) + 40*0.20 (8) + 50*0.20 (10) + 70*0.20 (14) = 60.0
        score, effective_weights = engine._compute_weighted_score(detector_results)
        assert score == 60.0
        for k, w in settings.risk_weights.items():
            assert pytest.approx(effective_weights[k], rel=1e-3) == w

        confidence = engine._compute_confidence(detector_results)
        assert confidence == 1.0

        level = engine._map_risk_level(score)
        assert level in {"HIGH", "High"}

    def test_weight_renormalization_single_failure(self):
        """When 1 engine fails, its 20% weight is redistributed equally among remaining 4 (25% each)."""
        engine = RiskEngine()
        detector_results = {
            "cost_anomaly": {"score": 80, "severity": "high", "reason": "ok", "details": {}},
            "delay": {"score": 60, "severity": "medium", "reason": "ok", "details": {}},
            "agency_pattern": {"score": 40, "severity": "medium", "reason": "ok", "details": {}},
            "progress_mismatch": {"score": 50, "severity": "medium", "reason": "ok", "details": {}},
            "duplicate_detection": {
                "score": 0,
                "severity": "low",
                "reason": "Execution failed",
                "details": {"error": "embedding model offline"},
            },
        }
        score, effective_weights = engine._compute_weighted_score(detector_results)

        # Remaining 4 engines: each has 0.20 / 0.80 = 0.25
        # Expected sum: 80*0.25 (20.0) + 60*0.25 (15.0) + 40*0.25 (10.0) + 50*0.25 (12.5) = 57.5
        assert score == 57.5
        assert effective_weights["duplicate_detection"] == 0.0
        assert pytest.approx(effective_weights["cost_anomaly"], rel=1e-3) == 0.25
        assert pytest.approx(effective_weights["delay"], rel=1e-3) == 0.25
        assert pytest.approx(effective_weights["agency_pattern"], rel=1e-3) == 0.25
        assert pytest.approx(effective_weights["progress_mismatch"], rel=1e-3) == 0.25

        # Confidence: 4 of 5 = 0.8
        assert engine._compute_confidence(detector_results) == 0.8

    def test_weight_renormalization_multiple_failures(self):
        """When 3 engines fail, remaining 2 engines renormalize to 50% each."""
        engine = RiskEngine()
        detector_results = {
            "cost_anomaly": {"score": 90, "details": {}},
            "delay": {"score": 30, "details": {}},
            "agency_pattern": {"score": 0, "details": {"error": "service unavailable"}},
            "progress_mismatch": {"score": 0, "details": {"error": "missing progress"}},
            "duplicate_detection": {"score": 0, "details": {"error": "service down"}},
        }
        score, effective_weights = engine._compute_weighted_score(detector_results)

        # Successful: cost_anomaly (0.20), delay (0.20), total = 0.40
        # Each gets 0.20 / 0.40 = 0.50
        # Expected score: 90 * 0.5 + 30 * 0.5 = 60.0
        assert pytest.approx(score, rel=1e-2) == 60.0
        assert pytest.approx(effective_weights["cost_anomaly"], rel=1e-3) == 0.50
        assert pytest.approx(effective_weights["delay"], rel=1e-3) == 0.50
        assert pytest.approx(sum(effective_weights.values()), rel=1e-3) == 1.0
        assert engine._compute_confidence(detector_results) == 0.4

    def test_all_detectors_fail(self):
        """When all detectors fail, score is 0.0 and confidence is 0.0."""
        engine = RiskEngine()
        detector_results = {
            k: {"score": 0, "details": {"error": "failed"}} for k in settings.risk_weights
        }
        score, effective_weights = engine._compute_weighted_score(detector_results)
        assert score == 0.0
        assert all(w == 0.0 for w in effective_weights.values())
        assert engine._compute_confidence(detector_results) == 0.0
        assert engine._map_risk_level(score) in {"LOW", "Low"}

    def test_single_detector_succeeds(self):
        """When only 1 detector succeeds, it receives 100% of the effective weight."""
        engine = RiskEngine()
        detector_results = {
            "cost_anomaly": {"score": 85, "details": {}},
            "delay": {"score": 0, "details": {"error": "err"}},
            "agency_pattern": {"score": 0, "details": {"error": "err"}},
            "progress_mismatch": {"score": 0, "details": {"error": "err"}},
            "duplicate_detection": {"score": 0, "details": {"error": "err"}},
        }
        score, effective_weights = engine._compute_weighted_score(detector_results)
        assert score == 85.0
        assert effective_weights["cost_anomaly"] == 1.0
        assert engine._compute_confidence(detector_results) == 0.2
        assert engine._map_risk_level(score) in {"CRITICAL", "Critical"}

    def test_custom_weights_override(self):
        """Can construct RiskEngine with custom weights."""
        custom_weights = {
            "cost_anomaly": 0.50,
            "delay": 0.50,
            "fund_utilization": 0.0,
            "progress_mismatch": 0.0,
            "duplicate_detection": 0.0,
        }
        engine = RiskEngine(weights=custom_weights)
        detector_results = {
            "cost_anomaly": {"score": 100, "details": {}},
            "delay": {"score": 50, "details": {}},
            "fund_utilization": {"score": 0, "details": {}},
            "progress_mismatch": {"score": 0, "details": {}},
            "duplicate_detection": {"score": 0, "details": {}},
        }
        score, effective_weights = engine._compute_weighted_score(detector_results)
        # 100 * 0.5 + 50 * 0.5 = 75.0
        assert score == 75.0


# =============================================================================
# 2. Engines 1–5 Integration & Aggregation Tests
# =============================================================================

class TestEngines1To5Integration:
    """
    Validates central risk aggregation across Engines 1–5:
    - All low scores
    - All high scores
    - Mixed scores
    - Boundary values (0, 29, 30, 59, 60, 79, 80, 100)
    - Custom weights
    - Missing engine handling (single, multiple, all)
    - Invalid score handling (None, strings, negative, overflow, NaN)
    - Single engine failure fault containment
    """

    def test_all_low_scores_yields_low_risk(self):
        """When all 5 engines report low scores, aggregate score is in [0, 29] and level is LOW."""
        engine = RiskEngine()
        scores = {
            "cost_anomaly": 10.0,
            "duplicate_detection": 15.0,
            "delay_detection": 20.0,
            "progress_mismatch": 5.0,
            "agency_pattern": 25.0,
        }
        # 10*0.2 + 15*0.2 + 20*0.2 + 5*0.2 + 25*0.2 = 15.0
        overall, level, weights, unavailable = engine.calculate_overall_score(scores)
        assert overall == 15.0
        assert level == "LOW"
        assert len(unavailable) == 0
        for w in weights.values():
            assert pytest.approx(w, rel=1e-3) == 0.20

    def test_all_high_scores_yields_critical_or_high_risk(self):
        """When all 5 engines report critical scores (>=80), aggregate is CRITICAL."""
        engine = RiskEngine()
        critical_scores = {
            "cost_anomaly": 85.0,
            "duplicate_detection": 90.0,
            "delay_detection": 80.0,
            "progress_mismatch": 95.0,
            "agency_pattern": 88.0,
        }
        # 85*0.2 + 90*0.2 + 80*0.2 + 95*0.2 + 88*0.2 = 87.6
        overall, level, _, _ = engine.calculate_overall_score(critical_scores)
        assert overall == 87.6
        assert level == "CRITICAL"

        # High tier scores (60-79)
        high_scores = {
            "cost_anomaly": 70.0,
            "duplicate_detection": 70.0,
            "delay_detection": 70.0,
            "progress_mismatch": 70.0,
            "agency_pattern": 70.0,
        }
        overall_high, level_high, _, _ = engine.calculate_overall_score(high_scores)
        assert overall_high == 70.0
        assert level_high == "HIGH"

    def test_mixed_scores_weighted_average(self):
        """Mixed scores calculate exact weighted sum and map to MEDIUM tier."""
        engine = RiskEngine()
        mixed_scores = {
            "cost_anomaly": 80.0,
            "duplicate_detection": 20.0,
            "delay_detection": 60.0,
            "progress_mismatch": 40.0,
            "agency_pattern": 50.0,
        }
        # 80*0.2 (16) + 20*0.2 (4) + 60*0.2 (12) + 40*0.2 (8) + 50*0.2 (10) = 50.0
        overall, level, _, _ = engine.calculate_overall_score(mixed_scores)
        assert overall == 50.0
        assert level == "MEDIUM"

    @pytest.mark.parametrize(
        "score,expected_level",
        [
            (0.0, "LOW"),
            (29.0, "LOW"),
            (29.99, "LOW"),
            (30.0, "MEDIUM"),
            (59.0, "MEDIUM"),
            (59.99, "MEDIUM"),
            (60.0, "HIGH"),
            (79.0, "HIGH"),
            (79.99, "HIGH"),
            (80.0, "CRITICAL"),
            (100.0, "CRITICAL"),
        ],
    )
    def test_boundary_values_exact_mapping(self, score, expected_level):
        """Verifies exact category boundaries: 0-29 LOW, 30-59 MEDIUM, 60-79 HIGH, 80-100 CRITICAL."""
        engine = RiskEngine()
        # Single uniform score across all 5 engines
        scores = {
            "cost_anomaly": score,
            "duplicate_detection": score,
            "delay_detection": score,
            "progress_mismatch": score,
            "agency_pattern": score,
        }
        overall, level, _, _ = engine.calculate_overall_score(scores)
        assert pytest.approx(overall, rel=1e-2) == score
        assert level == expected_level

    def test_custom_weights_calculation(self):
        """Engine correctly applies user-specified custom weights summing to 1.0."""
        custom_weights = {
            "cost_anomaly": 0.40,
            "duplicate_detection": 0.20,
            "delay_detection": 0.20,
            "progress_mismatch": 0.10,
            "agency_pattern": 0.10,
        }
        engine = RiskEngine(weights=custom_weights)
        scores = {
            "cost_anomaly": 100.0,
            "duplicate_detection": 50.0,
            "delay_detection": 40.0,
            "progress_mismatch": 20.0,
            "agency_pattern": 30.0,
        }
        # 100*0.4 (40) + 50*0.2 (10) + 40*0.2 (8) + 20*0.1 (2) + 30*0.1 (3) = 63.0
        overall, level, eff_weights, unavailable = engine.calculate_overall_score(scores)
        assert overall == 63.0
        assert level == "HIGH"
        assert len(unavailable) == 0
        assert eff_weights["cost_anomaly"] == 0.40

    def test_missing_single_engine_renormalization(self):
        """When 1 engine is missing, weights renormalize among remaining 4 (25% each)."""
        engine = RiskEngine()
        # delay_detection is missing
        partial_scores = {
            "cost_anomaly": 80.0,
            "duplicate_detection": 60.0,
            "progress_mismatch": 40.0,
            "agency_pattern": 60.0,
        }
        overall, level, eff_weights, unavailable = engine.calculate_overall_score(partial_scores)

        # 4 engines -> 25% each
        # 80*0.25 (20) + 60*0.25 (15) + 40*0.25 (10) + 60*0.25 (15) = 60.0
        assert overall == 60.0
        assert level == "HIGH"
        assert "delay_detection" in unavailable
        assert eff_weights["delay_detection"] == 0.0
        assert pytest.approx(eff_weights["cost_anomaly"], rel=1e-3) == 0.25
        assert pytest.approx(sum(eff_weights.values()), rel=1e-3) == 1.0

    def test_missing_multiple_engines(self):
        """When multiple engines fail or are missing, weights renormalize proportionally."""
        engine = RiskEngine()
        # 3 engines missing, only 2 present
        partial_scores = {
            "cost_anomaly": 90.0,
            "agency_pattern": 30.0,
        }
        overall, level, eff_weights, unavailable = engine.calculate_overall_score(partial_scores)
        # 90*0.50 + 30*0.50 = 60.0
        assert overall == 60.0
        assert level == "HIGH"
        assert len(unavailable) == 3
        assert set(unavailable) == {"duplicate_detection", "delay_detection", "progress_mismatch"}
        assert pytest.approx(eff_weights["cost_anomaly"], rel=1e-3) == 0.50
        assert pytest.approx(eff_weights["agency_pattern"], rel=1e-3) == 0.50

    def test_all_engines_missing_does_not_crash(self):
        """When all engines fail/missing, returns score 0.0, LOW, confidence 0.0 without crashing."""
        engine = RiskEngine()
        empty_scores = {}
        overall, level, eff_weights, unavailable = engine.calculate_overall_score(empty_scores)
        assert overall == 0.0
        assert level == "LOW"
        assert len(unavailable) == 5
        assert all(w == 0.0 for w in eff_weights.values())

    def test_invalid_scores_clamping_and_handling(self):
        """Tests handling of None, string, negative, overflow, and NaN scores."""
        engine = RiskEngine()
        scores = {
            "cost_anomaly": -20.0,          # Clamped to 0
            "duplicate_detection": 150.0,    # Clamped to 100
            "delay_detection": None,         # Marked unavailable
            "progress_mismatch": "invalid",  # Marked unavailable
            "agency_pattern": float("nan"),  # Marked unavailable
        }
        overall, level, eff_weights, unavailable = engine.calculate_overall_score(scores)

        # Active valid: cost_anomaly (0.0 clamped) and duplicate_detection (100.0 clamped)
        # Each gets 50% weight -> 0.0 * 0.5 + 100.0 * 0.5 = 50.0
        assert overall == 50.0
        assert level == "MEDIUM"
        assert set(unavailable) == {"delay_detection", "progress_mismatch", "agency_pattern"}
        assert pytest.approx(eff_weights["cost_anomaly"], rel=1e-3) == 0.50
        assert pytest.approx(eff_weights["duplicate_detection"], rel=1e-3) == 0.50

    def test_engine_failure_fault_containment(self):
        """If one engine raises an unhandled exception, pipeline logs and aggregates remaining engines."""
        mock_failing_engine = MagicMock()
        mock_failing_engine.evaluate.side_effect = RuntimeError("Database timeout in delay engine")

        mock_ok_cost = MagicMock()
        mock_ok_cost.evaluate.return_value = EngineResult(
            engine="cost_anomaly", score=80, risk_level=RiskLevel.HIGH, reason="High", confidence=0.9
        )
        mock_ok_dup = MagicMock()
        mock_ok_dup.evaluate.return_value = EngineResult(
            engine="duplicate_detection", score=60, risk_level=RiskLevel.MEDIUM, reason="Dup", confidence=0.9
        )
        mock_ok_prog = MagicMock()
        mock_ok_prog.evaluate.return_value = EngineResult(
            engine="progress_mismatch", score=40, risk_level=RiskLevel.MEDIUM, reason="Gap", confidence=0.9
        )
        mock_ok_agency = MagicMock()
        mock_ok_agency.evaluate.return_value = EngineResult(
            engine="agency_pattern", score=60, risk_level=RiskLevel.MEDIUM, reason="Agency", confidence=0.9
        )

        engine = RiskEngine(
            cost_anomaly_engine=mock_ok_cost,
            duplicate_detection_engine=mock_ok_dup,
            delay_detection_engine=mock_failing_engine,
            progress_mismatch_engine=mock_ok_prog,
            agency_pattern_engine=mock_ok_agency,
        )

        mock_db = MagicMock()
        # Must not raise exception
        result = engine.evaluate("P-01", db=mock_db, persist=False)
        assert result["project_id"] == "P-01"
        assert result["overall_risk_score"] == 60.0  # 80*0.25 + 60*0.25 + 40*0.25 + 60*0.25
        assert result["risk_level"] == "HIGH"
        assert "delay_detection" in result["unavailable_engines"]


# =============================================================================
# 3. Threshold Boundary Tests
# =============================================================================

class TestRiskThresholds:

    @pytest.mark.parametrize(
        "score,expected_level",
        [
            (0.0, "LOW"),
            (15.0, "LOW"),
            (29.99, "LOW"),
            (30.0, "MEDIUM"),
            (45.0, "MEDIUM"),
            (59.99, "MEDIUM"),
            (60.0, "HIGH"),
            (70.0, "HIGH"),
            (79.99, "HIGH"),
            (80.0, "CRITICAL"),
            (95.0, "CRITICAL"),
            (100.0, "CRITICAL"),
        ],
    )
    def test_risk_level_boundaries(self, score, expected_level):
        engine = RiskEngine()
        assert engine._map_risk_level(score) == expected_level

    @pytest.mark.parametrize(
        "score,expected_impact",
        [
            (0, "Low"),
            (29, "Low"),
            (30, "Medium"),
            (59, "Medium"),
            (60, "High"),
            (79, "High"),
            (80, "Critical"),
            (100, "Critical"),
        ],
    )
    def test_score_to_impact(self, score, expected_impact):
        assert _score_to_impact(score) == expected_impact


# =============================================================================
# 3. Persistence & Database Check Constraint Tests
# =============================================================================

class TestRiskEnginePersistence:

    def test_factor_category_mapping_valid_in_db(self):
        """All mapped factor categories must be valid according to the DB check constraint."""
        valid_db_categories = {
            "Agency Past Performance",
            "Delay in Tendering",
            "Budget Gap",
            "Slow Physical Pace",
            "Monsoon Seasonality",
            "Geographic Remoteness",
            "Land Dispute",
            "Contractor Inaction",
            "Other",
        }
        for detector_key, cat in DETECTOR_KEY_TO_FACTOR_CATEGORY.items():
            assert cat in valid_db_categories, (
                f"Category '{cat}' for detector '{detector_key}' violates PostgreSQL check constraint"
            )

    def test_evaluate_and_persist_real_project(self, db_session):
        """Evaluates real project MPLADS-2024-0001, persists results, and verifies rows in DB."""
        engine = RiskEngine()
        result = engine.evaluate(
            project_id="MPLADS-2024-0001",
            db=db_session,
            persist=True,
        )

        assert result["project_id"] == "MPLADS-2024-0001"
        assert 0.0 <= result["overall_risk_score"] <= 100.0
        assert result["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL", "Low", "Moderate", "High", "Critical"}
        assert 0.0 <= result["confidence"] <= 1.0
        assert len(result["detector_breakdown"]) == 5

        # Verify persisted RiskScore row
        score_row = db_session.query(RiskScore).filter_by(project_id="MPLADS-2024-0001").first()
        assert score_row is not None
        assert float(score_row.overall_risk_score) == result["overall_risk_score"]
        db_map = {"LOW": "Low", "MEDIUM": "Moderate", "HIGH": "High", "CRITICAL": "Critical"}
        expected_db_level = db_map.get(result["risk_level"], result["risk_level"])
        assert score_row.risk_level == expected_db_level

        # Verify persisted RiskFactor rows (all 6 engines)
        factors = db_session.query(RiskFactor).filter_by(project_id="MPLADS-2024-0001").all()
        assert len(factors) == 6

        # Verify all factor categories satisfy the CHECK constraint without DB error
        for f in factors:
            assert f.factor_category in {
                "Agency Past Performance", "Delay in Tendering", "Budget Gap",
                "Slow Physical Pace", "Monsoon Seasonality", "Geographic Remoteness",
                "Land Dispute", "Contractor Inaction", "Other"
            }
            assert f.factor_impact in {"Low", "Medium", "High", "Critical"}
            assert 0.0 <= float(f.factor_weight) <= 1.0

    def test_idempotent_recalculation(self, db_session):
        """Recalculating risk replaces existing score and factors cleanly without duplicate key error."""
        engine = RiskEngine()
        # First evaluation
        res1 = engine.evaluate("MPLADS-2024-0002", db=db_session, persist=True)
        # Second evaluation (idempotent overwrite)
        res2 = engine.evaluate("MPLADS-2024-0002", db=db_session, persist=True)

        assert res1["overall_risk_score"] == res2["overall_risk_score"]

        # Exactly 1 RiskScore and 6 RiskFactor rows must exist
        score_count = db_session.query(RiskScore).filter_by(project_id="MPLADS-2024-0002").count()
        factor_count = db_session.query(RiskFactor).filter_by(project_id="MPLADS-2024-0002").count()
        assert score_count == 1
        assert factor_count == 6


# =============================================================================
# 4. Batch Evaluation Tests
# =============================================================================

class TestRiskEngineBatch:

    def test_batch_evaluation_with_explicit_ids(self, db_session):
        engine = RiskEngine()
        pids = ["MPLADS-2024-0001", "MPLADS-2024-0002"]
        results = engine.evaluate_batch(db=db_session, project_ids=pids, persist=True)
        assert len(results) == 2
        assert {r["project_id"] for r in results} == set(pids)

    def test_batch_evaluation_with_limit(self, db_session):
        engine = RiskEngine()
        results = engine.evaluate_batch(db=db_session, project_ids=None, limit=3, persist=False)
        assert len(results) <= 3
        for r in results:
            assert "overall_risk_score" in r
            assert "risk_level" in r


# =============================================================================
# 5. FastAPI Route Endpoints Tests
# =============================================================================

class TestRiskAPIEndpoints:

    def test_get_project_risk_cached(self, test_client):
        """GET /api/v1/projects/{id}/risk returns cached risk assessment."""
        response = test_client.get("/api/v1/projects/MPLADS-2024-0001/risk")
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "MPLADS-2024-0001"
        assert "overall_risk_score" in data
        assert "risk_level" in data
        assert "confidence" in data
        assert "sub_scores" in data
        assert "detector_breakdown" in data
        assert len(data["detector_breakdown"]) > 0

    def test_get_project_risk_recalculate_query_param(self, test_client):
        """GET /api/v1/projects/{id}/risk?recalculate=true triggers fresh recalculation."""
        response = test_client.get("/api/v1/projects/MPLADS-2024-0001/risk?recalculate=true")
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "MPLADS-2024-0001"
        assert len(data["detector_breakdown"]) == 5

    def test_get_project_risk_not_found(self, test_client):
        """GET /api/v1/projects/{id}/risk returns 404 for nonexistent project."""
        response = test_client.get("/api/v1/projects/MPLADS-DOES-NOT-EXIST/risk")
        assert response.status_code == 404

    def test_post_project_risk_recalculate(self, test_client):
        """POST /api/v1/projects/{id}/risk/recalculate forces fresh recalculation."""
        response = test_client.post("/api/v1/projects/MPLADS-2024-0002/risk/recalculate")
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "MPLADS-2024-0002"
        assert len(data["detector_breakdown"]) == 5

    def test_post_project_risk_recalculate_not_found(self, test_client):
        """POST /api/v1/projects/{id}/risk/recalculate returns 404 for nonexistent project."""
        response = test_client.post("/api/v1/projects/NONEXISTENT-PROJ-ID/risk/recalculate")
        assert response.status_code == 404

    def test_post_batch_risk_explicit_ids(self, test_client):
        """POST /api/v1/projects/risk/batch with explicit IDs evaluates only those projects."""
        payload = {
            "project_ids": ["MPLADS-2024-0001", "MPLADS-2024-0002"],
            "limit": 10,
        }
        response = test_client.post("/api/v1/projects/risk/batch", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        pids = [item["project_id"] for item in data]
        assert "MPLADS-2024-0001" in pids
        assert "MPLADS-2024-0002" in pids

    def test_post_batch_risk_default_limit(self, test_client):
        """POST /api/v1/projects/risk/batch with limit evaluates top projects."""
        payload = {
            "limit": 3
        }
        response = test_client.post("/api/v1/projects/risk/batch", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 3
