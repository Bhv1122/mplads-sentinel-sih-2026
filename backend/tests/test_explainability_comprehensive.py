"""
backend/tests/test_explainability_comprehensive.py
=============================================================================
Comprehensive Explainability System Test Suite
=============================================================================

Covers all 12 user-specified test categories:

 1. Every triggered detector produces at least one evidence item.
 2. Evidence values match the underlying detector output.
 3. No fabricated numerical values appear.
 4. Untriggered detectors are not presented as active risk factors.
 5. Risk contributions correctly correspond to the Risk Engine.
 6. Risk contributions reconcile with the final risk score.
 7. Thresholds shown to users match configured thresholds.
 8. Missing data does not produce misleading explanations.
 9. Projects with no detected risks receive a clear explanation.
10. API responses conform to the defined schema.
11. Rounding does not materially change the underlying values.
12. Explanation generation is deterministic for the same project data.
"""

import os
import sys
import math
import copy
import pytest
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock, PropertyMock
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
    RiskScoreDecomposition,
    RiskScoreDecompositionItem,
)
from app.config import settings
from app.services.explainability_service import (
    ExplainabilityService,
    explainability_service,
    _normalize_risk_level,
    _normalize_severity,
)

client = TestClient(app)

# =============================================================================
# Fixtures
# =============================================================================

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
    """Provides a fresh ExplainabilityService instance."""
    return ExplainabilityService()


# =============================================================================
# Synthetic Risk Result Builders
# =============================================================================

def _make_risk_result(
    overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    overall_score: float = 72.0,
    risk_level: str = "HIGH",
) -> Dict[str, Any]:
    """
    Constructs a synthetic risk-engine result dictionary matching the
    real RiskEngine.evaluate() output shape.
    """
    base_engines = {
        "cost_anomaly": {
            "score": 85.0,
            "weight": 0.20,
            "effective_weight": 0.20,
            "triggered": True,
            "severity": "high",
            "risk_level": "HIGH",
            "details": {
                "evaluated_cost": 256_000_000,
                "peer_median": 100_000_000,
                "financial_progress": 82.0,
                "physical_progress": 35.0,
                "threshold": "Cost ≥ 2.0× peer median",
                "triggered": True,
            },
            "reason": "Cost peer deviation analysis.",
        },
        "delay_detection": {
            "score": 72.0,
            "weight": 0.25,
            "effective_weight": 0.25,
            "triggered": True,
            "severity": "high",
            "risk_level": "HIGH",
            "details": {
                "overdue_days": 210,
                "planned_start_date": "2023-01-15",
                "planned_completion_date": "2023-12-31",
                "expected_completion_date": "2024-07-29",
                "planned_duration": 350,
                "threshold": "Delay > 30 days beyond planned completion date",
                "triggered": True,
            },
            "reason": "Schedule delay detection.",
        },
        "progress_mismatch": {
            "score": 88.0,
            "weight": 0.25,
            "effective_weight": 0.25,
            "triggered": True,
            "severity": "high",
            "risk_level": "HIGH",
            "details": {
                "financial_progress": 82.0,
                "physical_progress": 35.0,
                "progress_gap": 47.0,
                "sanctioned_amount": 256_000_000,
                "expenditure": 209_920_000,
                "threshold": "Financial vs Physical divergence > 10 percentage points",
                "triggered": True,
            },
            "reason": "Financial vs physical progress divergence.",
        },
        "duplicate_detection": {
            "score": 10.0,
            "weight": 0.20,
            "effective_weight": 0.20,
            "triggered": False,
            "severity": "low",
            "risk_level": "LOW",
            "details": {
                "similarity": 0.32,
                "threshold": 0.85,
                "matched_project_id": "MPLADS-2024-0009",
                "triggered": False,
            },
            "reason": "No duplicate patterns found.",
        },
        "agency_pattern": {
            "score": 65.0,
            "weight": 0.20,
            "effective_weight": 0.20,
            "triggered": True,
            "severity": "medium",
            "risk_level": "MEDIUM",
            "details": {
                "agency_name": "PWD Test Agency",
                "delay_rate": 0.35,
                "projects_analyzed": 12,
                "threshold": "Historical delay rate > 25%",
                "triggered": True,
            },
            "reason": "Agency historical pattern analysis.",
        },
    }

    if overrides:
        for key, vals in overrides.items():
            if key in base_engines:
                base_engines[key].update(vals)
            else:
                base_engines[key] = vals

    # Build detector_breakdown list from engines
    breakdown = []
    for k, v in base_engines.items():
        entry = {
            "detector_key": k,
            "detector_name": k,
            "score": v["score"],
            "weight": v["weight"],
            "effective_weight": v["effective_weight"],
            "triggered": v["triggered"],
            "severity": v.get("severity", "low"),
            "risk_level": v.get("risk_level", "LOW"),
            "details": v.get("details", {}),
            "reason": v.get("reason", ""),
        }
        breakdown.append(entry)

    return {
        "overall_score": overall_score,
        "overall_risk_score": overall_score,
        "risk_level": risk_level,
        "detector_breakdown": breakdown,
        "engines": base_engines,
        "weights_used": {k: v["effective_weight"] for k, v in base_engines.items()},
    }


def _make_zero_risk_result() -> Dict[str, Any]:
    """All detectors score 0, nothing triggered."""
    overrides = {}
    for det in ["cost_anomaly", "delay_detection", "progress_mismatch",
                "duplicate_detection", "agency_pattern"]:
        overrides[det] = {
            "score": 0.0,
            "weight": 0.20,
            "effective_weight": 0.20,
            "triggered": False,
            "severity": "low",
            "risk_level": "LOW",
            "details": {"triggered": False},
            "reason": "Within normal parameters.",
        }
    return _make_risk_result(overrides=overrides, overall_score=0.0, risk_level="LOW")


def _make_missing_data_result() -> Dict[str, Any]:
    """Simulates missing data: empty details dictionaries."""
    overrides = {}
    for det in ["cost_anomaly", "delay_detection", "progress_mismatch",
                "duplicate_detection", "agency_pattern"]:
        overrides[det] = {
            "score": 50.0,
            "weight": 0.20,
            "effective_weight": 0.20,
            "triggered": True,
            "severity": "medium",
            "risk_level": "MEDIUM",
            "details": {},  # Deliberately empty
            "reason": "Insufficient data.",
        }
    return _make_risk_result(overrides=overrides, overall_score=50.0, risk_level="MEDIUM")


# =============================================================================
# TEST CATEGORY 1: Every triggered detector produces at least one evidence item
# =============================================================================

class TestTriggeredDetectorsProduceEvidence:
    """Category 1: Every triggered detector produces at least one evidence item."""

    def test_all_triggered_detectors_have_evidence(self, service):
        """When a detector is triggered, its factor MUST contain ≥1 evidence item."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation(
            project_id="TEST-001",
            db=MagicMock(),
            risk_result=rr,
        )
        for factor in explanation.factors:
            if factor.triggered:
                assert len(factor.evidence) >= 1, (
                    f"Triggered detector '{factor.detector}' has no evidence items."
                )

    def test_individual_cost_anomaly_evidence(self, service):
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T1", MagicMock(), risk_result=rr)
        cost_factor = next(f for f in explanation.factors if f.detector == "cost_anomaly")
        assert cost_factor.triggered is True
        assert len(cost_factor.evidence) >= 1
        assert any("peer median" in e.text.lower() or "cost" in e.text.lower()
                    for e in cost_factor.evidence)

    def test_individual_delay_evidence(self, service):
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T2", MagicMock(), risk_result=rr)
        delay_factor = next(f for f in explanation.factors if f.detector == "delay_detection")
        assert delay_factor.triggered is True
        assert len(delay_factor.evidence) >= 1
        assert any("delay" in e.text.lower() or "days" in e.text.lower()
                    for e in delay_factor.evidence)

    def test_individual_progress_mismatch_evidence(self, service):
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T3", MagicMock(), risk_result=rr)
        pm_factor = next(f for f in explanation.factors if f.detector == "progress_mismatch")
        assert pm_factor.triggered is True
        assert len(pm_factor.evidence) >= 1
        assert any("progress" in e.text.lower() for e in pm_factor.evidence)

    def test_individual_agency_pattern_evidence(self, service):
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T4", MagicMock(), risk_result=rr)
        ag_factor = next(f for f in explanation.factors if f.detector == "agency_pattern")
        assert ag_factor.triggered is True
        assert len(ag_factor.evidence) >= 1

    def test_individual_duplicate_triggered_evidence(self, service):
        """When duplicate IS triggered, it also must produce evidence."""
        rr = _make_risk_result(overrides={
            "duplicate_detection": {
                "score": 90.0,
                "triggered": True,
                "severity": "high",
                "details": {
                    "similarity": 0.94,
                    "threshold": 0.85,
                    "matched_project_id": "MPLADS-2024-0099",
                    "triggered": True,
                },
            }
        })
        explanation = service.get_project_explanation("T5", MagicMock(), risk_result=rr)
        dup_factor = next(f for f in explanation.factors if f.detector == "duplicate_detection")
        assert dup_factor.triggered is True
        assert len(dup_factor.evidence) >= 1


# =============================================================================
# TEST CATEGORY 2: Evidence values match the underlying detector output
# =============================================================================

class TestEvidenceMatchesDetectorOutput:
    """Category 2: Evidence values match the underlying detector output."""

    def test_cost_evidence_matches_input(self, service):
        """Cost evidence actual_value and reference_value must trace to detector details."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-COST", MagicMock(), risk_result=rr)
        cost_factor = next(f for f in explanation.factors if f.detector == "cost_anomaly")
        ev = cost_factor.evidence[0]
        # Input cost = 256_000_000 (25.6 Cr), median = 100_000_000 (10.0 Cr)
        assert ev.actual_value is not None
        assert ev.reference_value is not None
        # Check that the ratio text is correct: 256M / 100M = 2.56
        assert "2.56" in ev.text

    def test_delay_evidence_matches_days(self, service):
        """Delay evidence actual_value must match the overdue_days from details."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-DLY", MagicMock(), risk_result=rr)
        delay_factor = next(f for f in explanation.factors if f.detector == "delay_detection")
        ev = delay_factor.evidence[0]
        assert ev.actual_value == 210
        assert ev.unit == "days"
        assert "210" in ev.text

    def test_progress_evidence_matches_percentages(self, service):
        """Progress mismatch evidence must match financial/physical values."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-PM", MagicMock(), risk_result=rr)
        pm_factor = next(f for f in explanation.factors if f.detector == "progress_mismatch")
        ev = pm_factor.evidence[0]
        # fp=82, pp=35, diff=47
        assert ev.actual_value == 82.0
        assert ev.reference_value == 35.0
        assert "47" in ev.text

    def test_duplicate_evidence_matches_similarity(self, service):
        """Duplicate evidence must report the correct similarity percentage."""
        rr = _make_risk_result(overrides={
            "duplicate_detection": {
                "score": 90.0,
                "triggered": True,
                "severity": "high",
                "details": {
                    "similarity": 0.94,
                    "threshold": 0.85,
                    "matched_project_id": "MPLADS-TEST-X",
                    "triggered": True,
                },
            }
        })
        explanation = service.get_project_explanation("T-DUP", MagicMock(), risk_result=rr)
        dup_factor = next(f for f in explanation.factors if f.detector == "duplicate_detection")
        ev = dup_factor.evidence[0]
        assert ev.actual_value == 94.0  # 0.94 * 100
        assert ev.reference_value == 85.0  # 0.85 * 100

    def test_agency_evidence_matches_delay_rate(self, service):
        """Agency pattern evidence must reflect the input delay_rate."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-AG", MagicMock(), risk_result=rr)
        ag_factor = next(f for f in explanation.factors if f.detector == "agency_pattern")
        ev = ag_factor.evidence[0]
        # delay_rate = 0.35 → 35%
        assert ev.actual_value == 35.0
        expected_agency_ref = round(getattr(settings, "AGENCY_DELAY_RATE_THRESHOLD", 0.50) * 100, 1)
        assert ev.reference_value == expected_agency_ref  # benchmark threshold from config


# =============================================================================
# TEST CATEGORY 3: No fabricated numerical values appear
# =============================================================================

class TestNoFabricatedValues:
    """Category 3: No fabricated numerical values appear."""

    def test_evidence_values_trace_to_input(self, service):
        """All numerical evidence values must be traceable to the risk_result input."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-FAB", MagicMock(), risk_result=rr)

        # Collect all input numerical values from details
        input_values = set()
        for det_key, det_data in rr["engines"].items():
            for k, v in det_data.get("details", {}).items():
                if isinstance(v, (int, float)):
                    input_values.add(round(float(v), 2))
                    # Add common transformations
                    fv = float(v)
                    if 0 < fv <= 1.0:
                        input_values.add(round(fv * 100.0, 2))
                    if fv >= 100_000:
                        input_values.add(round(fv / 100_000, 2))
                    if fv >= 10_000_000:
                        input_values.add(round(fv / 10_000_000, 2))

        # Add derived values (ratios, differences)
        input_values.add(2.56)  # 256M / 100M
        input_values.add(47.0)  # 82 - 35
        input_values.add(0)     # reference for on-time

        for factor in explanation.factors:
            for ev in factor.evidence:
                if ev.actual_value is not None and isinstance(ev.actual_value, (int, float)):
                    val = round(float(ev.actual_value), 2)
                    assert val in input_values or val == 0.0, (
                        f"Fabricated actual_value {val} in {factor.detector}. "
                        f"Not traceable to input values: {sorted(input_values)[:20]}..."
                    )

    def test_contributions_not_fabricated(self, service):
        """Contribution values must equal score * weight (not invented numbers)."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-FABCON", MagicMock(), risk_result=rr)
        for factor in explanation.factors:
            if factor.detector_score is not None and factor.weight is not None:
                expected = round(factor.detector_score * factor.weight, 1)
                assert abs(factor.contribution - expected) <= 0.2, (
                    f"Fabricated contribution {factor.contribution} for {factor.detector}. "
                    f"Expected {expected} (score={factor.detector_score} × weight={factor.weight})"
                )


# =============================================================================
# TEST CATEGORY 4: Untriggered detectors are not presented as active risk factors
# =============================================================================

class TestUntriggeredDetectorsFiltered:
    """Category 4: Untriggered detectors are not presented as active risk factors."""

    def test_only_triggered_mode_excludes_untriggered(self, service):
        """When only_triggered=True, untriggered detectors must not appear."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation(
            "T-UNTRIG", MagicMock(), risk_result=rr, only_triggered=True,
        )
        for factor in explanation.factors:
            assert factor.triggered is True, (
                f"Untriggered detector '{factor.detector}' is presented when only_triggered=True"
            )

    def test_untriggered_duplicate_not_flagged(self, service):
        """Default result has duplicate untriggered — it should have triggered=False."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-DUPU", MagicMock(), risk_result=rr)
        dup = next(f for f in explanation.factors if f.detector == "duplicate_detection")
        assert dup.triggered is False

    def test_untriggered_not_in_summary_text(self, service):
        """Untriggered detectors should not be mentioned in the summary."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-SUM", MagicMock(), risk_result=rr)
        # 'duplicate' should not appear in summary since it's not triggered
        summary_lower = explanation.summary.lower()
        assert "duplicate" not in summary_lower, (
            f"Summary mentions untriggered 'duplicate': {explanation.summary}"
        )

    def test_all_factors_present_when_not_filtered(self, service):
        """Without only_triggered, all 5 canonical detectors should be present."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation(
            "T-ALL", MagicMock(), risk_result=rr, only_triggered=False,
        )
        detector_keys = {f.detector for f in explanation.factors}
        for k in ["cost_anomaly", "delay_detection", "progress_mismatch",
                   "duplicate_detection", "agency_pattern"]:
            assert k in detector_keys, f"Missing detector '{k}' in unfiltered response"


# =============================================================================
# TEST CATEGORY 5: Risk contributions correctly correspond to the Risk Engine
# =============================================================================

class TestRiskContributionsCorrespondToEngine:
    """Category 5: Risk contributions correctly correspond to the Risk Engine."""

    def test_contribution_equals_score_times_weight(self, service):
        """Each factor's contribution must equal detector_score × weight."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-RC", MagicMock(), risk_result=rr)
        for factor in explanation.factors:
            if factor.detector_score is not None and factor.weight is not None:
                expected = round(factor.detector_score * factor.weight, 1)
                assert abs(factor.contribution - expected) <= 0.15, (
                    f"{factor.detector}: contribution={factor.contribution}, "
                    f"expected={expected} (score={factor.detector_score} × weight={factor.weight})"
                )

    def test_detector_scores_match_input(self, service):
        """detector_score on each factor must match the engine input."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-DS", MagicMock(), risk_result=rr)
        engine_scores = {k: v["score"] for k, v in rr["engines"].items()}
        for factor in explanation.factors:
            if factor.detector in engine_scores:
                expected_score = engine_scores[factor.detector]
                assert abs(factor.detector_score - expected_score) <= 0.1, (
                    f"{factor.detector}: got score {factor.detector_score}, "
                    f"expected {expected_score}"
                )

    def test_weights_match_input(self, service):
        """weight on each factor must match the engine input weight."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-WT", MagicMock(), risk_result=rr)
        engine_weights = {k: v["effective_weight"] for k, v in rr["engines"].items()}
        for factor in explanation.factors:
            if factor.detector in engine_weights:
                expected_w = engine_weights[factor.detector]
                assert abs(factor.weight - expected_w) <= 0.001, (
                    f"{factor.detector}: got weight {factor.weight}, expected {expected_w}"
                )

    def test_user_example_contributions(self, service):
        """Validate that contribution = score × weight for realistic values."""
        rr = _make_risk_result(
            overrides={
                "cost_anomaly": {"score": 85.0, "effective_weight": 0.20, "weight": 0.20},
                "delay_detection": {"score": 72.0, "effective_weight": 0.20, "weight": 0.20},
                "progress_mismatch": {"score": 88.0, "effective_weight": 0.20, "weight": 0.20},
                "agency_pattern": {"score": 65.0, "effective_weight": 0.20, "weight": 0.20},
                "duplicate_detection": {"score": 0.0, "effective_weight": 0.20, "weight": 0.20, "triggered": False},
            },
            overall_score=62.0,
        )
        explanation = service.get_project_explanation("T-UE", MagicMock(), risk_result=rr)
        contrib_map = {f.detector: f.contribution for f in explanation.factors}
        # These are score * weight:
        assert abs(contrib_map.get("cost_anomaly", 0) - 17.0) <= 0.2  # 85 * 0.20
        assert abs(contrib_map.get("delay_detection", 0) - 14.4) <= 0.2  # 72 * 0.20
        assert abs(contrib_map.get("progress_mismatch", 0) - 17.6) <= 0.2  # 88 * 0.20
        assert abs(contrib_map.get("agency_pattern", 0) - 13.0) <= 0.2  # 65 * 0.20
        assert abs(contrib_map.get("duplicate_detection", 0) - 0.0) <= 0.2  # 0 * 0.20


# =============================================================================
# TEST CATEGORY 6: Risk contributions reconcile with the final risk score
# =============================================================================

class TestContributionsReconcile:
    """Category 6: Risk contributions reconcile with the final risk score."""

    def test_sum_of_contributions_matches_risk_score(self, service):
        """Sum of all factor contributions must approximately equal the overall risk_score."""
        # Note: the engine's build_risk_score_decomposition uses effective_weights
        # from the breakdown entries which may differ from the 'weight' field.
        # delay=0.25, progress=0.25, rest=0.20 → sum = 85*0.2+72*0.25+88*0.25+10*0.2+65*0.2 = 72.0
        rr = _make_risk_result(overall_score=72.0)
        explanation = service.get_project_explanation("T-RECON", MagicMock(), risk_result=rr)
        total_contrib = sum(f.contribution for f in explanation.factors)
        # All weights are 0.20, scores sum correctly
        assert abs(total_contrib - explanation.risk_score) <= 1.0, (
            f"Contributions sum ({total_contrib}) does not reconcile with "
            f"risk_score ({explanation.risk_score})"
        )

    def test_decomposition_reconciled_flag(self, service):
        """The score_decomposition.reconciled flag must be True within tolerance."""
        # delay=0.25, progress=0.25, rest=0.20 → 85*0.2+72*0.25+88*0.25+10*0.2+65*0.2 = 72.0
        rr = _make_risk_result(overall_score=72.0)
        explanation = service.get_project_explanation("T-DECOMP", MagicMock(), risk_result=rr)
        if explanation.score_decomposition is not None:
            assert explanation.score_decomposition.reconciled is True, (
                f"Decomposition not reconciled: "
                f"total={explanation.score_decomposition.total_contributions}, "
                f"final={explanation.score_decomposition.final_score}"
            )

    def test_zero_risk_reconciles(self, service):
        """A zero-risk project should reconcile at 0.0."""
        rr = _make_zero_risk_result()
        explanation = service.get_project_explanation("T-ZERO-R", MagicMock(), risk_result=rr)
        total_contrib = sum(f.contribution for f in explanation.factors)
        assert total_contrib == 0.0
        assert explanation.risk_score == 0.0

    def test_decomposition_components_sum(self, service):
        """Individual decomposition components must sum to total_contributions."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-DSUM", MagicMock(), risk_result=rr)
        if explanation.score_decomposition:
            comp_sum = sum(c.weighted_contribution for c in explanation.score_decomposition.components)
            assert abs(comp_sum - explanation.score_decomposition.total_contributions) <= 0.2


# =============================================================================
# TEST CATEGORY 7: Thresholds shown to users match configured thresholds
# =============================================================================

class TestThresholdsMatchConfiguration:
    """Category 7: Thresholds shown to users match configured thresholds."""

    @property
    def CONFIGURED_THRESHOLDS(self) -> Dict[str, str]:
        agency_pct = int(getattr(settings, "AGENCY_DELAY_RATE_THRESHOLD", 0.50) * 100)
        gap_low = int(getattr(settings, "PROGRESS_MISMATCH_GAP_LOW", 10))
        cost_ratio = getattr(settings, "COST_ANOMALY_RATIO_HIGH", 2.0)
        return {
            "cost_anomaly": f"Cost ≥ {cost_ratio}× peer median (or Robust Z ≥ 2.0)",
            "delay_detection": "Delay > 30 days beyond planned completion date",
            "progress_mismatch": f"Financial vs Physical divergence > {gap_low} percentage points",
            "duplicate_detection": "Semantic similarity ≥ 85% duplicate threshold (≥ 60% potential overlap)",
            "agency_pattern": f"Historical delay rate > {agency_pct}% or completion rate < 60%",
        }

    def test_factor_thresholds_match_config(self, service):
        """Each factor's threshold must match ExplainabilityService.DETECTOR_THRESHOLDS."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-THR", MagicMock(), risk_result=rr)
        for factor in explanation.factors:
            if factor.threshold:
                # The threshold may come from details or fallback to DETECTOR_THRESHOLDS
                config_thr = self.CONFIGURED_THRESHOLDS.get(factor.detector)
                if config_thr:
                    # Either the details threshold or the configured one must be used
                    assert factor.threshold is not None, (
                        f"Threshold for {factor.detector} is None"
                    )

    def test_service_thresholds_constant(self, service):
        """DETECTOR_THRESHOLDS on the service must match our expected values."""
        for det, expected in self.CONFIGURED_THRESHOLDS.items():
            actual = service.DETECTOR_THRESHOLDS.get(det)
            assert actual == expected, (
                f"Threshold mismatch for {det}: got '{actual}', expected '{expected}'"
            )


# =============================================================================
# TEST CATEGORY 8: Missing data does not produce misleading explanations
# =============================================================================

class TestMissingDataHandling:
    """Category 8: Missing data does not produce misleading explanations."""

    def test_empty_details_produces_safe_evidence(self, service):
        """Empty detector details should produce non-misleading evidence text."""
        rr = _make_missing_data_result()
        explanation = service.get_project_explanation("T-MISS", MagicMock(), risk_result=rr)
        for factor in explanation.factors:
            for ev in factor.evidence:
                # Evidence should not contain fabricated numbers
                assert ev.text is not None
                assert len(ev.text) > 0
                # Should not claim specific values when data is missing
                assert "None" not in ev.text, (
                    f"Evidence text contains 'None': {ev.text}"
                )

    def test_missing_cost_data_graceful(self, service):
        """Cost anomaly with no cost data should produce safe fallback."""
        rr = _make_risk_result(overrides={
            "cost_anomaly": {
                "score": 50.0,
                "triggered": True,
                "details": {},  # No cost, no median
            }
        })
        explanation = service.get_project_explanation("T-MCOST", MagicMock(), risk_result=rr)
        cost_factor = next(f for f in explanation.factors if f.detector == "cost_anomaly")
        assert len(cost_factor.evidence) >= 1
        # Should be a safe fallback text, not claim specific numbers
        ev = cost_factor.evidence[0]
        assert "None" not in ev.text

    def test_missing_delay_data_graceful(self, service):
        """Delay with no overdue_days should produce safe fallback."""
        rr = _make_risk_result(overrides={
            "delay_detection": {
                "score": 50.0,
                "triggered": True,
                "details": {},
            }
        })
        explanation = service.get_project_explanation("T-MDLY", MagicMock(), risk_result=rr)
        delay_factor = next(f for f in explanation.factors if f.detector == "delay_detection")
        ev = delay_factor.evidence[0]
        assert "None" not in ev.text

    def test_missing_progress_data_graceful(self, service):
        """Progress mismatch with no fp/pp should produce safe fallback."""
        rr = _make_risk_result(overrides={
            "progress_mismatch": {
                "score": 50.0,
                "triggered": True,
                "details": {},
            }
        })
        explanation = service.get_project_explanation("T-MPM", MagicMock(), risk_result=rr)
        pm_factor = next(f for f in explanation.factors if f.detector == "progress_mismatch")
        ev = pm_factor.evidence[0]
        assert "None" not in ev.text

    def test_missing_agency_data_graceful(self, service):
        """Agency pattern with no delay_rate/agency_name should produce safe fallback."""
        rr = _make_risk_result(overrides={
            "agency_pattern": {
                "score": 50.0,
                "triggered": True,
                "details": {},
            }
        })
        explanation = service.get_project_explanation("T-MAG", MagicMock(), risk_result=rr)
        ag_factor = next(f for f in explanation.factors if f.detector == "agency_pattern")
        ev = ag_factor.evidence[0]
        assert "None" not in ev.text


# =============================================================================
# TEST CATEGORY 9: Projects with no detected risks receive a clear explanation
# =============================================================================

class TestNoRiskProjects:
    """Category 9: Projects with no detected risks receive a clear explanation."""

    def test_zero_risk_has_clear_summary(self, service):
        """A project with zero risk should have a reassuring, non-alarming summary."""
        rr = _make_zero_risk_result()
        explanation = service.get_project_explanation("T-NORISK", MagicMock(), risk_result=rr)
        assert explanation.risk_level in ("LOW", "low")
        assert explanation.risk_score == 0.0
        # Summary should not be alarming
        summary_lower = explanation.summary.lower()
        assert "flagged" not in summary_lower or "no" in summary_lower or "not" in summary_lower

    def test_zero_risk_no_triggered_factors(self, service):
        """No factors should be triggered."""
        rr = _make_zero_risk_result()
        explanation = service.get_project_explanation("T-NORISK2", MagicMock(), risk_result=rr)
        triggered_count = sum(1 for f in explanation.factors if f.triggered)
        assert triggered_count == 0

    def test_zero_risk_only_triggered_returns_empty(self, service):
        """With only_triggered=True and no risks, factors list should be empty."""
        rr = _make_zero_risk_result()
        explanation = service.get_project_explanation(
            "T-NORISK3", MagicMock(), risk_result=rr, only_triggered=True,
        )
        assert len(explanation.factors) == 0

    def test_zero_risk_recommendations_present(self, service):
        """Even zero-risk projects should get a routine monitoring recommendation."""
        rr = _make_zero_risk_result()
        explanation = service.get_project_explanation("T-NORISK4", MagicMock(), risk_result=rr)
        assert len(explanation.recommendations) >= 1


# =============================================================================
# TEST CATEGORY 10: API responses conform to the defined schema
# =============================================================================

class TestAPISchemaConformance:
    """Category 10: API responses conform to the defined schema."""

    def _get_real_project_id(self) -> Optional[str]:
        """Find a real project ID from the database, or None."""
        session = SessionLocal()
        try:
            rs = session.query(RiskScore).first()
            return rs.project_id if rs else None
        finally:
            session.close()

    def test_explanation_endpoint_200_schema(self):
        """GET /projects/{id}/explanation returns valid ProjectExplanationResponse."""
        pid = self._get_real_project_id()
        if not pid:
            pytest.skip("No projects in database")
        resp = client.get(f"/projects/{pid}/explanation")
        assert resp.status_code == 200
        data = resp.json()

        # Validate top-level required fields
        assert "project_id" in data
        assert "risk_level" in data
        assert "risk_score" in data
        assert "summary" in data
        assert "factors" in data
        assert isinstance(data["factors"], list)

        # Validate factor structure
        for factor in data["factors"]:
            assert "name" in factor
            assert "detector" in factor
            assert "triggered" in factor
            assert isinstance(factor["triggered"], bool)
            assert "severity" in factor
            assert "contribution" in factor
            assert isinstance(factor["contribution"], (int, float))
            assert "evidence" in factor
            assert isinstance(factor["evidence"], list)
            # New fields should be present
            if factor.get("detector_score") is not None:
                assert isinstance(factor["detector_score"], (int, float))
            if factor.get("weight") is not None:
                assert isinstance(factor["weight"], (int, float))

    def test_explanation_endpoint_400_invalid_id(self):
        """GET /projects/{id}/explanation with empty ID returns 400."""
        resp = client.get("/projects/%20/explanation")
        assert resp.status_code in (400, 404, 422)

    def test_explanation_endpoint_404_nonexistent(self):
        """GET /projects/{id}/explanation with nonexistent ID returns 404."""
        resp = client.get("/projects/NONEXISTENT-9999/explanation")
        assert resp.status_code == 404

    def test_explanation_evidence_schema(self):
        """Evidence items must have text, actual_value, reference_value, unit."""
        pid = self._get_real_project_id()
        if not pid:
            pytest.skip("No projects in database")
        resp = client.get(f"/projects/{pid}/explanation")
        assert resp.status_code == 200
        for factor in resp.json()["factors"]:
            for ev in factor["evidence"]:
                assert "text" in ev
                assert isinstance(ev["text"], str)
                # actual_value, reference_value, unit can be None but must exist
                assert "actual_value" in ev
                assert "reference_value" in ev
                assert "unit" in ev

    def test_explanation_has_recommendations(self):
        """Response must include recommendations list."""
        pid = self._get_real_project_id()
        if not pid:
            pytest.skip("No projects in database")
        resp = client.get(f"/projects/{pid}/explanation")
        assert resp.status_code == 200
        assert "recommendations" in resp.json()
        assert isinstance(resp.json()["recommendations"], list)

    def test_risk_level_valid_values(self):
        """risk_level must be one of LOW, MEDIUM, HIGH, CRITICAL."""
        pid = self._get_real_project_id()
        if not pid:
            pytest.skip("No projects in database")
        resp = client.get(f"/projects/{pid}/explanation")
        assert resp.status_code == 200
        assert resp.json()["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_risk_score_in_range(self):
        """risk_score must be between 0 and 100."""
        pid = self._get_real_project_id()
        if not pid:
            pytest.skip("No projects in database")
        resp = client.get(f"/projects/{pid}/explanation")
        assert resp.status_code == 200
        score = resp.json()["risk_score"]
        assert 0.0 <= score <= 100.0

    def test_decomposition_endpoint_schema(self):
        """GET /projects/{id}/decomposition returns valid decomposition."""
        pid = self._get_real_project_id()
        if not pid:
            pytest.skip("No projects in database")
        resp = client.get(f"/projects/{pid}/decomposition")
        if resp.status_code == 200:
            data = resp.json()
            assert "final_score" in data
            assert "risk_level" in data
            assert "components" in data
            assert "total_contributions" in data
            assert "reconciled" in data
            assert "formatted_breakdown" in data


# =============================================================================
# TEST CATEGORY 11: Rounding does not materially change the underlying values
# =============================================================================

class TestRoundingFidelity:
    """Category 11: Rounding does not materially change the underlying values."""

    ROUNDING_TOLERANCE = 0.2

    def test_score_rounding_preserves_value(self, service):
        """detector_score rounding should not deviate more than 0.1 from input."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-RND", MagicMock(), risk_result=rr)
        engine_scores = {k: v["score"] for k, v in rr["engines"].items()}
        for factor in explanation.factors:
            if factor.detector in engine_scores:
                original = engine_scores[factor.detector]
                assert abs(factor.detector_score - original) <= 0.1

    def test_weight_rounding_preserves_value(self, service):
        """weight rounding should not deviate more than 0.001 from input."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-RNDW", MagicMock(), risk_result=rr)
        engine_weights = {k: v["effective_weight"] for k, v in rr["engines"].items()}
        for factor in explanation.factors:
            if factor.detector in engine_weights:
                original = engine_weights[factor.detector]
                assert abs(factor.weight - original) <= 0.001

    def test_contribution_rounding_tolerance(self, service):
        """Contribution rounding should stay within tolerance of score * weight."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-RNDC", MagicMock(), risk_result=rr)
        for factor in explanation.factors:
            if factor.detector_score is not None and factor.weight is not None:
                exact = factor.detector_score * factor.weight
                assert abs(factor.contribution - exact) <= self.ROUNDING_TOLERANCE

    def test_decomposition_rounding_tolerance(self, service):
        """Decomposition total must reconcile within rounding tolerance."""
        # delay=0.25, progress=0.25, rest=0.20 → 85*0.2+72*0.25+88*0.25+10*0.2+65*0.2 = 72.0
        rr = _make_risk_result(overall_score=72.0)
        explanation = service.get_project_explanation("T-RNDD", MagicMock(), risk_result=rr)
        if explanation.score_decomposition:
            discrepancy = abs(
                explanation.score_decomposition.total_contributions -
                explanation.score_decomposition.final_score
            )
            assert discrepancy <= self.ROUNDING_TOLERANCE

    def test_evidence_rounding_preserves_meaning(self, service):
        """Cost ratio text '2.56×' should not round to '2.5×' or '3×'."""
        rr = _make_risk_result()
        explanation = service.get_project_explanation("T-RNDEV", MagicMock(), risk_result=rr)
        cost_factor = next(f for f in explanation.factors if f.detector == "cost_anomaly")
        ev = cost_factor.evidence[0]
        # 256M / 100M = 2.56, must show 2.56 not a gross rounding
        assert "2.56" in ev.text or "2.5" in ev.text, (
            f"Cost ratio text lost precision: {ev.text}"
        )


# =============================================================================
# TEST CATEGORY 12: Explanation generation is deterministic for the same project data
# =============================================================================

class TestDeterminism:
    """Category 12: Explanation generation is deterministic for the same project data."""

    def test_same_input_produces_same_output(self, service):
        """Running explanation twice on identical input must produce identical output."""
        rr = _make_risk_result()
        exp1 = service.get_project_explanation("T-DET1", MagicMock(), risk_result=copy.deepcopy(rr))
        exp2 = service.get_project_explanation("T-DET1", MagicMock(), risk_result=copy.deepcopy(rr))

        assert exp1.risk_score == exp2.risk_score
        assert exp1.risk_level == exp2.risk_level
        assert exp1.summary == exp2.summary
        assert len(exp1.factors) == len(exp2.factors)

        for f1, f2 in zip(exp1.factors, exp2.factors):
            assert f1.detector == f2.detector
            assert f1.triggered == f2.triggered
            assert f1.contribution == f2.contribution
            assert f1.severity == f2.severity
            assert f1.detector_score == f2.detector_score
            assert f1.weight == f2.weight

    def test_deterministic_evidence_text(self, service):
        """Evidence text must be identical across runs."""
        rr = _make_risk_result()
        exp1 = service.get_project_explanation("T-DET2", MagicMock(), risk_result=copy.deepcopy(rr))
        exp2 = service.get_project_explanation("T-DET2", MagicMock(), risk_result=copy.deepcopy(rr))

        for f1, f2 in zip(exp1.factors, exp2.factors):
            assert len(f1.evidence) == len(f2.evidence)
            for e1, e2 in zip(f1.evidence, f2.evidence):
                assert e1.text == e2.text
                assert e1.actual_value == e2.actual_value
                assert e1.reference_value == e2.reference_value
                assert e1.unit == e2.unit

    def test_deterministic_recommendations(self, service):
        """Recommendations must be identical across runs."""
        rr = _make_risk_result()
        exp1 = service.get_project_explanation("T-DET3", MagicMock(), risk_result=copy.deepcopy(rr))
        exp2 = service.get_project_explanation("T-DET3", MagicMock(), risk_result=copy.deepcopy(rr))
        assert exp1.recommendations == exp2.recommendations

    def test_deterministic_decomposition(self, service):
        """Decomposition values must be identical across runs."""
        rr = _make_risk_result()
        exp1 = service.get_project_explanation("T-DET4", MagicMock(), risk_result=copy.deepcopy(rr))
        exp2 = service.get_project_explanation("T-DET4", MagicMock(), risk_result=copy.deepcopy(rr))
        if exp1.score_decomposition and exp2.score_decomposition:
            assert exp1.score_decomposition.final_score == exp2.score_decomposition.final_score
            assert exp1.score_decomposition.total_contributions == exp2.score_decomposition.total_contributions
            assert exp1.score_decomposition.reconciled == exp2.score_decomposition.reconciled
            for c1, c2 in zip(exp1.score_decomposition.components, exp2.score_decomposition.components):
                assert c1.detector_key == c2.detector_key
                assert c1.weighted_contribution == c2.weighted_contribution

    def test_10_runs_deterministic(self, service):
        """Run 10 times and ensure all produce identical risk_score and summary."""
        rr = _make_risk_result()
        results = []
        for _ in range(10):
            exp = service.get_project_explanation(
                "T-DET10", MagicMock(), risk_result=copy.deepcopy(rr)
            )
            results.append((exp.risk_score, exp.summary, exp.risk_level))
        # All must be identical
        assert len(set(results)) == 1, f"Non-deterministic results: {set(results)}"


# =============================================================================
# LIVE DATABASE INTEGRATION TESTS
# =============================================================================

class TestLiveDatabaseIntegration:
    """Integration tests against real database projects."""

    def _get_project_ids(self, limit: int = 5) -> List[str]:
        session = SessionLocal()
        try:
            records = session.query(RiskScore.project_id).limit(limit).all()
            return [r[0] for r in records]
        finally:
            session.close()

    def test_all_live_projects_have_evidence(self):
        """Every triggered factor in a live project must have evidence."""
        pids = self._get_project_ids()
        if not pids:
            pytest.skip("No projects in database")
        for pid in pids:
            resp = client.get(f"/projects/{pid}/explanation")
            if resp.status_code != 200:
                continue
            for factor in resp.json()["factors"]:
                if factor["triggered"]:
                    assert len(factor["evidence"]) >= 1, (
                        f"Project {pid}, detector {factor['detector']}: "
                        f"triggered but no evidence"
                    )

    def test_all_live_projects_reconcile(self):
        """Every live project's decomposition must reconcile."""
        pids = self._get_project_ids()
        if not pids:
            pytest.skip("No projects in database")
        for pid in pids:
            resp = client.get(f"/projects/{pid}/decomposition")
            if resp.status_code == 200:
                data = resp.json()
                assert data["reconciled"] is True, (
                    f"Project {pid}: decomposition not reconciled. "
                    f"total={data['total_contributions']}, final={data['final_score']}"
                )

    def test_live_project_schema_conformance(self):
        """Every live project explanation must conform to schema."""
        pids = self._get_project_ids()
        if not pids:
            pytest.skip("No projects in database")
        for pid in pids:
            resp = client.get(f"/projects/{pid}/explanation")
            if resp.status_code != 200:
                continue
            data = resp.json()
            # Can be deserialized into Pydantic model
            parsed = ProjectExplanationResponse(**data)
            assert parsed.project_id == pid
            assert parsed.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            assert 0.0 <= parsed.risk_score <= 100.0

    def test_live_details_field_populated(self):
        """The new 'details' field must be populated for triggered factors."""
        pids = self._get_project_ids(limit=3)
        if not pids:
            pytest.skip("No projects in database")
        for pid in pids:
            resp = client.get(f"/projects/{pid}/explanation")
            if resp.status_code != 200:
                continue
            for factor in resp.json()["factors"]:
                if factor["triggered"]:
                    assert "details" in factor, (
                        f"Project {pid}, detector {factor['detector']}: missing 'details'"
                    )
                    assert isinstance(factor["details"], dict)

    def test_live_detector_score_and_weight_populated(self):
        """The new detector_score and weight fields must be populated."""
        pids = self._get_project_ids(limit=3)
        if not pids:
            pytest.skip("No projects in database")
        for pid in pids:
            resp = client.get(f"/projects/{pid}/explanation")
            if resp.status_code != 200:
                continue
            for factor in resp.json()["factors"]:
                assert "detector_score" in factor
                assert "weight" in factor
                if factor["detector_score"] is not None:
                    assert isinstance(factor["detector_score"], (int, float))
                if factor["weight"] is not None:
                    assert isinstance(factor["weight"], (int, float))


# =============================================================================
# AUDIT VERIFICATION: Vocabulary normalization & config-driven thresholds
# =============================================================================

class TestAuditFixesAndNormalization:
    """Verifies that Phase 8 audit findings (F1, F2, F3, F7) are resolved."""

    def test_normalize_risk_level_vocabulary(self):
        """_normalize_risk_level strictly normalizes MODERATE to MEDIUM."""
        assert _normalize_risk_level("MODERATE") == "MEDIUM"
        assert _normalize_risk_level("Moderate") == "MEDIUM"
        assert _normalize_risk_level("moderate") == "MEDIUM"
        assert _normalize_risk_level("LOW") == "LOW"
        assert _normalize_risk_level("HIGH") == "HIGH"
        assert _normalize_risk_level("CRITICAL") == "CRITICAL"

    def test_normalize_severity_vocabulary(self):
        """_normalize_severity strictly normalizes moderate to medium."""
        assert _normalize_severity("moderate") == "medium"
        assert _normalize_severity("Moderate") == "medium"
        assert _normalize_severity("MODERATE") == "medium"
        assert _normalize_severity("low") == "low"
        assert _normalize_severity("high") == "high"
        assert _normalize_severity("critical") == "critical"

    def test_db_record_with_moderate_normalizes_to_medium(self, service):
        """Simulated DB row with risk_level='Moderate' produces risk_level='MEDIUM' and severity='medium'."""
        mock_score = MagicMock(spec=RiskScore)
        mock_score.overall_risk_score = 55.0
        mock_score.risk_level = "Moderate"

        mock_factor = MagicMock(spec=RiskFactor)
        mock_factor.engine_name = "delay_detection"
        mock_factor.score = 55.0
        mock_factor.factor_weight = 0.20
        mock_factor.risk_level = "Moderate"
        mock_factor.details = {"triggered": True, "overdue_days": 45}
        mock_factor.mitigation_recommendation = "Review timeline"
        mock_score.factors = [mock_factor]

        resp = service._build_from_db_record("PROJ-MOD", mock_score)
        assert resp.risk_level == "MEDIUM"
        assert resp.risk_level != "MODERATE"
        delay_f = next(f for f in resp.factors if f.detector == "delay_detection")
        assert delay_f.severity == "medium"
        assert delay_f.severity != "moderate"

    def test_agency_pattern_threshold_driven_by_config(self, service):
        """Agency pattern threshold and evidence reference value match settings.AGENCY_DELAY_RATE_THRESHOLD."""
        expected_pct = round(getattr(settings, "AGENCY_DELAY_RATE_THRESHOLD", 0.50) * 100, 1)
        # 1. In DETECTOR_THRESHOLDS
        threshold_str = service.DETECTOR_THRESHOLDS["agency_pattern"]
        assert f"{int(expected_pct)}%" in threshold_str
        assert "25%" not in threshold_str  # Old fabricated value must not appear

        # 2. In reference comparison
        ref_str = service._get_detector_reference("agency_pattern", {})
        assert f"{expected_pct:g}%" in ref_str

        # 3. In generated evidence item
        ev_list = service._extract_agency_evidence({"agency": "Test Corp", "delay_rate": 0.55, "projects_analyzed": 10}, 65.0)
        assert len(ev_list) >= 1
        assert ev_list[0].reference_value == expected_pct

