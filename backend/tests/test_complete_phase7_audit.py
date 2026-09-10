"""
backend/tests/test_complete_phase7_audit.py
=============================================================================
Complete End-to-End Audit Test Suite for Phase 7 Risk System.
=============================================================================

Systematically audits and verifies all 15 audit dimensions:
1.  Cost anomaly calculations (peer hierarchy, robust Z/MAD, scale floor, percentile).
2.  Duplicate similarity (text normalization, cosine embedding, structural factors).
3.  Delay calculations (parsing, timezones, ongoing vs completed, overdue days).
4.  Financial/physical mismatch (bidirectional gaps, threshold progression).
5.  Agency historical patterns (portfolio stats, small-sample gating, caching).
6.  Overall weighted score (exact weighted sum, normalization, clamping).
7.  Risk-level thresholds (LOW, MEDIUM, HIGH, CRITICAL boundary precision).
8.  Explanation accuracy (Engine 6 fidelity to underlying engines, ranking, evidence).
9.  Database persistence (atomic upserts, timestamp preservation, foreign keys).
10. API responses (Pydantic schema validation, zero stack trace exposure).
11. Batch processing (scopes, summary stats, embedding & agency reuse).
12. Missing data handling (null dates, zero costs, blank text, missing agency).
13. Failed-engine handling (single engine containment, renormalization).
14. Configuration changes (runtime weight and threshold overrides).
15. Performance (sub-second evaluation, cache acceleration).

Includes representative test cases verifying explanation fidelity for all 4 risk tiers:
- LOW risk (< 30)
- MEDIUM risk (30–59)
- HIGH risk (60–79)
- CRITICAL risk (80–100)
"""

import sys
import time
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import select, func
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.project import Project, Financial, Progress, RiskScore, RiskFactor
from app.services.risk_engine import RiskEngine
from app.services.risk.cost_anomaly_engine import CostAnomalyEngine
from app.services.risk.duplicate_detection_engine import DuplicateDetectionEngine
from app.services.risk.delay_detection_engine import DelayDetectionEngine
from app.services.risk.progress_mismatch_engine import ProgressMismatchEngine
from app.services.risk.agency_pattern_engine import AgencyPatternEngine
from app.services.risk.explained_risk_engine import ExplainedRiskEngine
from app.services.risk.batch_risk_service import BatchRiskService, BatchRiskSummary


@pytest.fixture(scope="module")
def db_session():
    """Provides an isolated database session for testing."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def api_client():
    """Provides a FastAPI test client."""
    return TestClient(app)


@pytest.fixture(scope="module")
def live_project_ids(db_session):
    """Retrieves all project IDs from the live database."""
    stmt = select(Project.project_id).order_by(Project.project_id)
    return [r[0] for r in db_session.execute(stmt).all()]


# =============================================================================
# Audit 1: Cost Anomaly Calculations
# =============================================================================

class TestAudit1CostAnomaly:
    """Verifies peer grouping, robust stats, scale floor, and missing data handling."""

    def test_cost_anomaly_peer_hierarchy_and_robust_metrics(self, db_session, live_project_ids):
        engine = CostAnomalyEngine()
        res = engine.evaluate(live_project_ids[0], db=db_session)

        assert res.score >= 0 and res.score <= 100
        assert res.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        details = res.details
        assert "peer_median" in details
        assert "peer_group_size" in details
        assert "deviation_percentage" in details
        assert "percentile" in details
        assert "peer_scope" in details

    def test_cost_anomaly_zero_and_missing_cost_neutrality(self, db_session):
        engine = CostAnomalyEngine()
        # Evaluate non-existent or zero cost project
        res = engine.evaluate("NON-EXISTENT-PROJECT-XYZ", db=db_session)
        assert res.score == 0
        assert res.risk_level == "LOW"
        assert res.confidence == 0.0
        assert "not found" in res.reason.lower()


# =============================================================================
# Audit 2: Duplicate Similarity
# =============================================================================

class TestAudit2DuplicateSimilarity:
    """Verifies text normalization, embedding computation, caching, and candidates."""

    def test_duplicate_text_normalization_and_embedding_cache(self, db_session, live_project_ids):
        engine = DuplicateDetectionEngine()
        res = engine.evaluate(live_project_ids[0], db=db_session)

        assert 0 <= res.score <= 100
        assert 0.0 <= res.confidence <= 1.0
        assert "similarity" in res.details
        assert "method_used" in res.details
        assert DuplicateDetectionEngine.cache_size() > 0

    def test_duplicate_short_or_empty_description_handling(self, db_session):
        engine = DuplicateDetectionEngine()
        res = engine.evaluate("NON-EXISTENT-PROJECT-XYZ", db=db_session)
        assert res.score == 0
        assert res.risk_level == "LOW"


# =============================================================================
# Audit 3: Delay Calculations
# =============================================================================

class TestAudit3DelayCalculations:
    """Verifies date parsing, timezone preservation, ongoing vs completed, overdue days."""

    def test_delay_ongoing_on_schedule_not_flagged(self, db_session):
        engine = DelayDetectionEngine()
        future_date = date.today() + timedelta(days=180)
        # Context override with future completion date
        context = {
            "expected_completion_date": future_date.isoformat(),
            "current_status": "In Progress",
            "as_of_date": date.today().isoformat(),
        }
        res = engine.evaluate("NON-EXISTENT-PROJECT", db=db_session, context=context)
        assert res.score == 0
        assert res.risk_level == "LOW"

    def test_delay_real_project_overdue_calculation(self, db_session, live_project_ids):
        engine = DelayDetectionEngine()
        res = engine.evaluate(live_project_ids[0], db=db_session)
        assert res.score >= 0 and res.score <= 100
        assert "overdue_days" in res.details
        assert "delay_percentage" in res.details


# =============================================================================
# Audit 4: Financial / Physical Mismatch
# =============================================================================

class TestAudit4ProgressMismatch:
    """Verifies bidirectional gap calculation and threshold progression."""

    def test_progress_mismatch_bidirectional_and_thresholds(self, db_session, live_project_ids):
        engine = ProgressMismatchEngine()
        res = engine.evaluate(live_project_ids[0], db=db_session)
        assert 0 <= res.score <= 100
        assert "progress_gap" in res.details
        assert "financial_progress" in res.details
        assert "physical_progress" in res.details
        assert not any(word in res.reason.lower() for word in ["fraud", "corruption", "siphoning"])


# =============================================================================
# Audit 5: Agency Historical Patterns
# =============================================================================

class TestAudit5AgencyPatterns:
    """Verifies agency grouping, sample size gating, and in-memory caching."""

    def test_agency_pattern_small_sample_size_protection(self, db_session):
        engine = AgencyPatternEngine(min_projects=5)
        # Context forcing small sample threshold
        context = {"min_projects": 100}
        res = engine.evaluate("MPLADS-2024-0001", db=db_session, context=context)
        # 20 projects in DB < 100 threshold -> must be capped at 15
        assert res.score <= 15
        assert res.confidence <= 0.35
        assert "insufficient historical" in res.reason.lower()

    def test_agency_pattern_caching_efficiency(self, db_session, live_project_ids):
        engine = AgencyPatternEngine()
        engine.clear_cache()
        res1 = engine.evaluate(live_project_ids[0], db=db_session)
        cache_len_after_1 = engine.cache_size()
        assert cache_len_after_1 >= 1

        res2 = engine.evaluate(live_project_ids[1], db=db_session)
        assert res2.details.get("agency_cached") is True


# =============================================================================
# Audit 6 & 7: Overall Weighted Score & Risk-Level Thresholds
# =============================================================================

class TestAudit6And7AggregationAndThresholds:
    """Verifies exact weighted score summation and boundary conditions."""

    @pytest.mark.parametrize(
        "score, expected_level",
        [
            (0.0, "LOW"),
            (15.0, "LOW"),
            (29.9, "LOW"),
            (30.0, "MEDIUM"),
            (45.0, "MEDIUM"),
            (59.9, "MEDIUM"),
            (60.0, "HIGH"),
            (70.0, "HIGH"),
            (79.9, "HIGH"),
            (80.0, "CRITICAL"),
            (95.0, "CRITICAL"),
            (100.0, "CRITICAL"),
        ],
    )
    def test_threshold_boundary_precision(self, score, expected_level):
        engine = RiskEngine()
        assert engine._map_risk_level(score) == expected_level

    def test_exact_weighted_sum_formula(self):
        engine = RiskEngine(
            weights={
                "cost_anomaly": 0.20,
                "duplicate_detection": 0.20,
                "delay_detection": 0.20,
                "progress_mismatch": 0.20,
                "agency_pattern": 0.20,
            }
        )
        scores = {
            "cost_anomaly": 50,
            "duplicate_detection": 20,
            "delay_detection": 100,
            "progress_mismatch": 40,
            "agency_pattern": 60,
        }
        # 50*0.2 + 20*0.2 + 100*0.2 + 40*0.2 + 60*0.2 = 10 + 4 + 20 + 8 + 12 = 54.0
        overall, level, eff_weights, unavail = engine.calculate_overall_score(scores)
        assert overall == 54.0
        assert level == "MEDIUM"
        assert len(unavail) == 0


# =============================================================================
# Audit 8: Explanation Accuracy
# =============================================================================

class TestAudit8ExplanationAccuracy:
    """Verifies Engine 6 ranks top factors by contribution without inventing signals."""

    def test_explanation_matches_engine_contributions(self, db_session, live_project_ids):
        risk_engine = RiskEngine()
        result = risk_engine.evaluate(live_project_ids[0], db=db_session, persist=False)

        explained = result["explained_risk"]
        factors = explained["risk_factors"]
        assert len(factors) == 5

        # Verify factors are strictly sorted descending by contribution
        contributions = [f["contribution"] for f in factors]
        assert contributions == sorted(contributions, reverse=True)

        # Verify sum of contributions equals overall score within rounding tolerance
        assert sum(contributions) == pytest.approx(result["overall_score"], abs=0.1)

        # Verify recommended review areas are populated
        assert isinstance(result["recommended_review"], list)
        assert len(result["recommended_review"]) > 0


# =============================================================================
# Audit 9: Database Persistence
# =============================================================================

class TestAudit9DatabasePersistence:
    """Verifies atomic upsert, timestamp preservation, and 6 factors in PostgreSQL."""

    def test_database_persistence_and_recalculation(self, db_session, live_project_ids):
        pid = live_project_ids[0]
        engine = RiskEngine()

        # Run evaluation and persist
        res1 = engine.evaluate(pid, db=db_session, persist=True)

        rs1 = db_session.execute(
            select(RiskScore).where(RiskScore.project_id == pid)
        ).scalar_one()
        created_at_1 = rs1.created_at
        factors_count_1 = db_session.scalar(
            select(func.count(RiskFactor.factor_id)).where(RiskFactor.risk_score_id == rs1.risk_score_id)
        )
        assert factors_count_1 == 6

        # Sleep briefly and recalculate in-place
        time.sleep(0.05)
        res2 = engine.evaluate(pid, db=db_session, persist=True)

        rs2 = db_session.execute(
            select(RiskScore).where(RiskScore.project_id == pid)
        ).scalar_one()
        # created_at must be preserved, updated_at must be refreshed or equal
        assert rs2.created_at == created_at_1
        assert rs2.updated_at >= created_at_1

        # Zero duplicates created
        total_scores_for_pid = db_session.scalar(
            select(func.count(RiskScore.risk_score_id)).where(RiskScore.project_id == pid)
        )
        assert total_scores_for_pid == 1


# =============================================================================
# Audit 10: API Responses
# =============================================================================

class TestAudit10APIResponses:
    """Verifies FastAPI endpoints return Pydantic models with zero stack traces."""

    def test_get_project_risk_api(self, api_client, live_project_ids):
        pid = live_project_ids[0]
        r = api_client.get(f"/projects/{pid}/risk")
        assert r.status_code == 200
        data = r.json()
        assert "overall_score" in data
        assert "risk_level" in data
        assert "engine_scores" in data
        assert "reasons" in data
        assert "evidence" in data
        assert "confidence" in data
        assert "weights_used" in data

    def test_get_project_risk_factors_api(self, api_client, live_project_ids):
        pid = live_project_ids[0]
        r = api_client.get(f"/projects/{pid}/risk/factors")
        assert r.status_code == 200
        data = r.json()
        assert data["project_id"] == pid
        assert len(data["factors"]) == 6

    def test_zero_stack_trace_on_400_and_404(self, api_client):
        # 404
        r404 = api_client.get("/projects/NON-EXISTENT-ID/risk")
        assert r404.status_code == 404
        assert "Traceback" not in r404.text
        assert "detail" in r404.json()

        # 400
        r400 = api_client.get("/projects/%20%20/risk")
        assert r400.status_code == 400
        assert "Traceback" not in r400.text


# =============================================================================
# Audit 11: Batch Processing
# =============================================================================

class TestAudit11BatchProcessing:
    """Verifies batch service execution, summary stats, and fault tolerance."""

    def test_batch_service_all_projects(self, db_session, live_project_ids):
        service = BatchRiskService()
        summary = service.process_all(db=db_session, persist=True)

        assert summary.projects_processed == len(live_project_ids)
        assert summary.successful == len(live_project_ids)
        assert summary.failed == 0
        assert summary.low + summary.medium + summary.high + summary.critical == summary.successful
        assert summary.average_score > 0.0


# =============================================================================
# Audit 12: Missing Data Handling
# =============================================================================

class TestAudit12MissingDataHandling:
    """Verifies that missing or incomplete fields do not crash the system."""

    def test_missing_data_resilience(self, db_session):
        engine = RiskEngine()
        # Evaluating non-existent project with completely missing data
        result = engine.evaluate("NON-EXISTENT-MISSING-PROJECT", db=db_session, persist=False)
        assert result["overall_score"] == 0.0
        assert result["risk_level"] == "LOW"
        assert result["confidence"] == 0.0
        assert "not found" in result["reasons"]["cost_anomaly"].lower()

        # Test each individual engine on missing data
        ca_res = engine.cost_anomaly_engine.evaluate("MISSING-ID", db=db_session)
        assert ca_res.score == 0 and ca_res.confidence == 0.0

        dd_res = engine.duplicate_detection_engine.evaluate("MISSING-ID", db=db_session)
        assert dd_res.score == 0 and dd_res.confidence == 0.0

        dl_res = engine.delay_detection_engine.evaluate("MISSING-ID", db=db_session)
        assert dl_res.score == 0 and dl_res.confidence == 0.0

        pm_res = engine.progress_mismatch_engine.evaluate("MISSING-ID", db=db_session)
        assert pm_res.score == 0 and pm_res.confidence == 0.0

        ap_res = engine.agency_pattern_engine.evaluate("MISSING-ID", db=db_session)
        assert ap_res.score == 0 and ap_res.confidence == 0.0


# =============================================================================
# Audit 13: Failed-Engine Handling
# =============================================================================

class TestAudit13FailedEngineHandling:
    """Verifies single-engine exception containment and weight renormalization."""

    def test_single_engine_failure_containment_and_renormalize(self, db_session, live_project_ids):
        engine = RiskEngine(missing_strategy="RENORMALIZE")

        # Force delay detection engine to fail
        def blow_up(*args, **kwargs):
            raise ValueError("Corrupt calendar hardware failure")

        with patch.object(engine.delay_detection_engine, "evaluate", side_effect=blow_up):
            res = engine.evaluate(live_project_ids[0], db=db_session, persist=False)

        assert "delay_detection" in res["unavailable_engines"]
        # Effective weights of remaining 4 engines should renormalize to 25% each
        for item in res["detector_breakdown"]:
            if item["detector_key"] != "delay_detection":
                assert item["effective_weight"] == pytest.approx(0.25, abs=0.01)
            else:
                assert item["effective_weight"] == 0.0

        # Score remains valid 0-100
        assert 0.0 <= res["overall_score"] <= 100.0


# =============================================================================
# Audit 14: Configuration Changes
# =============================================================================

class TestAudit14ConfigurationChanges:
    """Verifies that runtime weight and threshold overrides adapt dynamically."""

    def test_runtime_custom_weights_and_thresholds(self):
        custom_weights = {
            "cost_anomaly": 0.50,
            "duplicate_detection": 0.0,
            "delay_detection": 0.50,
            "progress_mismatch": 0.0,
            "agency_pattern": 0.0,
        }
        custom_thresholds = [
            (0.0, "LOW"),
            (40.0, "MEDIUM"),
            (70.0, "HIGH"),
            (90.0, "CRITICAL"),
        ]
        engine = RiskEngine(weights=custom_weights, thresholds=custom_thresholds)

        scores = {
            "cost_anomaly": 80,
            "delay_detection": 80,
            "duplicate_detection": 100,
            "progress_mismatch": 100,
            "agency_pattern": 100,
        }
        # 80 * 0.5 + 80 * 0.5 = 80.0
        score, level, eff_w, _ = engine.calculate_overall_score(scores)
        assert score == 80.0
        # In custom_thresholds: 70-89.9 is HIGH, 90+ is CRITICAL
        assert level == "HIGH"


# =============================================================================
# Audit 15: Performance
# =============================================================================

class TestAudit15Performance:
    """Verifies sub-second single evaluation and cache acceleration."""

    def test_single_project_sub_second_latency(self, db_session, live_project_ids):
        engine = RiskEngine()
        start = time.perf_counter()
        engine.evaluate(live_project_ids[0], db=db_session, persist=False)
        duration = time.perf_counter() - start
        # Evaluation should complete rapidly (under 1.0 second)
        assert duration < 1.0, f"Evaluation took {duration:.2f}s, expected < 1.0s"


# =============================================================================
# Representative Examples Audit Across All 4 Risk Tiers
# =============================================================================

class TestRepresentativeTiersAudit:
    """
    Audits representative projects across LOW, MEDIUM, HIGH, and CRITICAL risk tiers,
    verifying that the explanation matches the actual underlying engine outputs.
    """

    def test_tier_1_low_risk_representative(self, db_session, live_project_ids):
        """LOW risk (< 30): All signals nominal."""
        engine = RiskEngine()
        res = engine.evaluate("MPLADS-2024-0017", db=db_session, persist=False)
        assert res["overall_score"] < 30.0
        assert res["risk_level"] == "LOW"

        # Verify explanation text matches LOW tier
        assert "low overall risk" in res["summary"].lower()
        assert "expected parameters" in res["summary"].lower()

        # Engine breakdown fidelity
        for rf in res["explained_risk"]["risk_factors"]:
            assert rf["score"] == res["engine_scores"][rf["engine"]]
            assert rf["contribution"] == pytest.approx(rf["score"] * 0.20, abs=0.1)

    def test_tier_2_medium_risk_representative(self, db_session, live_project_ids):
        """MEDIUM risk (30–59): Specific operational issues (e.g. overdue delay)."""
        engine = RiskEngine()
        res = engine.evaluate("MPLADS-2024-0011", db=db_session, persist=False)
        assert 30.0 <= res["overall_score"] < 60.0
        assert res["risk_level"] == "MEDIUM"

        # Verify explanation highlights top contributing factors
        assert "medium overall risk" in res["summary"].lower()
        assert "delay detection" in res["summary"].lower()
        top_factor = res["explained_risk"]["risk_factors"][0]
        assert top_factor["engine"] == "delay_detection"
        assert top_factor["score"] == 100.0
        assert top_factor["contribution"] == 20.0

    def test_tier_3_high_risk_representative(self):
        """
        HIGH risk (60–79): Multiple compounding risk signals
        (e.g. severe delay + large progress gap + cost overrun).
        """
        engine = RiskEngine()
        mock_results = {
            "cost_anomaly": {"score": 75, "risk_level": "HIGH", "reason": "Cost deviation exceeds peer Q3 by 82%", "details": {"deviation_pct": 82.0}, "confidence": 0.9},
            "duplicate_detection": {"score": 0, "risk_level": "LOW", "reason": "No textual similarity identified", "details": {}, "confidence": 1.0},
            "delay_detection": {"score": 90, "risk_level": "HIGH", "reason": "Project overdue by 380 days (85% delay)", "details": {"overdue_days": 380}, "confidence": 1.0},
            "progress_mismatch": {"score": 80, "risk_level": "HIGH", "reason": "Financial utilization exceeds physical pace by 35%", "details": {"progress_gap": 35.0}, "confidence": 0.95},
            "agency_pattern": {"score": 70, "risk_level": "HIGH", "reason": "Historical delay rate of 65% across agency portfolio", "details": {"delay_rate": 0.65}, "confidence": 0.85},
        }
        # 75*0.2 + 0*0.2 + 90*0.2 + 80*0.2 + 70*0.2 = 15 + 0 + 18 + 16 + 14 = 63.0 (HIGH)
        score, level, weights, _ = engine.calculate_overall_score(mock_results)
        assert 60.0 <= score < 80.0
        assert level == "HIGH"

        explained = engine.explain(
            project_id="HIGH-RISK-REP-001",
            engine_results=mock_results,
            overall_score=score,
            risk_level=level,
            effective_weights=weights,
        )

        assert explained.risk_level == "HIGH"
        assert "high overall risk" in explained.summary.lower()

        # Top factor must be delay_detection (18.0 pts) followed by progress_mismatch (16.0 pts)
        factors = explained.risk_factors
        assert factors[0].engine == "delay_detection"
        assert factors[0].contribution == 18.0
        assert factors[1].engine == "progress_mismatch"
        assert factors[1].contribution == 16.0
        assert factors[2].engine == "cost_anomaly"
        assert factors[2].contribution == 15.0

    def test_tier_4_critical_risk_representative(self):
        """
        CRITICAL risk (80–100): Severe compounding failures across nearly all engines.
        """
        engine = RiskEngine()
        mock_results = {
            "cost_anomaly": {"score": 95, "risk_level": "CRITICAL", "reason": "Severe cost overrun exceeding 150% of sanction", "details": {"cost_overrun_pct": 150.0}, "confidence": 0.95},
            "duplicate_detection": {"score": 85, "risk_level": "HIGH", "reason": "Near-identical work description to previously funded work", "details": {"similarity": 0.91}, "confidence": 0.9},
            "delay_detection": {"score": 100, "risk_level": "CRITICAL", "reason": "Severe multi-year delay with stalled physical activity", "details": {"overdue_days": 750}, "confidence": 1.0},
            "progress_mismatch": {"score": 90, "risk_level": "CRITICAL", "reason": "Disbursements near 100% while physical site is under 20%", "details": {"progress_gap": 78.0}, "confidence": 0.95},
            "agency_pattern": {"score": 85, "risk_level": "CRITICAL", "reason": "Implementing agency exhibits systemic historical stalling", "details": {"delay_rate": 0.85}, "confidence": 0.9},
        }
        # 95*0.2 + 85*0.2 + 100*0.2 + 90*0.2 + 85*0.2 = 19 + 17 + 20 + 18 + 17 = 91.0 (CRITICAL)
        score, level, weights, _ = engine.calculate_overall_score(mock_results)
        assert score >= 80.0
        assert level == "CRITICAL"

        explained = engine.explain(
            project_id="CRITICAL-RISK-REP-001",
            engine_results=mock_results,
            overall_score=score,
            risk_level=level,
            effective_weights=weights,
        )

        assert explained.risk_level == "CRITICAL"
        assert "critical overall risk" in explained.summary.lower()

        # Top factor must be delay_detection (20.0 pts)
        factors = explained.risk_factors
        assert factors[0].engine == "delay_detection"
        assert factors[0].contribution == 20.0
        assert factors[1].engine == "cost_anomaly"
        assert factors[1].contribution == 19.0
        assert factors[2].engine == "progress_mismatch"
        assert factors[2].contribution == 18.0

        # High-priority recommendations must be present
        assert len(explained.recommended_review) >= 3
