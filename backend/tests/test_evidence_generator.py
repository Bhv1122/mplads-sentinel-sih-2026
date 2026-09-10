"""
backend/tests/test_evidence_generator.py
=============================================================================
Phase 8: Evidence Generator Unit and Integration Tests.
=============================================================================

Validates:
1. Reusable formatting functions (currency, percentages, ratios, dates, durations, scores, multipliers).
2. Exact user prompt examples:
   - Cost Anomaly: "Cost is 2.56× peer median."
   - Delay Detection: "Project is delayed by 210 days."
   - Progress Mismatch: "Financial progress exceeds physical progress by 47 percentage points."
   - Duplicate Detection: "Project description has 94% similarity with project XYZ, exceeding the 85% duplicate threshold."
3. Strict non-hallucination / numerical preservation.
4. Underlying raw values retention on EvidenceStatement for frontend inspection.
5. Integration with ExplainabilityService and StructuredExplanation.
"""

import os
import sys
import pytest
from datetime import datetime, date
from decimal import Decimal

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.schemas.explainability import EvidenceStatement, StructuredExplanation
from app.services.evidence_generator import (
    EvidenceGenerator,
    evidence_generator,
    format_currency,
    format_percentage,
    format_percentage_points,
    format_multiplier,
    format_ratio,
    format_duration,
    format_date,
    format_score,
    parse_numerical_value,
)
from app.services.explainability_service import ExplainabilityService


# =============================================================================
# 1. Reusable Formatting Functions Tests
# =============================================================================

class TestFormattingFunctions:

    def test_format_currency_standard_indian_system(self):
        """Validates Indian comma grouping (Lakhs and Crores)."""
        assert format_currency(25600000) == "₹2,56,00,000.00"
        assert format_currency(100000) == "₹1,00,000.00"
        assert format_currency(1234567.89) == "₹12,34,567.89"
        assert format_currency(500) == "₹500.00"
        assert format_currency(None) == "N/A"

    def test_format_currency_compact_and_crore(self):
        """Validates compact representation and in_crores conversion."""
        assert format_currency(25600000, compact=True) == "₹2.56 Cr"
        assert format_currency(10000000, compact=True) == "₹1 Cr"
        assert format_currency(150000, compact=True) == "₹1.5 L"
        assert format_currency(25600000, in_crores=True) == "2.56 crore"
        assert format_currency("25.6 crore") == "25.6 crore"
        assert format_currency("10 crore") == "10 crore"

    def test_format_percentage(self):
        """Validates percentage formatting from ratios and whole numbers."""
        assert format_percentage(0.94) == "94%"
        assert format_percentage(0.85) == "85%"
        assert format_percentage(82) == "82%"
        assert format_percentage("82%") == "82%"
        assert format_percentage(0.475, decimals=1) == "47.5%"
        assert format_percentage(0.94, include_symbol=False) == "94"
        assert format_percentage(None) == "N/A"

    def test_format_percentage_points(self):
        """Validates percentage point differences and singular/plural units."""
        assert format_percentage_points(47) == "47 percentage points"
        assert format_percentage_points(1) == "1 percentage point"
        assert format_percentage_points(-47) == "47 percentage points"
        assert format_percentage_points(12.5, decimals=1) == "12.5 percentage points"
        assert format_percentage_points(None) == "N/A"

    def test_format_multiplier(self):
        """Validates mathematical multiplication sign '×' and rounding."""
        assert format_multiplier(2.56) == "2.56×"
        assert format_multiplier(2.0) == "2×"
        assert format_multiplier(1.35) == "1.35×"
        assert format_multiplier("2.56") == "2.56×"
        assert format_multiplier(None) == "N/A"

    def test_format_ratio(self):
        """Validates ratio output styles."""
        assert format_ratio(25.6, 10.0, style="multiplier") == "2.56×"
        assert format_ratio(25.6, 10.0, style="ratio") == "2.56:1"
        assert format_ratio(20, 10, style="ratio") == "2:1"
        assert format_ratio(10, 0) == "N/A"

    def test_format_duration(self):
        """Validates duration strings and singular/plural."""
        assert format_duration(210) == "210 days"
        assert format_duration(1) == "1 day"
        assert format_duration(0) == "0 days"
        assert format_duration("210") == "210 days"
        assert format_duration(None) == "N/A"

    def test_format_date(self):
        """Validates standard date formatting."""
        dt = datetime(2026, 9, 9, 12, 0, 0)
        d = date(2026, 9, 9)
        assert format_date(dt) == "2026-09-09"
        assert format_date(d) == "2026-09-09"
        assert format_date("2026-09-09T18:30:00Z") == "2026-09-09"
        assert format_date(None) == "N/A"

    def test_format_score(self):
        """Validates detector and composite score formatting."""
        assert format_score(78.4) == "78.4"
        assert format_score(78.4, include_max=True) == "78.4/100"
        assert format_score(86) == "86"
        assert format_score(None) == "N/A"


# =============================================================================
# 2. Exact User Prompt Examples
# =============================================================================

class TestUserPromptExamples:

    @pytest.fixture
    def gen(self):
        return EvidenceGenerator()

    def test_example_1_cost_anomaly(self, gen):
        """
        Input:
            project_cost = 25.6 crore
            peer_median = 10 crore
        Output:
            "Cost is 2.56× peer median."
        """
        # Test with string inputs mentioning crore
        stmt1 = gen.generate_cost_statement(project_cost="25.6 crore", peer_median="10 crore")
        assert stmt1.statement == "Cost is 2.56× peer median."
        assert stmt1.detector_name == "cost_anomaly"
        assert stmt1.metric_key == "cost_multiplier"
        assert stmt1.raw_values["multiplier"] == 2.56
        assert stmt1.raw_values["project_cost"] == "25.6 crore"
        assert stmt1.raw_values["peer_median"] == "10 crore"

        # Test with raw numeric values (in crores)
        stmt2 = gen.generate_cost_statement(project_cost=25.6, peer_median=10.0)
        assert stmt2.statement == "Cost is 2.56× peer median."
        assert stmt2.raw_values["multiplier"] == 2.56

        # Test with raw INR amounts (25.6 crore vs 10 crore in INR)
        stmt3 = gen.generate_cost_statement(project_cost=256_000_000, peer_median=100_000_000)
        assert stmt3.statement == "Cost is 2.56× peer median."
        assert stmt3.raw_values["multiplier"] == 2.56

    def test_example_2_delay_detection(self, gen):
        """
        Input:
            delay_days = 210
        Output:
            "Project is delayed by 210 days."
        """
        stmt = gen.generate_delay_statement(delay_days=210)
        assert stmt.statement == "Project is delayed by 210 days."
        assert stmt.detector_name == "delay_detection"
        assert stmt.metric_key == "delay_days"
        assert stmt.raw_values["delay_days"] == 210
        assert stmt.raw_values["is_delayed"] is True

        # Test on-schedule case
        stmt_on_schedule = gen.generate_delay_statement(delay_days=0)
        assert stmt_on_schedule.statement == "Project is on schedule."
        assert stmt_on_schedule.raw_values["is_delayed"] is False

    def test_example_3_progress_mismatch(self, gen):
        """
        Input:
            financial_progress = 82%
            physical_progress = 35%
        Output:
            "Financial progress exceeds physical progress by 47 percentage points."
        """
        # Test with string percentage inputs
        stmt1 = gen.generate_progress_statement(financial_progress="82%", physical_progress="35%")
        assert stmt1.statement == "Financial progress exceeds physical progress by 47 percentage points."
        assert stmt1.detector_name == "progress_mismatch"
        assert stmt1.metric_key == "progress_gap"
        assert stmt1.raw_values["progress_gap"] == 47.0
        assert stmt1.raw_values["direction"] == "financial_ahead"

        # Test with whole numeric values
        stmt2 = gen.generate_progress_statement(financial_progress=82.0, physical_progress=35.0)
        assert stmt2.statement == "Financial progress exceeds physical progress by 47 percentage points."
        assert stmt2.raw_values["progress_gap"] == 47.0

        # Test with ratio floats (0.82 vs 0.35)
        stmt3 = gen.generate_progress_statement(financial_progress=0.82, physical_progress=0.35)
        assert stmt3.statement == "Financial progress exceeds physical progress by 47 percentage points."
        assert stmt3.raw_values["progress_gap"] == 47.0

        # Test physical ahead
        stmt4 = gen.generate_progress_statement(financial_progress=20, physical_progress=40)
        assert stmt4.statement == "Physical progress exceeds financial progress by 20 percentage points."
        assert stmt4.raw_values["direction"] == "physical_ahead"

    def test_example_4_duplicate_detection(self, gen):
        """
        Input:
            similarity_score = 0.94
            threshold = 0.85
        Output:
            "Project description has 94% similarity with project XYZ, exceeding the 85% duplicate threshold."
        """
        stmt = gen.generate_duplicate_statement(
            similarity_score=0.94,
            threshold=0.85,
            matched_project_id="XYZ",
        )
        assert stmt.statement == "Project description has 94% similarity with project XYZ, exceeding the 85% duplicate threshold."
        assert stmt.detector_name == "duplicate_detection"
        assert stmt.metric_key == "similarity_score"
        assert stmt.raw_values["similarity_score"] == 0.94
        assert stmt.raw_values["threshold"] == 0.85
        assert stmt.raw_values["matched_project_id"] == "XYZ"
        assert stmt.raw_values["exceeds_threshold"] is True

        # Test within threshold
        stmt_within = gen.generate_duplicate_statement(
            similarity_score=0.55,
            threshold=0.85,
            matched_project_id="XYZ",
        )
        assert stmt_within.statement == "Project description has 55% similarity with project XYZ, within the 85% duplicate threshold."
        assert stmt_within.raw_values["exceeds_threshold"] is False


# =============================================================================
# 3. Agency & Overrun Statements
# =============================================================================

class TestAgencyAndOverrunStatements:

    @pytest.fixture
    def gen(self):
        return EvidenceGenerator()

    def test_agency_statement_exceeding_benchmark(self, gen):
        """Validates agency statement when historical delay exceeds benchmark."""
        stmt = gen.generate_agency_statement(
            agency_name="NBCC Ltd",
            projects_analyzed=12,
            delay_rate=0.75,
            benchmark=0.25,
        )
        assert stmt.statement == "Implementing agency NBCC Ltd has a 75% historical delay rate across 12 projects, exceeding the 25% benchmark."
        assert stmt.detector_name == "agency_pattern"
        assert stmt.raw_values["projects_analyzed"] == 12
        assert stmt.raw_values["exceeds_benchmark"] is True

    def test_agency_statement_insufficient_history(self, gen):
        """Validates agency statement with fewer than 3 historical projects."""
        stmt = gen.generate_agency_statement(
            agency_name="CPWD Sub-division",
            projects_analyzed=2,
            delay_rate=0.50,
            insufficient_history=True,
        )
        assert stmt.statement == "Implementing agency CPWD Sub-division has only 2 historical projects recorded (minimum 3 required for statistical pattern analysis)."
        assert stmt.raw_values["insufficient_history"] is True

    def test_cost_overrun_statement(self, gen):
        """Validates expenditure overrun against approved sanction."""
        stmt = gen.generate_cost_overrun_statement(
            expenditure=2_500_000,
            sanctioned=2_000_000,
        )
        assert stmt.statement == "Expenditure exceeds sanctioned amount by 25.0%."
        assert stmt.raw_values["cost_overrun_pct"] == 25.0


# =============================================================================
# 4. Dispatcher & Raw Value Retention
# =============================================================================

class TestDispatcherAndRetention:

    @pytest.fixture
    def gen(self):
        return EvidenceGenerator()

    def test_generate_statements_from_detector_cost(self, gen):
        """Tests dispatcher for cost anomaly engine."""
        data = {
            "score": 85.0,
            "details": {
                "evaluated_cost": 25600000.0,
                "peer_median": 10000000.0,
                "sanctioned_amount": 20000000.0,
                "cost_overrun_pct": 28.0,
            }
        }
        stmts = gen.generate_statements_from_detector("cost_anomaly", data)
        assert len(stmts) == 2
        assert stmts[0].statement == "Cost is 2.56× peer median."
        assert "Expenditure exceeds sanctioned amount" in stmts[1].statement
        assert stmts[0].raw_values["parsed_cost"] == 25600000.0

    def test_generate_statements_from_detector_delay(self, gen):
        """Tests dispatcher for delay detection engine."""
        data = {
            "score": 75.0,
            "details": {
                "overdue_days": 210,
                "planned_duration": 365,
                "expected_completion_date": "2025-06-30",
            }
        }
        stmts = gen.generate_statements_from_detector("delay_detection", data)
        assert len(stmts) == 1
        assert stmts[0].statement == "Project is delayed by 210 days."
        assert stmts[0].raw_values["delay_days"] == 210


# =============================================================================
# 5. Integration with ExplainabilityService
# =============================================================================

class TestExplainabilityServiceIntegration:

    def test_explainability_service_attaches_evidence_statements(self):
        """Verifies that ExplainabilityService populates evidence_statements and concise_statements."""
        service = ExplainabilityService()

        synthetic_risk_result = {
            "project_id": "MPLADS-2024-TEST-EVIDENCE",
            "overall_score": 78.4,
            "risk_level": "HIGH",
            "confidence": 0.90,
            "summary": "Project exhibits elevated risk due to cost anomaly and schedule overrun.",
            "engines": {
                "cost_anomaly": {
                    "score": 86.0,
                    "triggered": True,
                    "weight": 0.20,
                    "contribution": 17.2,
                    "reason": "Evaluated cost is significantly higher than peer median.",
                    "details": {
                        "evaluated_cost": 25.6,
                        "peer_median": 10.0,
                        "deviation_percentage": 156.0,
                        "peer_scope": "district_category",
                        "sanctioned_amount": 20.0,
                        "cost_overrun_pct": 28.0,
                    }
                },
                "delay_detection": {
                    "score": 80.0,
                    "triggered": True,
                    "weight": 0.20,
                    "contribution": 16.0,
                    "reason": "Project execution is delayed.",
                    "details": {
                        "overdue_days": 210,
                        "delay_percentage": 57.5,
                        "planned_duration": 365,
                        "expected_completion_date": "2025-06-30",
                    }
                },
                "progress_mismatch": {
                    "score": 70.0,
                    "triggered": True,
                    "weight": 0.20,
                    "contribution": 14.0,
                    "reason": "Financial progress leads physical completion.",
                    "details": {
                        "financial_progress": 82.0,
                        "physical_progress": 35.0,
                        "progress_gap": 47.0,
                        "direction": "financial_ahead",
                    }
                },
                "duplicate_detection": {
                    "score": 75.0,
                    "triggered": True,
                    "weight": 0.20,
                    "contribution": 15.0,
                    "reason": "Substantial textual similarity with project XYZ.",
                    "details": {
                        "similarity": 0.94,
                        "threshold": 0.85,
                        "matched_project_id": "XYZ",
                    }
                },
                "agency_pattern": {
                    "score": 60.0,
                    "triggered": False,
                    "weight": 0.20,
                    "contribution": 12.0,
                    "reason": "Agency track record is within acceptable limits.",
                    "details": {
                        "agency_name": "Standard Construction Agency",
                        "projects_analyzed": 5,
                        "delay_rate": 0.20,
                        "mismatch_rate": 0.10,
                    }
                }
            }
        }

        explanation: StructuredExplanation = service.explain_risk_result(
            risk_result=synthetic_risk_result,
            project_metadata={"project_title": "Community Center Construction"},
        )

        # Check that concise_statements is populated on top-level StructuredExplanation
        assert len(explanation.concise_statements) > 0

        # Verify that each factor contains evidence_statements
        factor_map = {f.detector_name: f for f in explanation.explanation_factors}

        # Check Cost Factor
        cost_factor = factor_map["cost_anomaly"]
        assert len(cost_factor.evidence_statements) >= 1
        cost_stmts = [s.statement for s in cost_factor.evidence_statements]
        assert "Cost is 2.56× peer median." in cost_stmts

        # Check Delay Factor
        delay_factor = factor_map["delay_detection"]
        assert len(delay_factor.evidence_statements) >= 1
        delay_stmts = [s.statement for s in delay_factor.evidence_statements]
        assert "Project is delayed by 210 days." in delay_stmts

        # Check Progress Mismatch Factor
        mismatch_factor = factor_map["progress_mismatch"]
        assert len(mismatch_factor.evidence_statements) >= 1
        mismatch_stmts = [s.statement for s in mismatch_factor.evidence_statements]
        assert "Financial progress exceeds physical progress by 47 percentage points." in mismatch_stmts

        # Check Duplicate Factor
        dup_factor = factor_map["duplicate_detection"]
        assert len(dup_factor.evidence_statements) >= 1
        dup_stmts = [s.statement for s in dup_factor.evidence_statements]
        assert "Project description has 94% similarity with project XYZ, exceeding the 85% duplicate threshold." in dup_stmts

        # Check that top-level concise_statements contains these exact statements
        assert "Cost is 2.56× peer median." in explanation.concise_statements
        assert "Project is delayed by 210 days." in explanation.concise_statements
        assert "Financial progress exceeds physical progress by 47 percentage points." in explanation.concise_statements
        assert "Project description has 94% similarity with project XYZ, exceeding the 85% duplicate threshold." in explanation.concise_statements
