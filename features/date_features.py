"""
features/date_features.py
=============================================================================
Standardized date manipulation and derived timeline metrics:
1. delay_days (with explicit sign convention)
2. project_duration (planned, actual, elapsed, and administrative)
3. sanction SLA latency and breach metrics
=============================================================================
"""

import pandas as pd
import numpy as np
from datetime import date
from typing import Optional, List

from features.config import FeatureConfig


def _get_dt_series(df: pd.DataFrame, col: Optional[str]) -> pd.Series:
    """
    Safely converts a DataFrame column to a pandas DatetimeSeries without mutating the original column.
    """
    if col is not None and col in df.columns:
        return pd.to_datetime(df[col], errors="coerce")
    return pd.Series(pd.NaT, index=df.index)


def compute_delay_days(
    df: pd.DataFrame,
    config: Optional[FeatureConfig] = None
) -> pd.DataFrame:
    """
    Calculates project execution delay in days with a documented sign convention.
    Strictly preserves all raw/original columns and their types without mutation.

    Sign Convention:
        When `positive_means_delayed = True` (Default):
            - delay_days > 0: Project is delayed / overdue.
            - delay_days == 0: Project completed exactly on schedule, or active project on track.
            - delay_days < 0: Project completed early ahead of the planned milestone.

    Formula:
        - Completed Projects:
            delta = actual_completion_date - expected_completion_date
        - Active / Stalled Projects:
            If as_of_date > expected_completion_date:
                delta = as_of_date - expected_completion_date
            Else:
                delta = 0 (project is still within scheduled delivery window)

        If the project table includes an inspected `days_delayed` field from engineering
        inspections, it is integrated as the primary telemetry signal if positive.

    Risk Engine Safety:
        - In-Flight Surveillance: SAFE. Essential for escalating stalled or slipping works.
        - Pre-Sanction Prediction: UNSAFE (Target Leakage). Cannot be used as an input
          when predicting project feasibility at initial MP recommendation.

    Returns:
        DataFrame with new columns:
        - `delay_days`: integer/float delay in calendar days.
        - `is_delayed`: boolean indicator whether project experienced execution delay.
        - `sanction_sla_delay_days`: days taken for sanction beyond the 75-day statutory SLA.
    """
    cfg = config or FeatureConfig()
    df = df.copy()

    # Required date columns (converted to separate datetime series without mutating df)
    rec_dt = _get_dt_series(df, cfg.recommendation_date_col)
    sanc_dt = _get_dt_series(df, cfg.sanction_date_col)
    exp_dt = _get_dt_series(df, cfg.expected_completion_date_col)
    act_dt = _get_dt_series(df, cfg.actual_completion_date_col)
    rep_dt = _get_dt_series(df, cfg.reported_date_col)

    insp_delay_col = cfg.days_delayed_col

    # Determine reference date for ongoing works
    if cfg.as_of_date is not None:
        ref_date = pd.to_datetime(cfg.as_of_date)
    elif rep_dt.notna().any():
        ref_date = rep_dt.fillna(pd.to_datetime(date.today()))
    else:
        ref_date = pd.to_datetime(date.today())

    # 1. Calculate completion schedule delta for completed works
    has_actual = act_dt.notna()
    has_expected = exp_dt.notna()

    completed_mask = has_actual & has_expected
    delta_completed = (act_dt[completed_mask] - exp_dt[completed_mask]).dt.days

    # 2. Calculate schedule slippage for active / ongoing works
    ongoing_mask = (~has_actual) & has_expected
    if isinstance(ref_date, pd.Series):
        ongoing_delta = (ref_date[ongoing_mask] - exp_dt[ongoing_mask]).dt.days
    else:
        ongoing_delta = (ref_date - exp_dt[ongoing_mask]).dt.days

    # Negative ongoing delta means the project is not yet due -> 0 delay
    ongoing_delta = np.maximum(0, ongoing_delta)

    # Combine into derived delay series
    derived_delay = pd.Series(0, index=df.index, dtype=float)
    derived_delay.loc[completed_mask] = delta_completed
    derived_delay.loc[ongoing_mask] = ongoing_delta

    # Incorporate inspection telemetry if available
    if insp_delay_col in df.columns:
        valid_insp = df[insp_delay_col].notna() & (pd.to_numeric(df[insp_delay_col], errors="coerce") > 0)
        derived_delay = np.where(valid_insp, pd.to_numeric(df[insp_delay_col], errors="coerce"), derived_delay)

    # Adjust for inverted sign convention if requested
    if not cfg.positive_means_delayed:
        derived_delay = -derived_delay

    df["delay_days"] = derived_delay.astype(int)
    df["is_delayed"] = (derived_delay > 0)

    # 3. Administrative Sanction SLA Delay (Statutory 75 days under Guidelines Para 3.5)
    if sanc_dt.notna().any() and rec_dt.notna().any():
        sanc_latency = (sanc_dt - rec_dt).dt.days
        df["sanction_sla_delay_days"] = np.maximum(0, sanc_latency - cfg.sanction_sla_days).fillna(0).astype(int)
    else:
        df["sanction_sla_delay_days"] = 0

    return df


def compute_project_duration(
    df: pd.DataFrame,
    config: Optional[FeatureConfig] = None
) -> pd.DataFrame:
    """
    Computes standardized lifecycle duration metrics across project stages.
    Strictly preserves all raw/original columns and their types without mutation.

    Derived Columns:
        - `planned_duration_days`: Contractual scheduled execution days
            (expected_completion_date - work_order_date).
        - `actual_duration_days`: Realized execution days for completed works
            (actual_completion_date - work_order_date). NaN for active projects.
        - `elapsed_duration_days`: Calendar days elapsed from work order to reference date.
        - `admin_sanction_duration_days`: Administrative vetting days (sanction_date - recommendation_date).
        - `tendering_duration_days`: Procurement days (work_order_date - sanction_date).
        - `total_planned_lifecycle_days`: Total timeline (expected_completion_date - recommendation_date).

    Safety & Leakage Prevention:
        - `planned_duration_days` is established at contract award and safe for baseline modeling.
        - `actual_duration_days` is strictly restricted to completed works to avoid survival bias.
    """
    cfg = config or FeatureConfig()
    df = df.copy()

    rec_dt = _get_dt_series(df, cfg.recommendation_date_col)
    sanc_dt = _get_dt_series(df, cfg.sanction_date_col)
    wo_dt = _get_dt_series(df, cfg.work_order_date_col)
    exp_dt = _get_dt_series(df, cfg.expected_completion_date_col)
    act_dt = _get_dt_series(df, cfg.actual_completion_date_col)
    rep_dt = _get_dt_series(df, cfg.reported_date_col)

    # Reference date for active works
    if cfg.as_of_date is not None:
        ref_date = pd.to_datetime(cfg.as_of_date)
    elif rep_dt.notna().any():
        ref_date = rep_dt.fillna(pd.to_datetime(date.today()))
    else:
        ref_date = pd.to_datetime(date.today())

    # Determine start date: work_order_date -> fallback to sanction_date -> fallback to recommendation_date
    start_dt = wo_dt.copy()
    missing_start = start_dt.isna()
    start_dt[missing_start] = sanc_dt[missing_start]
    missing_start2 = start_dt.isna()
    start_dt[missing_start2] = rec_dt[missing_start2]

    # 1. Planned Contractual Execution Duration (guarded against impossible negative values)
    if exp_dt.notna().any() and start_dt.notna().any():
        planned = (exp_dt - start_dt).dt.days
        # Physical duration cannot be negative; clamp invalid inverted dates to 0
        df["planned_duration_days"] = np.maximum(0, planned)
    else:
        df["planned_duration_days"] = np.nan

    # 2. Actual Execution Duration (Completed projects only; guarded against impossible negative values)
    if act_dt.notna().any() and start_dt.notna().any():
        actual = (act_dt - start_dt).dt.days
        df["actual_duration_days"] = np.maximum(0, actual)
    else:
        df["actual_duration_days"] = np.nan

    # 3. Primary project_duration: actual/current duration between project start and completion/current date
    # Handles missing completion dates safely by measuring elapsed duration to reference date for ongoing works
    end_dt = act_dt.copy()
    missing_completion = end_dt.isna()
    if isinstance(ref_date, pd.Series):
        end_dt[missing_completion] = ref_date[missing_completion]
    else:
        end_dt[missing_completion] = ref_date

    has_both = start_dt.notna() & end_dt.notna()
    duration_series = pd.Series(0, index=df.index, dtype=int)
    if has_both.any():
        raw_dur = (end_dt[has_both] - start_dt[has_both]).dt.days
        # Physical duration between start and end cannot be negative; clamp to 0
        duration_series[has_both] = np.maximum(0, raw_dur).fillna(0).astype(int)

    df["project_duration"] = duration_series
    df["project_duration_days"] = duration_series

    # 4. Elapsed Duration to Date (Active ongoing projects)
    if start_dt.notna().any():
        if isinstance(ref_date, pd.Series):
            elapsed = (ref_date - start_dt).dt.days
        else:
            elapsed = (ref_date - start_dt).dt.days
        df["elapsed_duration_days"] = np.maximum(0, elapsed.fillna(0)).astype(int)
    else:
        df["elapsed_duration_days"] = 0

    # 5. Administrative Sanction Latency (guarded against negative dates)
    if sanc_dt.notna().any() and rec_dt.notna().any():
        df["admin_sanction_duration_days"] = np.maximum(0, (sanc_dt - rec_dt).dt.days)
    else:
        df["admin_sanction_duration_days"] = np.nan

    # 6. Tendering / Procurement Latency (guarded against negative dates)
    if wo_dt.notna().any() and sanc_dt.notna().any():
        df["tendering_duration_days"] = np.maximum(0, (wo_dt - sanc_dt).dt.days)
    else:
        df["tendering_duration_days"] = np.nan

    # 7. Total Planned Lifecycle (Recommendation to Expected Completion)
    if exp_dt.notna().any() and rec_dt.notna().any():
        df["total_planned_lifecycle_days"] = np.maximum(0, (exp_dt - rec_dt).dt.days)
    else:
        df["total_planned_lifecycle_days"] = np.nan

    return df
