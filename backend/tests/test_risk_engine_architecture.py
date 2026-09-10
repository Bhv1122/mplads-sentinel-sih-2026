"""
backend/tests/test_risk_engine_architecture.py
=============================================================================
Unit Tests for the Common Architecture for the Six Risk Engines.
=============================================================================

Validates:
1. Shared interface contract (BaseRiskEngine) and abstract method enforcement
2. Standardized return structure and Pydantic model validation (EngineResult)
3. Centralized configuration:
   - Default engine weights (cost_anomaly 20%, duplicate_detection 20%,
     delay_detection 20%, progress_mismatch 20%, agency_pattern 20%)
   - Default risk level thresholds (0-29 LOW, 30-59 MEDIUM, 60-79 HIGH, 80-100 CRITICAL)
   - Engine-specific thresholds for all six engines
   - Confidence score thresholds and categorization
4. Score and confidence clamping/validation rules
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.config import settings
from app.schemas.risk_engine import RiskLevel, EngineResult
from app.services.risk.engine_base import BaseRiskEngine, SIX_RISK_ENGINES


# =============================================================================
# 1. Pydantic Model & Output Contract Tests
# =============================================================================

class TestEngineResultSchema:

    def test_engine_result_exact_keys(self):
        """EngineResult must output the exact requested JSON keys."""
        res = EngineResult(
            engine="cost_anomaly",
            score=45,
            risk_level=RiskLevel.MEDIUM,
            reason="Sample moderate cost anomaly",
            details={"peer_group": "Health", "z_score": 1.4},
            confidence=0.85,
        )
        d = res.to_dict()
        expected_keys = {"engine", "score", "risk_level", "reason", "details", "confidence"}
        assert set(d.keys()) == expected_keys
        assert d["engine"] == "cost_anomaly"
        assert d["score"] == 45
        assert d["risk_level"] == "MEDIUM"
        assert d["reason"] == "Sample moderate cost anomaly"
        assert d["details"] == {"peer_group": "Health", "z_score": 1.4}
        assert d["confidence"] == 0.85

    def test_score_clamping_and_rounding(self):
        """Score must be an integer strictly bounded within [0, 100]."""
        # Lower bound clamping
        res_low = EngineResult(
            engine="delay_detection",
            score=-15,
            risk_level=RiskLevel.LOW,
            reason="Negative input",
            confidence=0.5,
        )
        assert res_low.score == 0

        # Upper bound clamping
        res_high = EngineResult(
            engine="delay_detection",
            score=150,
            risk_level=RiskLevel.CRITICAL,
            reason="Over 100 input",
            confidence=0.5,
        )
        assert res_high.score == 100

        # Float rounding
        res_float = EngineResult(
            engine="delay_detection",
            score=74.6,
            risk_level=RiskLevel.HIGH,
            reason="Float rounding",
            confidence=0.5,
        )
        assert res_float.score == 75

    def test_confidence_clamping(self):
        """Confidence must be bounded between 0.0 and 1.0."""
        res_low = EngineResult(
            engine="progress_mismatch",
            score=20,
            risk_level=RiskLevel.LOW,
            reason="Low conf",
            confidence=-0.5,
        )
        assert res_low.confidence == 0.0

        res_high = EngineResult(
            engine="progress_mismatch",
            score=20,
            risk_level=RiskLevel.LOW,
            reason="High conf",
            confidence=1.5,
        )
        assert res_high.confidence == 1.0

    @pytest.mark.parametrize(
        "raw_level,expected_enum",
        [
            ("LOW", RiskLevel.LOW),
            ("low", RiskLevel.LOW),
            ("Low", RiskLevel.LOW),
            ("MEDIUM", RiskLevel.MEDIUM),
            ("medium", RiskLevel.MEDIUM),
            ("Moderate", RiskLevel.MEDIUM),  # Normalized to MEDIUM
            ("HIGH", RiskLevel.HIGH),
            ("high", RiskLevel.HIGH),
            ("CRITICAL", RiskLevel.CRITICAL),
            ("critical", RiskLevel.CRITICAL),
        ],
    )
    def test_risk_level_normalization(self, raw_level, expected_enum):
        res = EngineResult(
            engine="agency_pattern",
            score=30,
            risk_level=raw_level,
            reason="Level normalization test",
            confidence=0.7,
        )
        assert res.risk_level == expected_enum.value


# =============================================================================
# 2. Centralized Configuration Tests
# =============================================================================

class TestCentralizedConfiguration:

    def test_six_risk_engines_registry(self):
        """Architecture must define exactly the six risk engines."""
        assert len(SIX_RISK_ENGINES) == 6
        expected_engines = {
            "cost_anomaly",
            "duplicate_detection",
            "delay_detection",
            "progress_mismatch",
            "agency_pattern",
            "fund_utilization",
        }
        assert set(SIX_RISK_ENGINES) == expected_engines

    def test_default_engine_weights(self):
        """
        Default weights for active engines must be 20% each (sum = 100%):
        cost_anomaly = 20%
        duplicate_detection = 20%
        delay_detection = 20%
        progress_mismatch = 20%
        agency_pattern = 20%
        """
        weights = settings.engine_weights
        assert weights["cost_anomaly"] == 0.20
        assert weights["duplicate_detection"] == 0.20
        assert weights["delay_detection"] == 0.20
        assert weights["progress_mismatch"] == 0.20
        assert weights["agency_pattern"] == 0.20

        active_sum = (
            weights["cost_anomaly"]
            + weights["duplicate_detection"]
            + weights["delay_detection"]
            + weights["progress_mismatch"]
            + weights["agency_pattern"]
        )
        assert pytest.approx(active_sum, rel=1e-5) == 1.0

    @pytest.mark.parametrize(
        "score,expected_level",
        [
            (0, "LOW"),
            (10, "LOW"),
            (29, "LOW"),
            (29.9, "LOW"),
            (30, "MEDIUM"),
            (45, "MEDIUM"),
            (59, "MEDIUM"),
            (59.9, "MEDIUM"),
            (60, "HIGH"),
            (75, "HIGH"),
            (79, "HIGH"),
            (79.9, "HIGH"),
            (80, "CRITICAL"),
            (90, "CRITICAL"),
            (100, "CRITICAL"),
        ],
    )
    def test_centralized_risk_thresholds(self, score, expected_level):
        """
        Default risk thresholds:
        0–29 = LOW
        30–59 = MEDIUM
        60–79 = HIGH
        80–100 = CRITICAL
        """
        assert settings.score_to_risk_level(score) == expected_level

    def test_engine_specific_thresholds_present(self):
        """All six engines must have defined thresholds in centralized config."""
        thresholds = settings.engine_thresholds
        for engine_name in SIX_RISK_ENGINES:
            assert engine_name in thresholds, f"Missing thresholds for engine '{engine_name}'"
            assert isinstance(thresholds[engine_name], dict)
            assert len(thresholds[engine_name]) > 0

    def test_confidence_thresholds(self):
        """Confidence score tiers must be centrally defined."""
        assert settings.confidence_to_level(0.90) == "HIGH"
        assert settings.confidence_to_level(0.70) == "MEDIUM"
        assert settings.confidence_to_level(0.40) == "LOW"
        assert settings.confidence_to_level(0.10) == "VERY_LOW"


# =============================================================================
# 3. BaseRiskEngine Shared Interface Tests
# =============================================================================

class ConcreteTestEngine(BaseRiskEngine):
    engine_name = "test_custom_engine"
    version = "1.0.0"

    def evaluate(self, project_id, db, context=None):
        score = 65.0
        return self.build_result(
            score=score,
            reason="Concrete test engine evaluated project",
            details={"test_metric": 123},
            confidence=0.92,
        )


class TestBaseRiskEngineInterface:

    def test_unimplemented_engine_raises_error(self):
        """Subclasses without evaluate() cannot be instantiated."""
        class IncompleteEngine(BaseRiskEngine):
            pass

        with pytest.raises(TypeError):
            IncompleteEngine()

    def test_concrete_engine_execution(self):
        """Subclass executing evaluate() returns valid EngineResult."""
        engine = ConcreteTestEngine()
        mock_db = MagicMock()
        result = engine.evaluate("MPLADS-TEST-001", mock_db)

        assert isinstance(result, EngineResult)
        assert result.engine == "test_custom_engine"
        assert result.score == 65
        assert result.risk_level == "HIGH"
        assert result.confidence == 0.92
        assert result.details["test_metric"] == 123

    def test_shared_calculate_risk_level(self):
        """Base engine helper maps scores according to centralized config."""
        engine = ConcreteTestEngine()
        assert engine.calculate_risk_level(15) == RiskLevel.LOW
        assert engine.calculate_risk_level(35) == RiskLevel.MEDIUM
        assert engine.calculate_risk_level(65) == RiskLevel.HIGH
        assert engine.calculate_risk_level(85) == RiskLevel.CRITICAL

    def test_evaluate_confidence_helper(self):
        """Base engine helper calculates bounded confidence ratio."""
        engine = ConcreteTestEngine()
        assert engine.evaluate_confidence(4, 5) == 0.8
        assert engine.evaluate_confidence(5, 5) == 1.0
        assert engine.evaluate_confidence(0, 5) == 0.0
        assert engine.evaluate_confidence(0, 0) == settings.CONFIDENCE_DEFAULT_FALLBACK
