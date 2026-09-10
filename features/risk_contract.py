"""
features/risk_contract.py
=============================================================================
Formal Feature Contract & Input Schema for the MPLADS Predictive Risk Engine.
=============================================================================

Defines the exact feature vector contract, data types, statistical boundaries,
missing-value imputation policies, and operational justifications for both:
1. Pre-Award Recommendation Scoring (Feasibility & Inherent Risk)
2. In-Flight Execution Surveillance (Anomaly Detection & Delay Forecasting)
"""

import json
from enum import Enum
from pathlib import Path
from decimal import Decimal
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class LeakageContext(str, Enum):
    SAFE_PRE_AWARD = "safe_pre_award"          # Known at initial MP recommendation / sanction
    IN_FLIGHT_ONLY = "in_flight_surveillance"  # Generated during post-award execution tracking


class FeatureMetadata(BaseModel):
    name: str
    data_type: str
    context: LeakageContext
    formula: str
    expected_min: Optional[float]
    expected_max: Optional[float]
    imputation_strategy: str
    predictive_rationale: str


# =============================================================================
# 1. Official Risk Engine Feature Catalog
# =============================================================================

RISK_ENGINE_FEATURE_SPECS: List[FeatureMetadata] = [
    # --- CORE 6 REQUESTED FEATURES ---
    FeatureMetadata(
        name="delay_days",
        data_type="int",
        context=LeakageContext.IN_FLIGHT_ONLY,
        formula="(actual_completion_date - expected_completion_date) if completed else max(0, as_of_date - expected_completion_date)",
        expected_min=-365.0,
        expected_max=1825.0,
        imputation_strategy="0 for active works within schedule window",
        predictive_rationale="Primary temporal slippage metric. Quantifies schedule overrun beyond contractual milestones to forecast abandonment risk."
    ),
    FeatureMetadata(
        name="utilization_ratio",
        data_type="float",
        context=LeakageContext.IN_FLIGHT_ONLY,
        formula="expenditure_amount / (released_amount + epsilon)",
        expected_min=0.0,
        expected_max=2.0,
        imputation_strategy="0.0 when released amount is 0 or unrecorded",
        predictive_rationale="Fund absorption velocity. Stalled projects exhibit zero or negligible absorption despite fund disbursement."
    ),
    FeatureMetadata(
        name="cost_per_category",
        data_type="float",
        context=LeakageContext.SAFE_PRE_AWARD,
        formula="mean(sanctioned_amount) grouped by developmental sector",
        expected_min=10000.0,
        expected_max=50000000.0,
        imputation_strategy="Overall dataset median cost if sector is unmapped",
        predictive_rationale="Peer group baseline. Serves as denominator to detect budget inflation or under-estimation relative to typical asset types."
    ),
    FeatureMetadata(
        name="progress_gap",
        data_type="float",
        context=LeakageContext.IN_FLIGHT_ONLY,
        formula="planned_schedule_pct - physical_progress_pct",
        expected_min=-100.0,
        expected_max=100.0,
        imputation_strategy="0.0 if milestone timeline dates are missing",
        predictive_rationale="Direct execution drag indicator. High positive gap (>20%) signals that physical progress is critically lagging elapsed contract time."
    ),
    FeatureMetadata(
        name="cost_deviation",
        data_type="float",
        context=LeakageContext.IN_FLIGHT_ONLY,
        formula="expenditure_amount - sanctioned_amount",
        expected_min=-50000000.0,
        expected_max=50000000.0,
        imputation_strategy="0.0 if expenditure has not commenced",
        predictive_rationale="Financial cost overrun metric in absolute currency. Quantifies budgetary deficits and contractor claim variances."
    ),
    FeatureMetadata(
        name="project_duration",
        data_type="int",
        context=LeakageContext.IN_FLIGHT_ONLY,
        formula="max(0, (actual_completion if completed else ref_date) - start_date)",
        expected_min=1.0,
        expected_max=3650.0,
        imputation_strategy="Elapsed duration to reference date if completion date is missing",
        predictive_rationale="Total lifespan to date. Older active projects accumulate exponential stalling probability due to contractor turnover or site disputes."
    ),

    # --- JUSTIFIED COMPANION FEATURES FOR PREDICTIVE RISK ---
    FeatureMetadata(
        name="cost_relative_to_category",
        data_type="float",
        context=LeakageContext.SAFE_PRE_AWARD,
        formula="sanctioned_amount / category_mean_cost",
        expected_min=0.1,
        expected_max=10.0,
        imputation_strategy="1.0 (average norm)",
        predictive_rationale="Normalized capital intensity index. Proposals exceeding 1.5x of the sector norm face higher procurement scrutiny and cost risks."
    ),
    FeatureMetadata(
        name="sanction_sla_delay_days",
        data_type="int",
        context=LeakageContext.SAFE_PRE_AWARD,
        formula="max(0, (sanction_date - recommendation_date) - 75)",
        expected_min=0.0,
        expected_max=1000.0,
        imputation_strategy="0 if dates are unrecorded",
        predictive_rationale="Statutory bureaucratic friction. Projects that breached the 75-day district sanction SLA correlate with poor inter-agency coordination."
    ),
    FeatureMetadata(
        name="progress_gap_fin_phy",
        data_type="float",
        context=LeakageContext.IN_FLIGHT_ONLY,
        formula="financial_progress_pct - physical_progress_pct",
        expected_min=-100.0,
        expected_max=100.0,
        imputation_strategy="0.0",
        predictive_rationale="Financial-to-physical divergence. When fund disbursement exceeds physical milestone delivery by >15%, flags leakage or premature billing."
    ),
    FeatureMetadata(
        name="unreleased_allocation",
        data_type="float",
        context=LeakageContext.IN_FLIGHT_ONLY,
        formula="max(0, sanctioned_amount - released_amount)",
        expected_min=0.0,
        expected_max=50000000.0,
        imputation_strategy="0.0",
        predictive_rationale="Funding pipeline backlog. High unreleased allocations starve contractor cash flows, directly inducing work stoppages."
    ),
    FeatureMetadata(
        name="planned_duration_days",
        data_type="int",
        context=LeakageContext.SAFE_PRE_AWARD,
        formula="max(0, expected_completion_date - start_date)",
        expected_min=15.0,
        expected_max=1825.0,
        imputation_strategy="Sector median planned duration",
        predictive_rationale="Contractual timeline scope. Multi-year complex civil works have higher systemic vulnerability to inflation and contractor default."
    )
]


# =============================================================================
# 2. Pydantic Runtime Feature Vector Contract
# =============================================================================

class RiskEngineFeatureVector(BaseModel):
    """
    Type-safe, validated feature vector passed into the future ML/heuristic risk scoring engine.
    """
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    project_id: str = Field(..., description="Unique Project Identifier")
    
    # 6 Core Required Features
    delay_days: int = Field(default=0, description="Schedule delay in calendar days (positive = late, negative = early)")
    utilization_ratio: float = Field(default=0.0, ge=0.0, description="Fund absorption ratio (expenditure / released)")
    cost_per_category: float = Field(default=0.0, ge=0.0, description="Developmental sector benchmark cost in INR")
    progress_gap: float = Field(default=0.0, ge=-100.0, le=100.0, description="Schedule trajectory gap (planned - physical %)")
    cost_deviation: float = Field(default=0.0, description="Cost variance in INR (expenditure - sanctioned)")
    project_duration: int = Field(default=0, ge=0, description="Realized or current elapsed duration in days")

    # High-Value Companion Features
    cost_relative_to_category: float = Field(default=1.0, ge=0.0, description="Normalized sector cost multiplier")
    sanction_sla_delay_days: int = Field(default=0, ge=0, description="Days exceeded beyond statutory 75-day sanction SLA")
    progress_gap_fin_phy: float = Field(default=0.0, ge=-100.0, le=100.0, description="Financial vs physical disbursement skew %")
    unreleased_allocation: float = Field(default=0.0, ge=0.0, description="Committed funds awaiting release in INR")
    planned_duration_days: Optional[int] = Field(default=None, ge=0, description="Contractual timeline in days")
    is_delayed: bool = Field(default=False, description="Flag indicating project is behind schedule")
    is_schedule_lagging: bool = Field(default=False, description="Flag indicating physical progress lags schedule timeline")
    is_disbursement_skewed: bool = Field(default=False, description="Flag indicating financial disbursement exceeds physical delivery")
    has_cost_overrun: bool = Field(default=False, description="Flag indicating cost overrun above sanctioned ceiling")


def export_feature_schema(output_path: Optional[Path] = None) -> Path:
    """
    Exports the formal feature catalog and JSON schema for external consumers and the future risk engine.
    """
    if output_path is None:
        base_dir = Path(__file__).resolve().parent.parent
        output_path = base_dir / "data" / "processed" / "risk_engine_feature_schema.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    schema_payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MPLADS_Risk_Engine_Feature_Contract",
        "description": "Formal feature vector contract for the MPLADS Predictive Risk Scoring Engine.",
        "version": "1.0.0",
        "features": [f.model_dump() for f in RISK_ENGINE_FEATURE_SPECS],
        "input_validation_schema": RiskEngineFeatureVector.model_json_schema()
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema_payload, f, indent=2)

    return output_path


if __name__ == "__main__":
    out = export_feature_schema()
    print(f"Exported Risk Engine Feature Schema to: {out}")
