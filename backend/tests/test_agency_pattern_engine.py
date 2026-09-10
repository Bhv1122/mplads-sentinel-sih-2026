"""
backend/tests/test_agency_pattern_engine.py
=============================================================================
Comprehensive Test Suite for Engine 5: Agency Pattern Detection.
=============================================================================

Tests:
1. Exact Schema & Return Contract (engine, score, risk_level, reason, details, confidence)
2. Mandatory Details Fields (projects_analyzed, delay_rate, cost_anomaly_rate, mismatch_rate)
3. Extended Metrics Fields (average_cost, median_cost, average_utilization, completion_rate, high_risk_frequency)
4. Normal Agency (low delays, low anomalies -> score < 30, LOW risk)
5. High-Delay Agency (frequent delays -> elevated score, delay explanation)
6. High-Anomaly Agency (frequent cost overruns & progress mismatches -> elevated score)
7. Insufficient History (projects < min_projects -> score <= 15, low confidence)
8. Missing Agency (null or blank agency -> score=0, confidence=0.0)
9. Candidate Agency Entity Resolution Fallbacks (implementing_agency -> executing_agency -> department, etc.)
10. Non-accusatory Governance Tone (no accusations of fraud or corruption)
11. Configurable Thresholds & Context Override
12. Live Database Evaluation against real MPLADS projects
"""

import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.models.project import Project, Financial, Progress
from app.schemas.risk_engine import RiskLevel, EngineResult
from app.services.risk.agency_pattern_engine import AgencyPatternEngine


@pytest.fixture
def db_session():
    """Provides an active database session against PostgreSQL."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def agency_engine():
    """AgencyPatternEngine instance with standard thresholds."""
    return AgencyPatternEngine(
        min_projects=3,
        delay_rate_threshold=0.40,
        cost_anomaly_rate_threshold=0.25,
        mismatch_rate_threshold=0.30,
    )


# =============================================================================
# Mock Helpers
# =============================================================================

def create_mock_project(
    project_id: str,
    agency: str = "Test Agency",
    status: str = "In Progress",
    expected_comp: date = None,
    actual_comp: date = None,
    **kwargs
) -> Project:
    p = MagicMock(spec=Project)
    p.project_id = project_id
    p.implementing_agency = agency
    p.executing_agency = kwargs.get("executing_agency", None)
    p.department = kwargs.get("department", None)
    p.contractor = kwargs.get("contractor", None)
    p.authority = kwargs.get("authority", None)
    p.current_status = status
    p.expected_completion_date = expected_comp or (date.today() + timedelta(days=60))
    p.actual_completion_date = actual_comp
    return p


def create_mock_financial(
    project_id: str,
    sanctioned: float = 1000000.0,
    released: float = 1000000.0,
    expenditure: float = 500000.0,
    overrun_pct: float = 0.0,
) -> Financial:
    f = MagicMock(spec=Financial)
    f.project_id = project_id
    f.sanctioned_amount = Decimal(str(sanctioned)) if sanctioned is not None else None
    f.released_amount = Decimal(str(released)) if released is not None else None
    f.expenditure_amount = Decimal(str(expenditure)) if expenditure is not None else None
    f.cost_overrun_pct = Decimal(str(overrun_pct)) if overrun_pct is not None else Decimal("0.0")
    return f


def create_mock_progress(
    project_id: str,
    physical_pct: float = 50.0,
    financial_pct: float = 50.0,
) -> Progress:
    pr = MagicMock(spec=Progress)
    pr.project_id = project_id
    pr.physical_progress_pct = Decimal(str(physical_pct)) if physical_pct is not None else None
    pr.financial_progress_pct = Decimal(str(financial_pct)) if financial_pct is not None else None
    return pr


# =============================================================================
# 1. Output Schema & Conformance Tests
# =============================================================================

class TestAgencyPatternSchema:

    def test_schema_keys_and_structure(self, db_session, agency_engine):
        """EngineResult must output the exact requested JSON keys and structure."""
        result = agency_engine.evaluate("MPLADS-2024-0001", db=db_session)
        assert isinstance(result, EngineResult)
        d = result.to_dict()

        expected_keys = {"engine", "score", "risk_level", "reason", "details", "confidence"}
        assert set(d.keys()) == expected_keys
        assert d["engine"] == "agency_pattern"
        assert 0 <= d["score"] <= 100
        assert d["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert isinstance(d["reason"], str) and len(d["reason"]) > 0
        assert isinstance(d["details"], dict)
        assert 0.0 <= d["confidence"] <= 1.0

    def test_mandatory_details_fields(self, db_session, agency_engine):
        """Details must contain all 4 mandatory keys specified in user prompt."""
        result = agency_engine.evaluate("MPLADS-2024-0001", db=db_session)
        details = result.details

        mandatory_keys = [
            "projects_analyzed",
            "delay_rate",
            "cost_anomaly_rate",
            "mismatch_rate",
        ]
        for key in mandatory_keys:
            assert key in details, f"Missing mandatory detail field: {key}"
            assert isinstance(details[key], (int, float))

    def test_extended_metrics_fields(self, db_session, agency_engine):
        """Details must also include the requested extended institutional statistics."""
        result = agency_engine.evaluate("MPLADS-2024-0001", db=db_session)
        details = result.details

        extended_keys = [
            "average_cost",
            "median_cost",
            "average_utilization",
            "completion_rate",
            "high_risk_frequency",
        ]
        for key in extended_keys:
            assert key in details, f"Missing extended metric: {key}"


# =============================================================================
# 2. Normal Agency (Healthy Track Record)
# =============================================================================

class TestNormalAgency:

    def test_normal_agency_portfolio(self, agency_engine):
        """
        An agency with 5 on-time, on-budget, matching-progress projects
        should yield LOW risk score (< 30) and high confidence.
        """
        mock_db = MagicMock()
        target_project = create_mock_project("P-01", agency="Reliable Corp")

        # Mock target project query
        mock_db.execute.return_value.scalar_one_or_none.return_value = target_project

        # Portfolio of 5 healthy projects
        portfolio = [
            create_mock_project(f"P-0{i}", agency="Reliable Corp", status="Completed",
                                expected_comp=date(2025, 1, 1), actual_comp=date(2025, 1, 1))
            for i in range(1, 6)
        ]

        # Financials and progress: all normal
        fin_list = [create_mock_financial(f"P-0{i}", 1000000, 1000000, 950000, 0.0) for i in range(1, 6)]
        prog_list = [create_mock_progress(f"P-0{i}", 100.0, 95.0) for i in range(1, 6)]

        # Setup mock db queries
        # 1st execute: Project scalar_one_or_none (target)
        # 2nd execute: Portfolio scalars().all()
        # 3rd execute: Financials scalars().all()
        # 4th execute: Progress scalars().all()
        mock_query_portfolio = MagicMock()
        mock_query_portfolio.scalars.return_value.all.return_value = portfolio

        mock_query_fin = MagicMock()
        mock_query_fin.scalars.return_value.all.return_value = fin_list

        mock_query_prog = MagicMock()
        mock_query_prog.scalars.return_value.all.return_value = prog_list

        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=target_project)),
            mock_query_portfolio,
            mock_query_fin,
            mock_query_prog,
        ]

        result = agency_engine.evaluate("P-01", db=mock_db)

        assert result.score < 30
        assert result.risk_level == RiskLevel.LOW
        assert result.details["projects_analyzed"] == 5
        assert result.details["delay_rate"] == 0.0
        assert result.details["cost_anomaly_rate"] == 0.0
        assert result.details["mismatch_rate"] == 0.0
        assert result.details["completion_rate"] == 100.0
        assert result.confidence >= 0.85
        assert "normal governance parameters" in result.reason or "consistent historical" in result.reason


# =============================================================================
# 3. High-Delay Agency (Chronic Delays)
# =============================================================================

class TestHighDelayAgency:

    def test_high_delay_agency_portfolio(self, agency_engine):
        """
        An agency where 4 out of 5 projects are overdue by > 30 days
        should yield elevated risk score (>= 60) and cite delay rate.
        """
        mock_db = MagicMock()
        target_project = create_mock_project("P-01", agency="Lagging Agency")

        today = date.today()
        # 4 delayed projects (expected completion was 120 days ago, not completed)
        portfolio = [
            create_mock_project("P-01", agency="Lagging Agency", status="In Progress",
                                expected_comp=today - timedelta(days=120)),
            create_mock_project("P-02", agency="Lagging Agency", status="In Progress",
                                expected_comp=today - timedelta(days=90)),
            create_mock_project("P-03", agency="Lagging Agency", status="In Progress",
                                expected_comp=today - timedelta(days=60)),
            create_mock_project("P-04", agency="Lagging Agency", status="Completed",
                                expected_comp=today - timedelta(days=200),
                                actual_comp=today - timedelta(days=50)),  # 150 days late
            create_mock_project("P-05", agency="Lagging Agency", status="Completed",
                                expected_comp=today - timedelta(days=10),
                                actual_comp=today - timedelta(days=10)),  # on time
        ]

        fin_list = [create_mock_financial(f"P-0{i}", 1000000, 800000, 750000, 0.0) for i in range(1, 6)]
        prog_list = [create_mock_progress(f"P-0{i}", 60.0, 60.0) for i in range(1, 6)]

        mock_query_portfolio = MagicMock()
        mock_query_portfolio.scalars.return_value.all.return_value = portfolio
        mock_query_fin = MagicMock()
        mock_query_fin.scalars.return_value.all.return_value = fin_list
        mock_query_prog = MagicMock()
        mock_query_prog.scalars.return_value.all.return_value = prog_list

        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=target_project)),
            mock_query_portfolio,
            mock_query_fin,
            mock_query_prog,
        ]

        result = agency_engine.evaluate("P-01", db=mock_db)

        assert result.score >= 60
        assert result.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        assert result.details["projects_analyzed"] == 5
        assert result.details["delay_rate"] == 0.80  # 4 / 5
        assert "delay" in result.reason.lower()


# =============================================================================
# 4. High-Anomaly Agency (Frequent Cost Overruns & Gaps)
# =============================================================================

class TestHighAnomalyAgency:

    def test_high_cost_and_mismatch_portfolio(self, agency_engine):
        """
        An agency where projects consistently incur cost overruns (>10%)
        and severe financial-physical progress mismatches (>15%).
        """
        mock_db = MagicMock()
        target_project = create_mock_project("P-01", agency="Volatile Works")

        portfolio = [
            create_mock_project(f"P-0{i}", agency="Volatile Works", status="In Progress")
            for i in range(1, 5)
        ]

        # Financials: 3 out of 4 have severe overruns
        fin_list = [
            create_mock_financial("P-01", sanctioned=1000000, released=1200000, expenditure=1300000, overrun_pct=30.0),
            create_mock_financial("P-02", sanctioned=1000000, released=1200000, expenditure=1250000, overrun_pct=25.0),
            create_mock_financial("P-03", sanctioned=1000000, released=1150000, expenditure=1200000, overrun_pct=20.0),
            create_mock_financial("P-04", sanctioned=1000000, released=1000000, expenditure=900000, overrun_pct=0.0),
        ]

        # Progress: 3 out of 4 have gaps > 15% (e.g. 80% money spent, 20% physical work)
        prog_list = [
            create_mock_progress("P-01", physical_pct=20.0, financial_pct=85.0),
            create_mock_progress("P-02", physical_pct=30.0, financial_pct=90.0),
            create_mock_progress("P-03", physical_pct=25.0, financial_pct=80.0),
            create_mock_progress("P-04", physical_pct=50.0, financial_pct=50.0),
        ]

        mock_query_portfolio = MagicMock()
        mock_query_portfolio.scalars.return_value.all.return_value = portfolio
        mock_query_fin = MagicMock()
        mock_query_fin.scalars.return_value.all.return_value = fin_list
        mock_query_prog = MagicMock()
        mock_query_prog.scalars.return_value.all.return_value = prog_list

        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=target_project)),
            mock_query_portfolio,
            mock_query_fin,
            mock_query_prog,
        ]

        result = agency_engine.evaluate("P-01", db=mock_db)

        assert result.score >= 50
        assert result.details["cost_anomaly_rate"] == 0.75  # 3 / 4
        assert result.details["mismatch_rate"] == 0.75      # 3 / 4
        assert result.details["projects_analyzed"] == 4


# =============================================================================
# 5. Insufficient History Gating
# =============================================================================

class TestInsufficientHistory:

    def test_single_project_agency_gated(self, agency_engine):
        """
        When agency has fewer projects than min_projects (e.g. 1 < 3),
        score must be capped at <= 15 (LOW) and confidence damped (< 0.50).
        """
        mock_db = MagicMock()
        target_project = create_mock_project("P-01", agency="New Agency")

        portfolio = [target_project]
        fin_list = [create_mock_financial("P-01", 1000000, 1000000, 1500000, 50.0)]
        prog_list = [create_mock_progress("P-01", 10.0, 90.0)]

        mock_query_portfolio = MagicMock()
        mock_query_portfolio.scalars.return_value.all.return_value = portfolio
        mock_query_fin = MagicMock()
        mock_query_fin.scalars.return_value.all.return_value = fin_list
        mock_query_prog = MagicMock()
        mock_query_prog.scalars.return_value.all.return_value = prog_list

        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=target_project)),
            mock_query_portfolio,
            mock_query_fin,
            mock_query_prog,
        ]

        result = agency_engine.evaluate("P-01", db=mock_db)

        # Must be capped due to insufficient sample
        assert result.score <= 15
        assert result.risk_level == RiskLevel.LOW
        assert result.confidence <= 0.40
        assert result.details["insufficient_history"] is True
        assert result.details["projects_analyzed"] == 1
        assert "insufficient" in result.reason.lower()


# =============================================================================
# 6. Missing Agency Entity
# =============================================================================

class TestMissingAgency:

    def test_null_agency_field(self, agency_engine):
        """
        If implementing_agency (and all fallbacks) is None,
        return score 0 and confidence 0.0 with clear reason.
        """
        mock_db = MagicMock()
        project_without_agency = create_mock_project("P-99", agency=None)
        mock_db.execute.return_value.scalar_one_or_none.return_value = project_without_agency

        result = agency_engine.evaluate("P-99", db=mock_db)

        assert result.score == 0
        assert result.confidence == 0.0
        assert result.risk_level == RiskLevel.LOW
        assert result.details["projects_analyzed"] == 0
        assert result.details["missing_agency"] is True
        assert "not specified" in result.reason.lower()

    def test_blank_string_agency(self, agency_engine):
        """Blank whitespace agency strings should also be treated as missing."""
        mock_db = MagicMock()
        project_blank_agency = create_mock_project("P-98", agency="   ")
        mock_db.execute.return_value.scalar_one_or_none.return_value = project_blank_agency

        result = agency_engine.evaluate("P-98", db=mock_db)

        assert result.score == 0
        assert result.confidence == 0.0
        assert result.details["missing_agency"] is True


# =============================================================================
# 7. Fallback Agency Entity Resolution
# =============================================================================

class TestCandidateFieldFallback:

    def test_fallback_to_executing_agency(self, agency_engine):
        """When implementing_agency is None, resolves executing_agency."""
        mock_db = MagicMock()
        p = create_mock_project("P-F1", agency=None, executing_agency="State PWD")
        mock_db.execute.return_value.scalar_one_or_none.return_value = p

        agency_name, field_used = agency_engine._resolve_agency(p)
        assert agency_name == "State PWD"
        assert field_used == "executing_agency"

    def test_fallback_to_department(self, agency_engine):
        """When implementing and executing are None, resolves department."""
        p = create_mock_project("P-F2", agency=None, executing_agency=None, department="Irrigation Dept")
        agency_name, field_used = agency_engine._resolve_agency(p)
        assert agency_name == "Irrigation Dept"
        assert field_used == "department"

    def test_fallback_to_contractor(self, agency_engine):
        """When others are None, resolves contractor."""
        p = create_mock_project("P-F3", agency=None, contractor="ABC Builders Ltd")
        agency_name, field_used = agency_engine._resolve_agency(p)
        assert agency_name == "ABC Builders Ltd"
        assert field_used == "contractor"

    def test_fallback_to_authority(self, agency_engine):
        """When others are None, resolves authority."""
        p = create_mock_project("P-F4", agency=None, authority="Municipal Corporation")
        agency_name, field_used = agency_engine._resolve_agency(p)
        assert agency_name == "Municipal Corporation"
        assert field_used == "authority"


# =============================================================================
# 8. Non-Accusatory Governance Tone
# =============================================================================

class TestGovernanceTone:

    @pytest.mark.parametrize("score, delay, cost, mismatch", [
        (10, 0.05, 0.0, 0.0),
        (45, 0.40, 0.20, 0.20),
        (65, 0.65, 0.35, 0.35),
        (85, 0.85, 0.50, 0.50),
    ])
    def test_no_fraud_or_criminal_accusations(self, score, delay, cost, mismatch):
        """Reasons must strictly avoid defamatory or accusatory terminology."""
        explanation = AgencyPatternEngine._generate_explanation(
            agency_name="Test Agency",
            projects_analyzed=10,
            delay_rate=delay,
            cost_anomaly_rate=cost,
            mismatch_rate=mismatch,
            completion_rate=80.0,
            score=score,
        )
        prohibited_terms = [
            "fraud", "corrupt", "scam", "illegal", "criminal", "embezzle",
            "stolen", "culpable", "guilty", "crime"
        ]
        explanation_lower = explanation.lower()
        for term in prohibited_terms:
            assert term not in explanation_lower, f"Prohibited accusatory term '{term}' found in reason: {explanation}"


# =============================================================================
# 9. Configurable Thresholds & Context Override
# =============================================================================

class TestConfigurability:

    def test_context_override_thresholds(self, agency_engine):
        """Runtime thresholds passed via context dictionary must override defaults."""
        mock_db = MagicMock()
        target = create_mock_project("P-01", agency="Flex Agency")

        # 2 projects (normally gated when min_projects=3)
        portfolio = [
            create_mock_project("P-01", agency="Flex Agency"),
            create_mock_project("P-02", agency="Flex Agency"),
        ]
        fin_list = [create_mock_financial(p.project_id) for p in portfolio]
        prog_list = [create_mock_progress(p.project_id) for p in portfolio]

        mock_query_portfolio = MagicMock()
        mock_query_portfolio.scalars.return_value.all.return_value = portfolio
        mock_query_fin = MagicMock()
        mock_query_fin.scalars.return_value.all.return_value = fin_list
        mock_query_prog = MagicMock()
        mock_query_prog.scalars.return_value.all.return_value = prog_list

        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=target)),
            mock_query_portfolio,
            mock_query_fin,
            mock_query_prog,
        ]

        # Override min_projects to 2 in context
        context = {"min_projects": 2}
        result = agency_engine.evaluate("P-01", db=mock_db, context=context)

        # Because min_projects was overridden to 2, N=2 is NOT gated as insufficient
        assert result.details["insufficient_history"] is False
        assert result.details["min_projects_threshold"] == 2


# =============================================================================
# 10. Live Database Integration Tests
# =============================================================================

class TestLiveDatabaseAgencyEvaluation:

    def test_drda_portfolio_evaluation(self, db_session, agency_engine):
        """
        Evaluate real live project MPLADS-2024-0001 (DRDA).
        Live dataset has 20 projects, all assigned to District Rural Development Agency (DRDA).
        """
        result = agency_engine.evaluate("MPLADS-2024-0001", db=db_session)
        assert result.engine == "agency_pattern"
        assert result.details["agency_name"] == "District Rural Development Agency (DRDA)"
        assert result.details["agency_field_used"] == "implementing_agency"
        assert result.details["projects_analyzed"] == 20
        assert result.details["insufficient_history"] is False
        assert result.confidence == 0.95
        assert 0 <= result.score <= 100
        assert result.risk_level in {RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}
        assert result.details["average_cost"] > 0
        assert result.details["median_cost"] > 0
        assert 0.0 <= result.details["delay_rate"] <= 1.0
        assert 0.0 <= result.details["cost_anomaly_rate"] <= 1.0
        assert 0.0 <= result.details["mismatch_rate"] <= 1.0

    def test_nonexistent_project_evaluation(self, db_session, agency_engine):
        """Nonexistent project ID should return score 0, confidence 0.0."""
        result = agency_engine.evaluate("NONEXISTENT-PROJECT-9999", db=db_session)
        assert result.score == 0
        assert result.confidence == 0.0
        assert result.details["status"] == "not_found"
        assert "not found" in result.reason.lower()


# =============================================================================
# 11. Small Sample Size & Audit Guardrails
# =============================================================================

class TestSampleAuditGuardrails:

    def test_two_projects_default_gating(self):
        """
        By default (min_projects=3), an agency with only 2 projects must be gated:
        score <= 15 (LOW), confidence <= 0.35, insufficient_history = True.
        """
        engine = AgencyPatternEngine()  # default min_projects is >= 3
        mock_db = MagicMock()
        target = create_mock_project("P-01", agency="Micro Agency")
        portfolio = [
            create_mock_project("P-01", agency="Micro Agency", status="In Progress", expected_comp=date(2023, 1, 1)),
            create_mock_project("P-02", agency="Micro Agency", status="In Progress", expected_comp=date(2023, 1, 1)),
        ]
        fin_list = [create_mock_financial(p.project_id) for p in portfolio]
        prog_list = [create_mock_progress(p.project_id) for p in portfolio]

        mock_query_portfolio = MagicMock()
        mock_query_portfolio.scalars.return_value.all.return_value = portfolio
        mock_query_fin = MagicMock()
        mock_query_fin.scalars.return_value.all.return_value = fin_list
        mock_query_prog = MagicMock()
        mock_query_prog.scalars.return_value.all.return_value = prog_list

        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=target)),
            mock_query_portfolio,
            mock_query_fin,
            mock_query_prog,
        ]

        result = engine.evaluate("P-01", db=mock_db)
        assert result.score <= 15
        assert result.risk_level == RiskLevel.LOW
        assert result.confidence <= 0.35
        assert result.details["insufficient_history"] is True
        assert "insufficient historical" in result.reason.lower()

    def test_small_sample_three_projects_cannot_reach_high_or_critical(self, agency_engine):
        """
        When agency has min_projects <= N < 5 (e.g. N=3), even with 100% delay rate,
        score must be capped at <= 55 (MEDIUM max), strictly preventing strong HIGH/CRITICAL conclusions.
        """
        mock_db = MagicMock()
        target = create_mock_project("P-01", agency="Small Bureau")
        # 3 projects, all 100% delayed
        today = date.today()
        portfolio = [
            create_mock_project(f"P-0{i}", agency="Small Bureau", status="In Progress",
                                expected_comp=today - timedelta(days=100))
            for i in range(1, 4)
        ]
        fin_list = [create_mock_financial(p.project_id) for p in portfolio]
        prog_list = [create_mock_progress(p.project_id) for p in portfolio]

        mock_query_portfolio = MagicMock()
        mock_query_portfolio.scalars.return_value.all.return_value = portfolio
        mock_query_fin = MagicMock()
        mock_query_fin.scalars.return_value.all.return_value = fin_list
        mock_query_prog = MagicMock()
        mock_query_prog.scalars.return_value.all.return_value = prog_list

        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=target)),
            mock_query_portfolio,
            mock_query_fin,
            mock_query_prog,
        ]

        result = agency_engine.evaluate("P-01", db=mock_db)
        assert result.details["projects_analyzed"] == 3
        assert result.details["insufficient_history"] is False
        assert result.score <= 55
        assert result.risk_level == RiskLevel.MEDIUM
        assert "limited sample size" in result.reason.lower() or "preliminary" in result.reason.lower()

    def test_adequate_sample_six_projects_can_reach_high(self, agency_engine):
        """
        When agency has N >= 5 (e.g. N=6) with chronic delays, score can reach HIGH (>= 60).
        """
        mock_db = MagicMock()
        target = create_mock_project("P-01", agency="Mid Agency")
        today = date.today()
        # 5 out of 6 delayed (>80% delay rate)
        portfolio = [
            create_mock_project(f"P-0{i}", agency="Mid Agency", status="In Progress",
                                expected_comp=today - timedelta(days=120))
            for i in range(1, 6)
        ] + [
            create_mock_project("P-06", agency="Mid Agency", status="Completed",
                                expected_comp=today - timedelta(days=10), actual_comp=today - timedelta(days=10))
        ]
        fin_list = [create_mock_financial(p.project_id) for p in portfolio]
        prog_list = [create_mock_progress(p.project_id) for p in portfolio]

        mock_query_portfolio = MagicMock()
        mock_query_portfolio.scalars.return_value.all.return_value = portfolio
        mock_query_fin = MagicMock()
        mock_query_fin.scalars.return_value.all.return_value = fin_list
        mock_query_prog = MagicMock()
        mock_query_prog.scalars.return_value.all.return_value = prog_list

        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=target)),
            mock_query_portfolio,
            mock_query_fin,
            mock_query_prog,
        ]

        result = agency_engine.evaluate("P-01", db=mock_db)
        assert result.details["projects_analyzed"] == 6
        assert result.score >= 60
        assert result.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}


# =============================================================================
# 12. Explainable Evidence Verification
# =============================================================================

class TestExplainableEvidence:

    def test_structured_evidence_dictionary(self, db_session, agency_engine):
        """Details must contain an auditable 'evidence' sub-dictionary with raw metrics."""
        result = agency_engine.evaluate("MPLADS-2024-0001", db=db_session)
        evidence = result.details.get("evidence")

        assert isinstance(evidence, dict)
        assert "total_projects" in evidence
        assert "delayed_count" in evidence
        assert "scheduled_count" in evidence
        assert "cost_anomaly_count" in evidence
        assert "mismatch_count" in evidence
        assert "completed_count" in evidence
        assert "sample_size_status" in evidence
        assert "data_completeness_pct" in evidence

        assert evidence["total_projects"] == 20
        assert evidence["delayed_count"] == 12
        assert evidence["cost_anomaly_count"] == 0
        assert evidence["mismatch_count"] == 8
        assert evidence["completed_count"] == 8
        assert evidence["sample_size_status"] in {"SUFFICIENT", "ROBUST"}

    def test_reason_includes_concrete_counts(self, db_session, agency_engine):
        """The textual reason must cite exact counts alongside percentages."""
        result = agency_engine.evaluate("MPLADS-2024-0001", db=db_session)
        reason = result.reason
        # E.g. "12 delayed [60.0%]"
        assert "12 delayed" in reason or "12" in reason
        assert "60.0%" in reason
        assert "District Rural Development Agency (DRDA)" in reason

