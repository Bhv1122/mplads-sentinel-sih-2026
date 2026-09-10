"""
features/config.py
=============================================================================
Configuration parameters and settings for Phase 5 Feature Engineering.
Supports customization of column mappings, sign conventions, SLA baselines,
and numerical safety thresholds.
=============================================================================
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List, Union


@dataclass
class FeatureConfig:
    """
    Configuration for MPLADS feature engineering transformations.

    Attributes:
        as_of_date: Reference date for active/ongoing project duration and schedule
            calculations. If None, dynamically uses reported_date per row or date.today().
        positive_means_delayed: If True, delay_days > 0 indicates schedule slippage.
            If False, delay_days > 0 indicates early completion.
        sanction_sla_days: Statutory limit in days between MP recommendation and
            administrative sanction (75 days as per Paragraph 3.5 of MPLADS Guidelines).
        epsilon: Small positive float used to prevent division by zero in ratios and z-scores.
        category_col: Primary grouping column for categorical benchmarks.
        cost_col: Primary project cost column (sanctioned allocation).
        recommended_cost_col: Proposed project cost column.
        released_cost_col: Cumulative disbursed fund column.
        expenditure_col: Certified cumulative expenditure column.
        recommendation_date_col: Date MP recommendation was submitted.
        sanction_date_col: Date administrative sanction was accorded.
        work_order_date_col: Date work order was awarded to executing agency.
        expected_completion_date_col: Target/contractual milestone completion date.
        actual_completion_date_col: Realized completion and commissioning date.
        reported_date_col: As-of date for physical/financial progress telemetry.
        physical_progress_col: Inspected physical execution percentage (0-100).
        financial_progress_col: Financial expenditure percentage (0-100).
        days_delayed_col: Inspected milestone delay recorded by engineering authority.
    """
    as_of_date: Optional[Union[date, str]] = None
    positive_means_delayed: bool = True
    sanction_sla_days: int = 75
    epsilon: float = 1e-6

    # Column mappings
    category_col: str = "sector"
    cost_col: str = "sanctioned_amount"
    recommended_cost_col: str = "recommended_amount"
    released_cost_col: str = "released_amount"
    expenditure_col: str = "expenditure_amount"

    recommendation_date_col: str = "recommendation_date"
    sanction_date_col: str = "sanction_date"
    work_order_date_col: str = "work_order_date"
    expected_completion_date_col: str = "expected_completion_date"
    actual_completion_date_col: str = "actual_completion_date"

    reported_date_col: str = "reported_date"
    physical_progress_col: str = "physical_progress_pct"
    financial_progress_col: str = "financial_progress_pct"
    days_delayed_col: str = "days_delayed"
