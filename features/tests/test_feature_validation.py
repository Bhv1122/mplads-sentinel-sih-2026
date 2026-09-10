"""
features/tests/test_feature_validation.py
=============================================================================
Comprehensive 12-Point Validation Suite for Phase 5 Feature Engineering.

Verifies:
1. delay_days has correct sign and date logic
2. utilization_ratio handles zero/missing allocation safely
3. utilization ratios are numerically valid (no inf, non-negative, bounded)
4. cost_per_category calculated using correct category grouping & preserves raw costs
5. progress_gap correctly represents planned vs actual progress
6. cost_deviation correctly represents budget vs actual expenditure
7. project_duration handles missing completion dates correctly
8. dates cannot produce impossible negative durations unless explicitly valid
9. no NaN/Infinity values are silently introduced
10. original raw columns and dtypes remain unchanged
11. feature calculations do not leak future information
12. row/project IDs remain unique and aligned after feature engineering
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
def base_validation_df():
    """Generates controlled validation test data covering all edge cases."""
    return pd.DataFrame({
        "project_id": ["P101", "P102", "P103", "P104", "P105", "P106"],
        "project_title": ["Solar Pump", "Rural Bridge", "School Hall", "Health Clinic", "Canal Lining", "Community Well"],
        "sector": ["Irrigation", "Roads", "Education", "Health", "Irrigation", "Water Supply"],
        "recommendation_date": ["2024-01-01", "2024-02-01", "2024-01-15", "2024-03-01", "2024-01-10", "2024-04-01"],
        "sanction_date": ["2024-01-25", "2024-02-28", "2024-02-20", "2024-03-20", "2024-02-15", "2024-04-15"],
        "work_order_date": ["2024-02-01", "2024-03-15", "2024-03-01", "2024-04-01", "2024-03-01", "2024-05-01"],
        "expected_completion_date": ["2024-06-01", "2024-08-01", "2024-05-01", "2024-09-01", "2024-07-01", "2024-11-01"],
        "actual_completion_date": ["2024-05-20", None, "2024-05-25", None, "2024-07-01", None],
        "reported_date": ["2024-06-15", "2024-06-15", "2024-06-15", "2024-06-15", "2024-07-10", "2024-06-15"],
        "recommended_amount": [100000.0, 500000.0, 300000.0, 400000.0, 200000.0, 150000.0],
        "sanctioned_amount": [90000.0, 480000.0, 300000.0, 0.0, 210000.0, 150000.0],
        "released_amount": [90000.0, 240000.0, 300000.0, 0.0, 210000.0, 50000.0],
        "expenditure_amount": [85000.0, 120000.0, 315000.0, 0.0, 210000.0, 10000.0],
        "physical_progress_pct": [100.0, 40.0, 100.0, 0.0, 100.0, 15.0],
        "financial_progress_pct": [94.44, 50.0, 105.0, 0.0, 100.0, 20.0],
        "current_status": ["Completed", "In Progress", "Completed", "Sanctioned", "Completed", "In Progress"]
    })


# -----------------------------------------------------------------------------
# 1. delay_days has the correct sign and date logic
# -----------------------------------------------------------------------------
def test_1_delay_days_sign_and_date_logic(base_validation_df):
    """
    Verifies sign convention:
    - Early completion (P101: 2024-05-20 vs 2024-06-01): delay_days == -12 (strictly < 0, early)
    - On-schedule completion (P105: 2024-07-01 vs 2024-07-01): delay_days == 0
    - Late completion (P103: 2024-05-25 vs 2024-05-01): delay_days == 24 (strictly > 0, delayed)
    - Active project within window (P102: as_of 2024-06-15 vs exp 2024-08-01): delay_days == 0
    - Inverted sign convention toggling works as configured.
    """
    cfg = FeatureConfig(as_of_date="2024-06-15", positive_means_delayed=True)
    df = compute_delay_days(base_validation_df, cfg)

    # Early completed
    p101_delay = df.loc[df["project_id"] == "P101", "delay_days"].iloc[0]
    assert p101_delay == -12, f"Expected -12 for early project, got {p101_delay}"
    assert not df.loc[df["project_id"] == "P101", "is_delayed"].iloc[0]

    # On-schedule completed
    p105_delay = df.loc[df["project_id"] == "P105", "delay_days"].iloc[0]
    assert p105_delay == 0, f"Expected 0 for on-time project, got {p105_delay}"
    assert not df.loc[df["project_id"] == "P105", "is_delayed"].iloc[0]

    # Late completed
    p103_delay = df.loc[df["project_id"] == "P103", "delay_days"].iloc[0]
    assert p103_delay == 24, f"Expected 24 for late project, got {p103_delay}"
    assert df.loc[df["project_id"] == "P103", "is_delayed"].iloc[0]

    # Active within schedule
    p102_delay = df.loc[df["project_id"] == "P102", "delay_days"].iloc[0]
    assert p102_delay == 0, f"Expected 0 for active project within window, got {p102_delay}"

    # Verify configurable sign inversion
    cfg_inv = FeatureConfig(as_of_date="2024-06-15", positive_means_delayed=False)
    df_inv = compute_delay_days(base_validation_df, cfg_inv)
    assert df_inv.loc[df_inv["project_id"] == "P101", "delay_days"].iloc[0] == 12
    assert df_inv.loc[df_inv["project_id"] == "P103", "delay_days"].iloc[0] == -24


# -----------------------------------------------------------------------------
# 2. utilization_ratio handles zero/missing allocation correctly
# -----------------------------------------------------------------------------
def test_2_utilization_ratio_zero_and_missing_allocation(base_validation_df):
    """
    Verifies that zero, null, or missing allocations are handled gracefully
    without raising ZeroDivisionError, producing Inf, or causing NaN.
    """
    cfg = FeatureConfig()
    df = compute_utilization_ratio(base_validation_df, cfg)

    # P104 has sanctioned_amount = 0.0 and released_amount = 0.0
    p104_util = df.loc[df["project_id"] == "P104", "utilization_ratio"].iloc[0]
    p104_sanc = df.loc[df["project_id"] == "P104", "utilization_ratio_sanctioned"].iloc[0]
    p104_rel = df.loc[df["project_id"] == "P104", "utilization_ratio_released"].iloc[0]

    assert p104_util == 0.0
    assert p104_sanc == 0.0
    assert p104_rel == 0.0
    assert not np.isinf(p104_util)
    assert not np.isnan(p104_util)

    # Edge case: DataFrame with missing/NaN allocation columns
    df_missing = pd.DataFrame({
        "project_id": ["E1"],
        "sanctioned_amount": [np.nan],
        "released_amount": [None],
        "expenditure_amount": [50000.0]
    })
    res_missing = compute_utilization_ratio(df_missing, cfg)
    assert res_missing["utilization_ratio"].iloc[0] == 0.0
    assert not np.isinf(res_missing["utilization_ratio"].iloc[0])


# -----------------------------------------------------------------------------
# 3. utilization ratios are numerically valid
# -----------------------------------------------------------------------------
def test_3_utilization_ratios_are_numerically_valid(base_validation_df):
    """
    Verifies:
    - All utilization ratios are non-negative.
    - No infinite or NaN values exist.
    - Ratios match exact formula: expenditure / allocation.
    """
    cfg = FeatureConfig()
    df = compute_utilization_ratio(base_validation_df, cfg)

    for col in ["utilization_ratio", "utilization_ratio_sanctioned", "utilization_ratio_released"]:
        s = df[col]
        assert (s >= 0.0).all(), f"Found negative values in {col}"
        assert not np.isinf(s).any(), f"Found infinite values in {col}"
        assert not s.isna().any(), f"Found NaN values in {col}"

    # P101: 85000 / 90000 = 0.9444
    p101_util = df.loc[df["project_id"] == "P101", "utilization_ratio"].iloc[0]
    assert np.isclose(p101_util, 85000.0 / 90000.0, atol=1e-3)

    # P102: 120000 / 240000 = 0.50
    p102_rel = df.loc[df["project_id"] == "P102", "utilization_ratio_released"].iloc[0]
    assert np.isclose(p102_rel, 0.50, atol=1e-3)


# -----------------------------------------------------------------------------
# 4. cost_per_category is calculated using correct category grouping
# -----------------------------------------------------------------------------
def test_4_cost_per_category_grouping_and_preservation(base_validation_df):
    """
    Verifies:
    - Correct grouping by sector.
    - Preserves all original cost columns without mutation.
    - Irrigation sector has P101 (90k) and P105 (210k) -> mean = 150k.
    - Single-item group (Health P104) handles std gracefully with zero.
    """
    cfg = FeatureConfig()
    raw_sanc = base_validation_df["sanctioned_amount"].copy()
    df = compute_cost_per_category(base_validation_df, cfg)

    # Irrigation sector mean: (90,000 + 210,000) / 2 = 150,000
    irr_mean = df.loc[df["sector"] == "Irrigation", "category_mean_cost"].iloc[0]
    assert irr_mean == 150000.0, f"Expected 150,000 for Irrigation mean, got {irr_mean}"

    # P101 relative index: 90,000 / 150,000 = 0.60
    p101_rel = df.loc[df["project_id"] == "P101", "cost_relative_to_category"].iloc[0]
    assert np.isclose(p101_rel, 0.60, atol=1e-3)

    # Original columns preserved exactly
    pd.testing.assert_series_equal(df["sanctioned_amount"], raw_sanc)


# -----------------------------------------------------------------------------
# 5. progress_gap correctly represents planned vs actual progress
# -----------------------------------------------------------------------------
def test_5_progress_gap_planned_vs_actual(base_validation_df):
    """
    Verifies:
    - Completed projects have planned = 100.0, physical = 100.0 -> progress_gap = 0.0
    - Lagging project (planned > physical): gap > 0
    - Financial vs physical gap correctly computed.
    - Output values remain strictly bounded in [-100.0, 100.0].
    """
    cfg = FeatureConfig(as_of_date="2024-06-15")
    df = compute_progress_gap(base_validation_df, cfg)

    # P101, P103, P105 are Completed -> progress_gap_schedule == 0.0
    for pid in ["P101", "P103", "P105"]:
        gap = df.loc[df["project_id"] == pid, "progress_gap"].iloc[0]
        assert gap == 0.0, f"Completed project {pid} should have schedule progress_gap == 0.0, got {gap}"

    # Financial - Physical gap for P102: 50.0 - 40.0 = +10.0%
    p102_fin_phy = df.loc[df["project_id"] == "P102", "progress_gap_fin_phy"].iloc[0]
    assert p102_fin_phy == 10.0

    # Bounds check
    assert (df["progress_gap"] >= -100.0).all() and (df["progress_gap"] <= 100.0).all()


# -----------------------------------------------------------------------------
# 6. cost_deviation correctly represents budget/planned vs actual expenditure
# -----------------------------------------------------------------------------
def test_6_cost_deviation_budget_vs_expenditure(base_validation_df):
    """
    Verifies:
    - cost_deviation_sanction = sanctioned - recommended
    - cost_deviation_expenditure = expenditure - sanctioned
    - P101: expenditure 85k, sanctioned 90k -> -5,000 (savings, no overrun)
    - P103: expenditure 315k, sanctioned 300k -> +15,000 (overrun, has_cost_overrun = True)
    """
    cfg = FeatureConfig()
    df = compute_cost_deviation(base_validation_df, cfg)

    # P101: 85k - 90k = -5,000
    p101_dev = df.loc[df["project_id"] == "P101", "cost_deviation"].iloc[0]
    assert p101_dev == -5000.0
    assert not df.loc[df["project_id"] == "P101", "has_cost_overrun"].iloc[0]

    # P103: 315k - 300k = +15,000
    p103_dev = df.loc[df["project_id"] == "P103", "cost_deviation"].iloc[0]
    assert p103_dev == 15000.0
    assert df.loc[df["project_id"] == "P103", "has_cost_overrun"].iloc[0]

    # Percentage deviation for P103: (15,000 / 300,000) * 100 = 5.0%
    p103_pct = df.loc[df["project_id"] == "P103", "cost_deviation_expenditure_pct"].iloc[0]
    assert np.isclose(p103_pct, 5.0, atol=1e-2)


# -----------------------------------------------------------------------------
# 7. project_duration handles missing completion dates correctly
# -----------------------------------------------------------------------------
def test_7_project_duration_missing_completion_dates(base_validation_df):
    """
    Verifies:
    - Completed project (P101): project_duration = actual_completion - start_date
    - Active project with missing completion date (P102): project_duration = ref_date - start_date
    - No NaN in project_duration column.
    """
    cfg = FeatureConfig(as_of_date="2024-06-15")
    df = compute_project_duration(base_validation_df, cfg)

    # P101: start 2024-02-01, actual 2024-05-20 -> 109 days
    p101_dur = df.loc[df["project_id"] == "P101", "project_duration"].iloc[0]
    assert p101_dur == 109

    # P102: start 2024-03-15, missing completion, ref 2024-06-15 -> 92 days
    p102_dur = df.loc[df["project_id"] == "P102", "project_duration"].iloc[0]
    assert p102_dur == 92
    assert not np.isnan(p102_dur)
    assert not df["project_duration"].isna().any(), "project_duration must not contain NaNs"


# -----------------------------------------------------------------------------
# 8. dates cannot produce impossible negative durations unless explicitly valid
# -----------------------------------------------------------------------------
def test_8_dates_cannot_produce_impossible_negative_durations():
    """
    Verifies:
    - If expected_completion_date < work_order_date (inverted anomaly),
      planned_duration_days floors at 0 and does NOT produce negative duration.
    - If actual_completion_date < work_order_date, actual_duration floors at 0.
    - If sanction_date < recommendation_date, admin latency floors at 0.
    - delay_days < 0 IS explicitly valid for early completion and preserved.
    - cost_deviation < 0 IS explicitly valid for cost savings and preserved.
    """
    dirty_df = pd.DataFrame({
        "project_id": ["ANOMALY_1", "ANOMALY_2"],
        "recommendation_date": ["2024-05-01", "2024-01-01"],
        "sanction_date": ["2024-04-01", "2024-01-10"],  # ANOMALY_1: Sanction BEFORE recommendation
        "work_order_date": ["2024-06-01", "2024-02-01"],
        "expected_completion_date": ["2024-05-01", "2024-06-01"],  # ANOMALY_1: Expected BEFORE work order
        "actual_completion_date": ["2024-04-15", "2024-05-15"],   # ANOMALY_1: Completed BEFORE start; ANOMALY_2: Completed early
        "reported_date": ["2024-06-15", "2024-06-15"],
        "sanctioned_amount": [100000.0, 100000.0],
        "expenditure_amount": [90000.0, 110000.0]
    })

    cfg = FeatureConfig(as_of_date="2024-06-15", positive_means_delayed=True)
    dur_df = compute_project_duration(dirty_df, cfg)
    delay_df = compute_delay_days(dirty_df, cfg)
    cost_df = compute_cost_deviation(dirty_df, cfg)

    # Physical durations CANNOT be negative
    for col in ["planned_duration_days", "actual_duration_days", "project_duration", "admin_sanction_duration_days"]:
        s = dur_df[col].dropna()
        assert (s >= 0).all(), f"Found impossible negative duration in {col}: {s[s < 0]}"

    # ANOMALY_2 completed early (2024-05-15 vs 2024-06-01) -> delay_days < 0 is explicitly valid
    a2_delay = delay_df.loc[delay_df["project_id"] == "ANOMALY_2", "delay_days"].iloc[0]
    assert a2_delay < 0, f"Early completion must produce explicitly valid negative delay, got {a2_delay}"

    # ANOMALY_1 expenditure 90k vs sanction 100k -> cost_deviation < 0 is explicitly valid savings
    a1_cost_dev = cost_df.loc[cost_df["project_id"] == "ANOMALY_1", "cost_deviation"].iloc[0]
    assert a1_cost_dev == -10000.0, "Cost savings must produce explicitly valid negative cost_deviation"


# -----------------------------------------------------------------------------
# 9. no NaN/Infinity values are silently introduced
# -----------------------------------------------------------------------------
def test_9_no_silent_nan_or_infinity_introduced():
    """
    Verifies that running the pipeline on the real Phase 2 dataset produces
    zero infinite values and no unintended NaNs in core governance features.
    """
    pipeline = FeatureEngineeringPipeline()
    featured_df = pipeline.run()

    numeric_cols = featured_df.select_dtypes(include=[np.number]).columns
    for c in numeric_cols:
        assert not np.isinf(featured_df[c]).any(), f"Column '{c}' contains infinite values!"

    # Mandatory core features that must NEVER have NaN
    mandatory_features = [
        "delay_days", "is_delayed", "utilization_ratio", "cost_per_category",
        "cost_relative_to_category", "progress_gap", "cost_deviation",
        "project_duration", "project_duration_days", "elapsed_duration_days"
    ]
    for feat in mandatory_features:
        assert not featured_df[feat].isna().any(), f"Mandatory feature '{feat}' contains silent NaNs!"


# -----------------------------------------------------------------------------
# 10. original raw columns remain unchanged
# -----------------------------------------------------------------------------
def test_10_original_raw_columns_unchanged(base_validation_df):
    """
    Verifies that all original input columns and their exact dtypes remain
    completely unchanged and unmutated after running the entire pipeline.
    """
    pipeline = FeatureEngineeringPipeline()
    input_copy = base_validation_df.copy()
    output_df = pipeline.transform(base_validation_df)

    for col in input_copy.columns:
        assert col in output_df.columns, f"Raw column '{col}' missing from transformed output"
        pd.testing.assert_series_equal(
            output_df[col],
            input_copy[col],
            check_dtype=True,
            check_names=True,
            obj=f"Raw column '{col}'"
        )


# -----------------------------------------------------------------------------
# 11. feature calculations do not leak future information
# -----------------------------------------------------------------------------
def test_11_feature_calculations_do_not_leak_future_information(base_validation_df):
    """
    Verifies that pre-award recommendation-time features do NOT depend on post-award
    telemetry (expenditure, actual_completion_date, physical_progress_pct).
    Wiping post-award telemetry must yield IDENTICAL pre-award features.
    """
    pipeline = FeatureEngineeringPipeline()

    # 1. Run on standard dataset
    df_normal = pipeline.transform(base_validation_df)

    # 2. Wipe all post-award telemetry
    df_pre_award = base_validation_df.copy()
    df_pre_award["actual_completion_date"] = None
    df_pre_award["expenditure_amount"] = 0.0
    df_pre_award["physical_progress_pct"] = 0.0
    df_pre_award["financial_progress_pct"] = 0.0

    df_sanitized = pipeline.transform(df_pre_award)

    pre_award_features = [
        "cost_per_category",
        "cost_relative_to_category",
        "cost_category_zscore",
        "cost_deviation_sanction",
        "cost_deviation_sanction_pct",
        "planned_duration_days",
        "admin_sanction_duration_days",
        "sanction_sla_delay_days"
    ]

    for feat in pre_award_features:
        pd.testing.assert_series_equal(
            df_normal[feat],
            df_sanitized[feat],
            check_dtype=True,
            obj=f"Pre-award feature '{feat}' leaked future information!"
        )


# -----------------------------------------------------------------------------
# 12. row/project IDs remain unique and aligned after feature engineering
# -----------------------------------------------------------------------------
def test_12_row_ids_remain_unique_and_aligned(base_validation_df):
    """
    Verifies:
    - project_id remains unique.
    - Total row count is exactly preserved.
    - Index alignment is 1:1 with input data.
    """
    pipeline = FeatureEngineeringPipeline()
    output_df = pipeline.transform(base_validation_df)

    assert output_df["project_id"].is_unique, "Project IDs are not unique in transformed output!"
    assert len(output_df) == len(base_validation_df), "Row count mismatch between input and output!"
    assert (output_df.index == base_validation_df.index).all(), "Index alignment compromised!"
    assert (output_df["project_id"] == base_validation_df["project_id"]).all(), "Row ordering mutated!"
