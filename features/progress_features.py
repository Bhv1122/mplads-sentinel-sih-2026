"""
features/progress_features.py
=============================================================================
Progress discrepancy analytics:
1. progress_gap: planned progress minus actual progress (schedule lag)
2. progress_gap_fin_phy: financial progress minus physical progress (disbursement gap)
=============================================================================
"""

import pandas as pd
import numpy as np
from datetime import date
from typing import Optional

from features.config import FeatureConfig
from features.date_features import _get_dt_series


def compute_progress_gap(
    df: pd.DataFrame,
    config: Optional[FeatureConfig] = None
) -> pd.DataFrame:
    """
    Computes progress gap metrics comparing planned vs. actual physical execution,
    and financial disbursements vs. verified physical milestones.
    Strictly preserves all raw/original columns without mutation.

    Formulas:
        1. Schedule Progress Gap (Planned Progress minus Actual Physical Progress):
            planned_schedule_pct = (as_of_date - work_order_date) / (expected_completion_date - work_order_date) * 100
            (clamped to [0.0, 100.0])

            progress_gap_schedule = planned_schedule_pct - physical_progress_pct
            - Positive (> 0): Planned progress leads actual delivery -> Project is lagging.
            - Zero (== 0): Delivery aligns with schedule trajectory.
            - Negative (< 0): Physical delivery is ahead of elapsed schedule time.

        2. Financial-to-Physical Gap (Disbursement vs Execution):
            progress_gap_fin_phy = financial_progress_pct - physical_progress_pct
            - Positive (> 0): Funds withdrawn/billed lead on-ground completion (anomaly risk).
            - Negative (< 0): Contractor delivery leads certified fund disbursement.

    Safety & Edge Cases:
        - If work_order_date == expected_completion_date (zero duration): planned_schedule_pct is clamped to 100.0.
        - If dates are null or missing: planned_schedule_pct defaults to 0.0.
        - Physical and financial progress values are clamped to [0.0, 100.0].
        - Original telemetry fields are preserved without mutation.

    Risk Engine Safety:
        - In-Flight Monitoring: HIGH VALUE. Flagging projects where schedule lag or
          disbursement skew exceeds governance tolerance thresholds (e.g. gap > 20%).
        - Pre-Sanction Prediction: UNSAFE. Telemetry is non-existent before construction.
    """
    cfg = config or FeatureConfig()
    df = df.copy()

    wo_dt = _get_dt_series(df, cfg.work_order_date_col)
    exp_dt = _get_dt_series(df, cfg.expected_completion_date_col)
    act_dt = _get_dt_series(df, cfg.actual_completion_date_col)
    rep_dt = _get_dt_series(df, cfg.reported_date_col)

    phy_col = cfg.physical_progress_col
    fin_col = cfg.financial_progress_col

    # Reference date
    if cfg.as_of_date is not None:
        ref_date = pd.to_datetime(cfg.as_of_date)
    elif rep_dt.notna().any():
        ref_date = rep_dt.fillna(pd.to_datetime(date.today()))
    else:
        ref_date = pd.to_datetime(date.today())

    # Actual physical and financial progress series
    phy_progress = pd.to_numeric(df[phy_col], errors="coerce").fillna(0.0).clip(0.0, 100.0) if phy_col in df.columns else pd.Series(0.0, index=df.index)
    fin_progress = pd.to_numeric(df[fin_col], errors="coerce").fillna(0.0).clip(0.0, 100.0) if fin_col in df.columns else pd.Series(0.0, index=df.index)

    # 1. Planned Schedule Progress Calculation
    has_dates = wo_dt.notna() & exp_dt.notna()
    total_scheduled_days = (exp_dt - wo_dt).dt.days

    if isinstance(ref_date, pd.Series):
        days_elapsed = (ref_date - wo_dt).dt.days
    else:
        days_elapsed = (ref_date - wo_dt).dt.days

    valid_schedule = has_dates & (total_scheduled_days > 0)

    planned_schedule_pct = np.zeros(len(df), dtype=float)
    if valid_schedule.any():
        ratio = (days_elapsed[valid_schedule] / total_scheduled_days[valid_schedule]) * 100.0
        planned_schedule_pct[valid_schedule] = np.clip(ratio, 0.0, 100.0)

    # If project is officially marked Completed, planned schedule is 100%
    if act_dt.notna().any():
        completed_mask = act_dt.notna()
        planned_schedule_pct[completed_mask] = 100.0

    df["planned_schedule_pct"] = np.round(planned_schedule_pct, 2)

    # Schedule Progress Gap (Planned minus Actual)
    df["progress_gap_schedule"] = np.round(df["planned_schedule_pct"] - phy_progress, 2)
    # Primary progress_gap alias (as requested by prompt)
    df["progress_gap"] = df["progress_gap_schedule"]

    # 2. Financial-to-Physical Progress Gap
    df["progress_gap_fin_phy"] = np.round(fin_progress - phy_progress, 2)

    # Operational classification flags
    df["is_schedule_lagging"] = (df["progress_gap_schedule"] > 0)
    df["is_disbursement_skewed"] = (df["progress_gap_fin_phy"] > 15.0)

    return df
