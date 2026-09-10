"""
features/tests/test_features.py
=============================================================================
Unit tests and edge-case validation suite for Phase 5 Feature Engineering.
=============================================================================
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date

from features.config import FeatureConfig
from features.date_features import compute_delay_days, compute_project_duration
from features.financial_features import compute_utilization_ratio, compute_cost_deviation
from features.progress_features import compute_progress_gap
from features.category_features import compute_cost_per_category
from features.pipeline import FeatureEngineeringPipeline


@pytest.fixture
def sample_projects_df():
    """Generates synthetic DataFrame with representative normal & edge cases."""
    return pd.DataFrame({
        "project_id": ["P1", "P2", "P3", "P4", "P5"],
        "sector": ["Water", "Water", "Roads", "Roads", "Health"],
        "recommendation_date": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01", "2024-05-01"],
        "sanction_date": ["2024-01-20", "2024-03-15", "2024-03-25", "2024-04-20", "2024-05-15"],
        "work_order_date": ["2024-02-01", "2024-04-01", "2024-04-10", "2024-05-01", "2024-06-01"],
        "expected_completion_date": ["2024-06-01", "2024-08-01", "2024-09-01", "2024-07-01", "2024-10-01"],
        "actual_completion_date": ["2024-05-20", None, None, "2024-07-15", None],
        "reported_date": ["2024-06-15", "2024-06-15", "2024-06-15", "2024-07-20", "2024-06-15"],
        "recommended_amount": [100000.0, 200000.0, 500000.0, 300000.0, 400000.0],
        "sanctioned_amount": [90000.0, 200000.0, 450000.0, 300000.0, 400000.0],
        "released_amount": [90000.0, 100000.0, 200000.0, 300000.0, 0.0],
        "expenditure_amount": [85000.0, 50000.0, 150000.0, 320000.0, 0.0],
        "physical_progress_pct": [100.0, 30.0, 40.0, 100.0, 0.0],
        "financial_progress_pct": [94.44, 50.0, 75.0, 106.67, 0.0],
        "days_delayed": [0, 0, 15, 0, 0]
    })


def test_delay_days_sign_convention(sample_projects_df):
    """
    Tests delay_days calculation:
    - P1: Completed 2024-05-20 vs planned 2024-06-01 -> Early by 12 days -> delay = -12
    - P2: Ongoing, as_of 2024-06-15 vs planned 2024-08-01 -> Not yet due -> delay = 0
    - P3: Has explicit inspection days_delayed = 15 -> delay = 15
    - P4: Completed 2024-07-15 vs planned 2024-07-01 -> Late by 14 days -> delay = 14
    """
    config = FeatureConfig(as_of_date="2024-06-15", positive_means_delayed=True)
    df = compute_delay_days(sample_projects_df, config)

    assert "delay_days" in df.columns
    assert "is_delayed" in df.columns

    # P1: Early
    assert df.loc[df["project_id"] == "P1", "delay_days"].iloc[0] == -12
    assert not df.loc[df["project_id"] == "P1", "is_delayed"].iloc[0]

    # P2: Active, within schedule
    assert df.loc[df["project_id"] == "P2", "delay_days"].iloc[0] == 0

    # P3: Delayed by inspection telemetry
    assert df.loc[df["project_id"] == "P3", "delay_days"].iloc[0] == 15
    assert df.loc[df["project_id"] == "P3", "is_delayed"].iloc[0]

    # P4: Completed late
    assert df.loc[df["project_id"] == "P4", "delay_days"].iloc[0] == 14
    assert df.loc[df["project_id"] == "P4", "is_delayed"].iloc[0]


def test_delay_days_inverted_sign_convention(sample_projects_df):
    """Verifies configurable sign convention when positive_means_delayed=False."""
    config = FeatureConfig(as_of_date="2024-06-15", positive_means_delayed=False)
    df = compute_delay_days(sample_projects_df, config)

    # Inverted: Early P1 is +12, Late P4 is -14
    assert df.loc[df["project_id"] == "P1", "delay_days"].iloc[0] == 12
    assert df.loc[df["project_id"] == "P4", "delay_days"].iloc[0] == -14


def test_utilization_ratio_and_zero_division(sample_projects_df):
    """Verifies utilization ratios and zero-denominator handling."""
    config = FeatureConfig()
    df = compute_utilization_ratio(sample_projects_df, config)

    assert "utilization_ratio" in df.columns
    assert "utilization_ratio_released" in df.columns
    assert "utilization_ratio_sanctioned" in df.columns

    # P1: 85000 / 90000 = ~0.9444
    assert np.isclose(df.loc[df["project_id"] == "P1", "utilization_ratio"].iloc[0], 0.9444, atol=1e-3)

    # P2: exp 50000, rel 100000, sanc 200000
    assert np.isclose(df.loc[df["project_id"] == "P2", "utilization_ratio_released"].iloc[0], 0.50, atol=1e-3)
    assert np.isclose(df.loc[df["project_id"] == "P2", "utilization_ratio_sanctioned"].iloc[0], 0.25, atol=1e-3)

    # P5: released = 0.0 -> must be 0.0, zero division avoided
    assert df.loc[df["project_id"] == "P5", "utilization_ratio"].iloc[0] == 0.0
    assert df.loc[df["project_id"] == "P5", "utilization_ratio_released"].iloc[0] == 0.0


def test_cost_deviation_formulas(sample_projects_df):
    """
    Verifies:
    - Sanction deviation: sanctioned - recommended
    - Expenditure deviation: expenditure - sanctioned (overrun)
    """
    config = FeatureConfig()
    df = compute_cost_deviation(sample_projects_df, config)

    assert "cost_deviation_sanction" in df.columns
    assert "cost_deviation_expenditure" in df.columns
    assert "has_cost_overrun" in df.columns

    # P1: sanctioned 90k, recommended 100k -> -10000 (-10.0%)
    assert df.loc[df["project_id"] == "P1", "cost_deviation_sanction"].iloc[0] == -10000.0
    assert df.loc[df["project_id"] == "P1", "cost_deviation_sanction_pct"].iloc[0] == -10.0

    # P4: expenditure 320k, sanctioned 300k -> +20000 overrun
    assert df.loc[df["project_id"] == "P4", "cost_deviation_expenditure"].iloc[0] == 20000.0
    assert df.loc[df["project_id"] == "P4", "has_cost_overrun"].iloc[0]


def test_cost_per_category_and_relative_index(sample_projects_df):
    """Verifies sector group means, relative ratios, and single-item groups."""
    config = FeatureConfig()
    df = compute_cost_per_category(sample_projects_df, config)

    assert "category_mean_cost" in df.columns
    assert "cost_relative_to_category" in df.columns
    assert "cost_category_zscore" in df.columns

    # Water sector: P1 (90k) and P2 (200k) -> mean = 145k
    water_mean = df.loc[df["sector"] == "Water", "category_mean_cost"].iloc[0]
    assert water_mean == 145000.0

    # P1 relative cost: 90 / 145 = ~0.6207
    p1_rel = df.loc[df["project_id"] == "P1", "cost_relative_to_category"].iloc[0]
    assert np.isclose(p1_rel, 90000.0 / 145000.0, atol=1e-3)

    # Health sector: single project P5 (400k) -> std = 0.0, zscore = 0.0 (no crash)
    p5_zscore = df.loc[df["project_id"] == "P5", "cost_category_zscore"].iloc[0]
    assert p5_zscore == 0.0


def test_progress_gap_calculations(sample_projects_df):
    """Verifies schedule gap and financial-physical gap."""
    config = FeatureConfig(as_of_date="2024-06-15")
    df = compute_progress_gap(sample_projects_df, config)

    assert "progress_gap" in df.columns
    assert "progress_gap_schedule" in df.columns
    assert "progress_gap_fin_phy" in df.columns

    # P2: financial 50% - physical 30% -> fin-phy gap = +20.0%
    p2_fin_phy = df.loc[df["project_id"] == "P2", "progress_gap_fin_phy"].iloc[0]
    assert p2_fin_phy == 20.0
    assert df.loc[df["project_id"] == "P2", "is_disbursement_skewed"].iloc[0]

    # Completed projects (P1, P4) have planned_schedule_pct = 100.0, physical = 100.0 -> gap = 0.0
    assert df.loc[df["project_id"] == "P1", "progress_gap_schedule"].iloc[0] == 0.0
    assert df.loc[df["project_id"] == "P4", "progress_gap_schedule"].iloc[0] == 0.0


def test_project_duration_metrics(sample_projects_df):
    """Verifies contractual duration vs actual duration vs elapsed duration."""
    config = FeatureConfig(as_of_date="2024-06-15")
    df = compute_project_duration(sample_projects_df, config)

    assert "planned_duration_days" in df.columns
    assert "actual_duration_days" in df.columns
    assert "elapsed_duration_days" in df.columns
    assert "admin_sanction_duration_days" in df.columns

    # P1: work order 2024-02-01, expected 2024-06-01 -> planned = 121 days
    # actual completion 2024-05-20 -> actual = 109 days
    assert df.loc[df["project_id"] == "P1", "planned_duration_days"].iloc[0] == 121
    assert df.loc[df["project_id"] == "P1", "actual_duration_days"].iloc[0] == 109

    # P2: Ongoing -> actual_duration_days is NaN (censored, avoids lookahead leakage)
    assert np.isnan(df.loc[df["project_id"] == "P2", "actual_duration_days"].iloc[0])
    # Elapsed duration: 2024-04-01 to 2024-06-15 -> 75 days
    assert df.loc[df["project_id"] == "P2", "elapsed_duration_days"].iloc[0] == 75


def test_raw_columns_preserved(sample_projects_df):
    """Guarantees that 100% of raw input columns remain untouched."""
    raw_cols = list(sample_projects_df.columns)
    pipeline = FeatureEngineeringPipeline()
    output_df = pipeline.transform(sample_projects_df)

    for col in raw_cols:
        assert col in output_df.columns
        # Value equality
        pd.testing.assert_series_equal(output_df[col], sample_projects_df[col], check_names=False)


def test_end_to_end_pipeline_with_real_data():
    """Runs the full FeatureEngineeringPipeline on the Phase 2 cleaned datasets."""
    pipeline = FeatureEngineeringPipeline()
    featured_df = pipeline.run()

    assert len(featured_df) == 20
    required_features = [
        "delay_days",
        "utilization_ratio",
        "cost_per_category",
        "cost_relative_to_category",
        "progress_gap",
        "cost_deviation",
        "planned_duration_days"
    ]
    for feat in required_features:
        assert feat in featured_df.columns
        assert featured_df[feat].notna().any()
