"""
backend/tests/test_cost_anomaly_engine.py
=============================================================================
Comprehensive Test Suite for Engine 1: Cost Anomaly Detection.
=============================================================================

Tests:
1. Normal project (cost aligned with peer median)
2. Unusually expensive project (statistical outlier)
3. Legitimately expensive project (high sanctioned, within budget -> dampened score)
4. Unusually cheap project (under 15% of peer median -> low cost anomaly)
5. Missing cost / zero expenditure
6. Small peer group (< min_peers -> neutral score 0, low confidence)
7. Different categories (separate peer baselines per sector)
8. Exact schema conformance (EngineResult keys, types, bounds)
9. Live database project evaluation
"""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.config import settings
from app.database import SessionLocal
from app.models.project import Project, Financial, ProjectFeature
from app.schemas.risk_engine import RiskLevel, EngineResult
from app.services.risk.cost_anomaly_engine import CostAnomalyEngine


@pytest.fixture
def db_session():
    """Provides an active database session against PostgreSQL."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def cost_engine():
    """CostAnomalyEngine instance with standard min_peers=3."""
    return CostAnomalyEngine(min_peers=3)


# =============================================================================
# 1. Output Schema & Conformance Tests
# =============================================================================

class TestCostAnomalyEngineSchema:

    def test_schema_keys_and_structure(self, db_session, cost_engine):
        """EngineResult must output the exact requested JSON keys and structure."""
        result = cost_engine.evaluate("MPLADS-2024-0001", db=db_session)
        assert isinstance(result, EngineResult)
        d = result.to_dict()

        expected_keys = {"engine", "score", "risk_level", "reason", "details", "confidence"}
        assert set(d.keys()) == expected_keys
        assert d["engine"] == "cost_anomaly"
        assert 0 <= d["score"] <= 100
        assert d["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert isinstance(d["reason"], str) and len(d["reason"]) > 0
        assert isinstance(d["details"], dict)
        assert 0.0 <= d["confidence"] <= 1.0

    def test_evidence_fields_present_in_details(self, db_session, cost_engine):
        """Details must contain all mandatory evidence metrics."""
        result = cost_engine.evaluate("MPLADS-2024-0001", db=db_session)
        details = result.details

        # Mandatory evidence fields specified in prompt
        assert "project_expenditure" in details
        assert "peer_median" in details
        assert "deviation_percentage" in details
        assert "percentile" in details
        assert "peer_group_size" in details

        # Additional robust metrics
        assert "peer_q1" in details
        assert "peer_q3" in details
        assert "peer_iqr" in details
        assert "robust_z_score" in details
        assert "anomaly_type" in details


# =============================================================================
# 2. Statistical Anomaly Scenarios (Mocked Peer Distributions)
# =============================================================================

class TestCostAnomalyScenarios:

    def test_normal_project(self, cost_engine):
        """
        Normal project: Expenditure is close to peer median.
        Should result in low risk score (< 30) and LOW risk level.
        """
        # Peers: 10 projects with median 1,500,000
        peer_costs = [
            1200000.0, 1300000.0, 1400000.0, 1450000.0, 1500000.0,
            1550000.0, 1600000.0, 1650000.0, 1700000.0, 1800000.0
        ]
        target_cost = 1520000.0  # Just 1.3% above median

        mock_project = MagicMock(spec=Project)
        mock_project.project_id = "TEST-NORM-001"
        mock_project.sector = "Health"
        mock_project.state_id = 1
        mock_project.current_status = "Ongoing"

        mock_financial = MagicMock(spec=Financial)
        mock_financial.expenditure_amount = target_cost
        mock_financial.sanctioned_amount = 1600000.0
        mock_financial.released_amount = 1600000.0
        mock_financial.cost_overrun_pct = 0.0

        mock_db = MagicMock()
        mock_db.execute.return_value.first.return_value = (mock_project, mock_financial, None)

        with patch.object(cost_engine, "_get_peer_costs", return_value=(peer_costs, "sector_and_state")):
            result = cost_engine.evaluate("TEST-NORM-001", db=mock_db)

        assert result.score < 30
        assert result.risk_level == RiskLevel.LOW.value
        assert result.details["anomaly_type"] == "NORMAL"
        assert abs(result.details["deviation_percentage"]) < 10.0
        assert "normal" in result.reason.lower()

    def test_unusually_expensive_project(self, cost_engine):
        """
        Unusually expensive project: Expenditure is 3.5x peer median with cost overrun.
        Should result in high/critical risk score (>= 60) and HIGH/CRITICAL risk level.
        """
        peer_costs = [
            1000000.0, 1100000.0, 1200000.0, 1250000.0, 1300000.0,
            1350000.0, 1400000.0, 1500000.0
        ]
        # Peer median = 1,275,000
        target_cost = 4500000.0  # 3.5x median

        mock_project = MagicMock(spec=Project)
        mock_project.project_id = "TEST-EXP-001"
        mock_project.sector = "Sanitation"
        mock_project.state_id = 2
        mock_project.current_status = "Completed"

        mock_financial = MagicMock(spec=Financial)
        mock_financial.expenditure_amount = target_cost
        mock_financial.sanctioned_amount = 3000000.0  # Exceeded sanctioned budget!
        mock_financial.released_amount = 4500000.0
        mock_financial.cost_overrun_pct = 50.0  # 50% overrun

        mock_db = MagicMock()
        mock_db.execute.return_value.first.return_value = (mock_project, mock_financial, None)

        with patch.object(cost_engine, "_get_peer_costs", return_value=(peer_costs, "sector_and_state")):
            result = cost_engine.evaluate("TEST-EXP-001", db=mock_db)

        assert result.score >= 60
        assert result.risk_level in {RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}
        assert result.details["robust_z_score"] > 3.0
        assert result.details["percentile"] == 100.0
        assert result.details["cost_overrun_pct"] == 50.0
        assert result.details["anomaly_type"] in {"HIGH_COST_OUTLIER", "COST_OVERRUN_ANOMALY"}

    def test_legitimately_expensive_project_not_misclassified(self, cost_engine):
        """
        Legitimately expensive project: High budget compared to general peers,
        BUT officially sanctioned for that amount with ZERO cost overrun.
        Should NOT be classified as CRITICAL / fraudulent (dampened score <= 50).
        """
        peer_costs = [
            1000000.0, 1100000.0, 1200000.0, 1250000.0, 1300000.0,
            1350000.0, 1400000.0, 1500000.0
        ]
        # Peer median = 1,275,000
        target_cost = 3200000.0  # 2.5x median

        mock_project = MagicMock(spec=Project)
        mock_project.project_id = "TEST-LEGIT-001"
        mock_project.sector = "Roads & Bridges"
        mock_project.state_id = 3
        mock_project.current_status = "Completed"

        mock_financial = MagicMock(spec=Financial)
        mock_financial.expenditure_amount = target_cost
        mock_financial.sanctioned_amount = 3500000.0  # Approved 35 Lakhs! Spent within sanction
        mock_financial.released_amount = 3500000.0
        mock_financial.cost_overrun_pct = 0.0  # Zero overrun

        mock_db = MagicMock()
        mock_db.execute.return_value.first.return_value = (mock_project, mock_financial, None)

        with patch.object(cost_engine, "_get_peer_costs", return_value=(peer_costs, "sector_and_state")):
            result = cost_engine.evaluate("TEST-LEGIT-001", db=mock_db)

        # Dampener ensures score is capped at or below 50 (MEDIUM or LOW), never HIGH/CRITICAL
        assert result.score <= 50
        assert result.risk_level in {RiskLevel.LOW.value, RiskLevel.MEDIUM.value}
        assert result.details["anomaly_type"] == "LEGITIMATE_HIGH_BUDGET"
        assert "legitimate" in result.reason.lower() or "within" in result.reason.lower()

    def test_unusually_cheap_project(self, cost_engine):
        """
        Unusually cheap project: Expenditure is < 10% of peer median for a completed work.
        Should flag LOW_COST_ANOMALY with a moderate risk score (30–50).
        """
        peer_costs = [
            2000000.0, 2200000.0, 2400000.0, 2500000.0, 2600000.0,
            2700000.0, 2800000.0, 3000000.0
        ]
        # Peer median = 2,550,000
        target_cost = 100000.0  # Only 1 Lakh (3.9% of median) for a major construction work

        mock_project = MagicMock(spec=Project)
        mock_project.project_id = "TEST-CHEAP-001"
        mock_project.sector = "Community Infrastructure"
        mock_project.state_id = 4
        mock_project.current_status = "Completed"

        mock_financial = MagicMock(spec=Financial)
        mock_financial.expenditure_amount = target_cost
        mock_financial.sanctioned_amount = 2500000.0
        mock_financial.released_amount = 500000.0
        mock_financial.cost_overrun_pct = 0.0

        mock_db = MagicMock()
        mock_db.execute.return_value.first.return_value = (mock_project, mock_financial, None)

        with patch.object(cost_engine, "_get_peer_costs", return_value=(peer_costs, "sector_and_state")):
            result = cost_engine.evaluate("TEST-CHEAP-001", db=mock_db)

        assert 30 <= result.score <= 55
        assert result.details["anomaly_type"] == "LOW_COST_ANOMALY"
        assert result.details["deviation_percentage"] < -85.0
        assert "unusually low" in result.reason.lower()

    def test_missing_cost(self, cost_engine):
        """
        Missing cost: Project has 0 or NULL expenditure and sanctioned amounts.
        Should return score 0, LOW risk level, and 0.0 confidence.
        """
        mock_project = MagicMock(spec=Project)
        mock_project.project_id = "TEST-NO-COST"
        mock_project.sector = "Drinking Water"
        mock_project.state_id = 5
        mock_project.current_status = "Recommended"

        mock_financial = MagicMock(spec=Financial)
        mock_financial.expenditure_amount = 0.0
        mock_financial.sanctioned_amount = 0.0
        mock_financial.released_amount = 0.0
        mock_financial.cost_overrun_pct = 0.0

        mock_db = MagicMock()
        mock_db.execute.return_value.first.return_value = (mock_project, mock_financial, None)

        result = cost_engine.evaluate("TEST-NO-COST", db=mock_db)

        assert result.score == 0
        assert result.risk_level == RiskLevel.LOW.value
        assert result.confidence == 0.0
        assert result.details["missing_cost"] is True
        assert result.details["anomaly_type"] == "MISSING_COST"

    def test_small_peer_group(self, cost_engine):
        """
        Small peer group: Fewer than MIN_PEERS (3) peers exist for the category.
        Should return score 0, low confidence (0.30), and small_peer_group flag.
        """
        peer_costs = [1500000.0]  # Only 1 peer found (< 3)
        target_cost = 1600000.0

        mock_project = MagicMock(spec=Project)
        mock_project.project_id = "TEST-SMALL-PEER"
        mock_project.sector = "RareSector"
        mock_project.state_id = 6
        mock_project.current_status = "Ongoing"

        mock_financial = MagicMock(spec=Financial)
        mock_financial.expenditure_amount = target_cost
        mock_financial.sanctioned_amount = 1600000.0
        mock_financial.released_amount = 1600000.0
        mock_financial.cost_overrun_pct = 0.0

        mock_db = MagicMock()
        mock_db.execute.return_value.first.return_value = (mock_project, mock_financial, None)

        with patch.object(cost_engine, "_get_peer_costs", return_value=(peer_costs, "insufficient_peers")):
            result = cost_engine.evaluate("TEST-SMALL-PEER", db=mock_db)

        assert result.score == 0
        assert result.confidence == 0.30
        assert result.details["small_peer_group"] is True
        assert result.details["peer_group_size"] == 1
        assert "insufficient peer data" in result.reason.lower()

    def test_different_categories_have_independent_baselines(self, cost_engine):
        """
        Different categories: An identical expenditure amount (e.g. 5,000,000)
        can be normal for one sector (Roads) but an extreme outlier for another (Sanitation).
        """
        identical_cost = 5000000.0

        # High-cost sector (Roads & Bridges) where median is 6,000,000
        roads_peers = [4000000.0, 5000000.0, 6000000.0, 7000000.0, 8000000.0]
        # Low-cost sector (Sanitation) where median is 500,000
        sanitation_peers = [300000.0, 400000.0, 500000.0, 600000.0, 700000.0]

        mock_roads = MagicMock(spec=Project)
        mock_roads.project_id = "TEST-ROADS"
        mock_roads.sector = "Roads & Bridges"
        mock_roads.state_id = 1
        mock_roads.current_status = "Ongoing"

        mock_sanitation = MagicMock(spec=Project)
        mock_sanitation.project_id = "TEST-SAN"
        mock_sanitation.sector = "Sanitation"
        mock_sanitation.state_id = 1
        mock_sanitation.current_status = "Ongoing"

        mock_financial = MagicMock(spec=Financial)
        mock_financial.expenditure_amount = identical_cost
        mock_financial.sanctioned_amount = identical_cost
        mock_financial.released_amount = identical_cost
        mock_financial.cost_overrun_pct = 0.0

        mock_db = MagicMock()

        # Evaluate Roads
        mock_db.execute.return_value.first.return_value = (mock_roads, mock_financial, None)
        with patch.object(cost_engine, "_get_peer_costs", return_value=(roads_peers, "sector_and_state")):
            res_roads = cost_engine.evaluate("TEST-ROADS", db=mock_db)

        # Evaluate Sanitation
        mock_db.execute.return_value.first.return_value = (mock_sanitation, mock_financial, None)
        with patch.object(cost_engine, "_get_peer_costs", return_value=(sanitation_peers, "sector_and_state")):
            res_san = cost_engine.evaluate("TEST-SAN", db=mock_db)

        # Roads: ₹50L is BELOW the ₹60L median -> LOW risk
        assert res_roads.score < 30
        assert res_roads.risk_level == RiskLevel.LOW.value

        # Sanitation: ₹50L is 10x the ₹5L median -> Severe Anomaly (HIGH / CRITICAL)
        assert res_san.score >= 60
        assert res_san.risk_level in {RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}
        assert res_san.score > res_roads.score


# =============================================================================
# 3. Live Database Evaluation Tests
# =============================================================================

class TestCostAnomalyLiveDatabase:

    def test_evaluate_live_database_project(self, db_session, cost_engine):
        """Evaluates cost anomaly engine on actual PostgreSQL project."""
        result = cost_engine.evaluate("MPLADS-2024-0001", db=db_session)
        assert result.engine == "cost_anomaly"
        assert isinstance(result.score, int)
        assert 0 <= result.score <= 100
        assert result.risk_level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert result.confidence > 0.0
        assert "project_expenditure" in result.details
        assert "peer_median" in result.details

    def test_evaluate_nonexistent_project(self, db_session, cost_engine):
        """Non-existent project should return clean not_found response with 0 score."""
        result = cost_engine.evaluate("NONEXISTENT-PROJECT-9999", db=db_session)
        assert result.engine == "cost_anomaly"
        assert result.score == 0
        assert result.risk_level == RiskLevel.LOW.value
        assert result.confidence == 0.0
        assert "not found" in result.reason.lower()


# =============================================================================
# 4. Feature Extraction, Hierarchy & Resilience Tests
# =============================================================================

class TestCostAnomalyFeaturesAndHierarchy:

    def test_district_level_peer_matching(self, cost_engine):
        """Verifies that district-level peers are prioritized when sufficient peers exist."""
        mock_db = MagicMock()
        mock_project = MagicMock(spec=Project)
        mock_project.project_id = "TEST-DIST-001"
        mock_project.sector = "Education"
        mock_project.state_id = 5
        mock_project.district_name = "Varanasi"
        mock_project.current_status = "Ongoing"

        mock_financial = MagicMock(spec=Financial)
        mock_financial.expenditure_amount = 1000000.0
        mock_financial.sanctioned_amount = 1000000.0
        mock_financial.released_amount = 1000000.0
        mock_financial.cost_overrun_pct = 0.0

        # Simulate 4 district peers found
        district_peers = [950000.0, 1000000.0, 1050000.0, 1100000.0]
        with patch.object(cost_engine, "_get_peer_costs", return_value=(district_peers, "sector_and_district")) as mock_get_peers:
            mock_db.execute.return_value.first.return_value = (mock_project, mock_financial, None)
            res = cost_engine.evaluate("TEST-DIST-001", db=mock_db)

            assert res.details["peer_scope"] == "sector_and_district"
            assert res.details["district_name"] == "Varanasi"
            assert res.confidence >= 0.70  # Higher confidence with district peer proximity

    def test_duration_and_cost_per_day_calculation(self, cost_engine):
        """Verifies duration extraction from ProjectFeature and daily cost derivation."""
        mock_db = MagicMock()
        mock_project = MagicMock(spec=Project)
        mock_project.project_id = "TEST-DUR-001"
        mock_project.sector = "Health"
        mock_project.state_id = 1
        mock_project.district_name = "Patna"
        mock_project.current_status = "Ongoing"

        mock_financial = MagicMock(spec=Financial)
        mock_financial.expenditure_amount = 1800000.0
        mock_financial.sanctioned_amount = 2000000.0
        mock_financial.released_amount = 1800000.0
        mock_financial.cost_overrun_pct = 0.0

        mock_features = MagicMock(spec=ProjectFeature)
        mock_features.project_duration_days = 365
        mock_features.cost_deviation = -200000.0
        mock_features.utilization_ratio = 1.0
        mock_features.cost_relative_to_category = 1.1
        mock_features.cost_category_zscore = 0.2

        peers = [1500000.0, 1600000.0, 1700000.0, 1800000.0, 1900000.0]
        with patch.object(cost_engine, "_get_peer_costs", return_value=(peers, "sector_and_state")):
            mock_db.execute.return_value.first.return_value = (mock_project, mock_financial, mock_features)
            res = cost_engine.evaluate("TEST-DUR-001", db=mock_db)

            assert res.details["project_duration_days"] == 365
            # Cost per day: 1,800,000 / 365 ~ 4931.51
            assert res.details["cost_per_day"] == 4931.51
            assert res.details["utilization_ratio"] == 1.0
            assert res.details["cost_deviation"] == -200000.0

    def test_missing_optional_financial_and_feature_records(self, cost_engine):
        """Engine should not crash if financial or features are None, or fields are missing."""
        mock_db = MagicMock()
        mock_project = MagicMock(spec=Project)
        mock_project.project_id = "TEST-NONE-RECS"
        mock_project.sector = "Water"
        mock_project.state_id = 2
        mock_project.district_name = None
        mock_project.current_status = "Proposed"

        # Both financial and features are None
        mock_db.execute.return_value.first.return_value = (mock_project, None, None)
        res = cost_engine.evaluate("TEST-NONE-RECS", db=mock_db)

        assert res.score == 0
        assert res.risk_level == RiskLevel.LOW.value
        assert res.details["missing_cost"] is True
        assert res.details["project_expenditure"] == 0.0
        assert res.details["peer_group_size"] == 0

