"""
backend/tests/test_standardized_detector_results.py
=============================================================================
Verification Test Suite for Standardized Common Detector Results & Concrete Evidence.
=============================================================================

Validates that all six risk engines:
1. Cost Anomaly Engine
2. Duplicate Detection Engine
3. Delay Detection Engine
4. Financial & Physical Progress Mismatch Engine
5. Agency Pattern Engine
6. Explained / Justification Engine

produce standardized structured outputs conforming to:
{
    "detector_name": "...",
    "triggered": true/false,
    "severity": "low|medium|high|critical",
    "score": 0-100,
    "weight": 0-1,
    "contribution": 0-100,
    "threshold": "...",
    "actual_value": "...",
    "expected_value": "...",
    "reference_value": "...",
    "evidence": [...],
    "metadata": {...}
}
"""

import pytest
from datetime import date
from sqlalchemy.orm import Session

try:
    from app.database import SessionLocal
    from app.schemas.risk_engine import RiskLevel, EngineResult, DetectorResult
    from app.services.risk.cost_anomaly_engine import CostAnomalyEngine
    from app.services.risk.duplicate_detection_engine import DuplicateDetectionEngine
    from app.services.risk.delay_detection_engine import DelayDetectionEngine
    from app.services.risk.progress_mismatch_engine import ProgressMismatchEngine
    from app.services.risk.agency_pattern_engine import AgencyPatternEngine
    from app.services.risk.explained_risk_engine import ExplainedRiskEngine
    from app.services.risk_engine import RiskEngine
except ImportError:
    from backend.app.database import SessionLocal
    from backend.app.schemas.risk_engine import RiskLevel, EngineResult, DetectorResult
    from backend.app.services.risk.cost_anomaly_engine import CostAnomalyEngine
    from backend.app.services.risk.duplicate_detection_engine import DuplicateDetectionEngine
    from backend.app.services.risk.delay_detection_engine import DelayDetectionEngine
    from backend.app.services.risk.progress_mismatch_engine import ProgressMismatchEngine
    from backend.app.services.risk.agency_pattern_engine import AgencyPatternEngine
    from backend.app.services.risk.explained_risk_engine import ExplainedRiskEngine
    from backend.app.services.risk_engine import RiskEngine


@pytest.fixture(scope="module")
def db_session():
    """Provides a transactional database session for tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestDetectorResultContract:
    """Verifies schema structure, typing, and serialization of DetectorResult."""

    def test_detector_result_schema_mandatory_fields(self):
        res = DetectorResult(
            detector_name="delay_detection",
            triggered=True,
            severity="high",
            score=75.0,
            weight=0.20,
            contribution=15.0,
            threshold="> 30 days overdue",
            actual_value="142 days overdue",
            expected_value="Planned completion: 2024-06-30",
            reference_value="As of 2024-11-19",
            evidence=[
                {"metric": "delay_days", "label": "Delay Days", "value": 142, "formatted": "142 days"}
            ],
            metadata={"status": "ongoing"},
        )
        d = res.to_dict()
        assert d["detector_name"] == "delay_detection"
        assert d["triggered"] is True
        assert d["severity"] == "high"
        assert d["score"] == 75.0
        assert d["weight"] == 0.20
        assert d["contribution"] == 15.0
        assert d["threshold"] == "> 30 days overdue"
        assert len(d["evidence"]) == 1
        assert d["metadata"]["status"] == "ongoing"

    def test_engine_result_dual_compatibility(self):
        """EngineResult must seamlessly satisfy both legacy and standardized consumers."""
        er = EngineResult(
            engine="cost_anomaly",
            score=82,
            risk_level=RiskLevel.HIGH,
            reason="Project cost is 1.8x above peer median.",
            details={"peer_median": 1500000, "project_cost": 2700000},
            confidence=0.95,
            triggered=True,
            threshold="Robust Z >= 2.0",
            actual_value="₹2,700,000.00",
            expected_value="Peer Median: ₹1,500,000.00",
            evidence=[{"metric": "peer_median", "label": "Peer Median", "value": 1500000}],
        )

        # Legacy access
        assert er.engine == "cost_anomaly"
        assert er.score == 82
        assert er.risk_level == "HIGH"
        assert er.details["peer_median"] == 1500000

        # Standardized access
        assert er.detector_name == "cost_anomaly"
        assert er.triggered is True
        assert er.severity == "high"
        assert er.threshold == "Robust Z >= 2.0"
        assert len(er.evidence) == 1

        # Serialization to standardized dict
        std_dict = er.to_standardized_dict()
        assert std_dict["detector_name"] == "cost_anomaly"
        assert std_dict["triggered"] is True
        assert std_dict["severity"] == "high"
        assert std_dict["score"] == 82

        # Strongly-typed conversion
        dr = er.to_detector_result()
        assert isinstance(dr, DetectorResult)
        assert dr.score == 82.0


class TestEngineConcreteEvidence:
    """Verifies each engine outputs concrete evidence matching the required specifications."""

    def test_cost_anomaly_concrete_evidence(self, db_session: Session):
        engine = CostAnomalyEngine()
        res = engine.evaluate("MPLADS-2024-0017", db_session)
        std = res.to_standardized_dict()

        assert std["detector_name"] == "cost_anomaly"
        assert "severity" in std
        assert isinstance(std["triggered"], bool)
        assert std["threshold"] is not None
        assert std["actual_value"] is not None
        assert std["expected_value"] is not None

        # Check concrete evidence items
        metrics = {e["metric"]: e for e in std["evidence"]}
        assert "project_cost" in metrics
        assert "peer_median" in metrics
        assert "deviation_multiplier" in metrics
        assert "percentile" in metrics
        assert "robust_z_score" in metrics
        assert "peer_iqr" in metrics

    def test_delay_detection_concrete_evidence(self, db_session: Session):
        engine = DelayDetectionEngine()
        context = {"as_of_date": date(2024, 11, 20)}
        res = engine.evaluate("MPLADS-2024-0017", db_session, context=context)
        std = res.to_standardized_dict()

        assert std["detector_name"] == "delay_detection"
        assert "severity" in std
        assert isinstance(std["triggered"], bool)
        assert std["threshold"] is not None
        assert std["actual_value"] is not None

        # Check concrete evidence items
        metrics = {e["metric"]: e for e in std["evidence"]}
        assert "planned_completion_date" in metrics
        assert "actual_current_date" in metrics
        assert "delay_days" in metrics
        assert "delay_percentage" in metrics

    def test_progress_mismatch_concrete_evidence(self, db_session: Session):
        engine = ProgressMismatchEngine()
        res = engine.evaluate("MPLADS-2024-0017", db_session)
        std = res.to_standardized_dict()

        assert std["detector_name"] == "progress_mismatch"
        assert "severity" in std
        assert isinstance(std["triggered"], bool)
        assert std["threshold"] is not None
        assert std["actual_value"] is not None

        # Check concrete evidence items
        metrics = {e["metric"]: e for e in std["evidence"]}
        assert "financial_progress" in metrics
        assert "physical_progress" in metrics
        assert "progress_gap" in metrics

    def test_duplicate_detection_concrete_evidence(self, db_session: Session):
        engine = DuplicateDetectionEngine()
        res = engine.evaluate("MPLADS-2024-0017", db_session)
        std = res.to_standardized_dict()

        assert std["detector_name"] == "duplicate_detection"
        assert "severity" in std
        assert isinstance(std["triggered"], bool)
        assert std["threshold"] is not None
        assert std["actual_value"] is not None

        # Check concrete evidence items
        metrics = {e["metric"]: e for e in std["evidence"]}
        assert "similarity_score" in metrics
        assert "matched_project_id" in metrics
        assert "matched_project_description" in metrics
        assert "similarity_threshold" in metrics

    def test_agency_pattern_concrete_evidence(self, db_session: Session):
        engine = AgencyPatternEngine()
        res = engine.evaluate("MPLADS-2024-0017", db_session)
        std = res.to_standardized_dict()

        assert std["detector_name"] == "agency_pattern"
        assert "severity" in std
        assert isinstance(std["triggered"], bool)
        assert std["threshold"] is not None
        assert std["actual_value"] is not None

        # Check concrete evidence items
        metrics = {e["metric"]: e for e in std["evidence"]}
        assert "agency_projects_analyzed" in metrics
        assert "agency_delay_rate" in metrics
        assert "agency_mismatch_rate" in metrics
        assert "agency_cost_anomaly_rate" in metrics
        assert "peer_comparison" in metrics

    def test_explained_justification_concrete_evidence(self, db_session: Session):
        engine = ExplainedRiskEngine()
        res = engine.evaluate("MPLADS-2024-0017", db_session)
        std = res.to_standardized_dict()

        assert std["detector_name"] == "explained_risk"
        assert "severity" in std
        assert isinstance(std["triggered"], bool)
        assert std["threshold"] is not None
        assert std["actual_value"] is not None

        # Check concrete evidence items
        metrics = {e["metric"]: e for e in std["evidence"]}
        assert "justification_status" in metrics
        assert "missing_or_insufficient_explanation" in metrics
        assert "supporting_fields_used" in metrics


class TestRiskEngineStandardizedIntegration:
    """Verifies that RiskEngine populates weight, contribution, and evidence in breakdown."""

    def test_risk_engine_breakdown_contains_standardized_fields(self, db_session: Session):
        risk_eng = RiskEngine()
        result = risk_eng.evaluate("MPLADS-2024-0017", db_session)

        assert "detector_breakdown" in result
        assert len(result["detector_breakdown"]) == 5

        for item in result["detector_breakdown"]:
            assert "detector_key" in item
            assert "score" in item
            assert "weight" in item
            assert "effective_weight" in item
            assert "contribution" in item
            assert "triggered" in item
            assert "severity" in item
            assert "threshold" in item
            assert "actual_value" in item
            assert "evidence" in item
            assert isinstance(item["evidence"], list)

            # Verification of contribution formula
            expected_contrib = round(float(item["score"]) * item["effective_weight"], 2)
            assert item["contribution"] == expected_contrib
