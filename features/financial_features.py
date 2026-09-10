"""
features/financial_features.py
=============================================================================
Financial ratio and variance engineering:
1. utilization_ratio (expenditure divided by sanctioned / released funds)
2. cost_deviation (sanction vs recommendation, expenditure vs sanction)
=============================================================================
"""

import pandas as pd
import numpy as np
from typing import Optional

from features.config import FeatureConfig


def compute_utilization_ratio(
    df: pd.DataFrame,
    config: Optional[FeatureConfig] = None
) -> pd.DataFrame:
    """
    Computes fund utilization ratios safely handling zero denominators and null values.

    Formulas:
        1. Sanction Utilization Ratio:
            utilization_ratio_sanctioned = expenditure_amount / sanctioned_amount
            (Measures what proportion of the approved allocation has been expended).

        2. Disbursed Release Utilization Ratio:
            utilization_ratio_released = expenditure_amount / released_amount
            (Measures fund absorption of actual cash disbursed to executing agency).

    Safety & Edge Cases:
        - If denominator is 0, NaN, or null: Returns 0.0.
        - Negative expenditures/allocations are clamped to 0.0.
        - Preserves all original financial columns intact.

    Risk Engine Safety:
        - In-Flight Surveillance: SAFE. Highly informative for detecting stalled works.
        - Pre-Sanction Prediction: UNSAFE (Lookahead Leakage). At recommendation,
          expenditures have not occurred yet.
    """
    cfg = config or FeatureConfig()
    df = df.copy()

    exp_col = cfg.expenditure_col
    sanc_col = cfg.cost_col
    rel_col = cfg.released_cost_col

    # Fill nulls with 0 for computation while preserving original columns
    exp = pd.to_numeric(df[exp_col], errors="coerce").fillna(0.0).clip(lower=0.0) if exp_col in df.columns else pd.Series(0.0, index=df.index)
    sanc = pd.to_numeric(df[sanc_col], errors="coerce").fillna(0.0).clip(lower=0.0) if sanc_col in df.columns else pd.Series(0.0, index=df.index)
    rel = pd.to_numeric(df[rel_col], errors="coerce").fillna(0.0).clip(lower=0.0) if rel_col in df.columns else pd.Series(0.0, index=df.index)

    # 1. Utilization against sanctioned ceiling
    sanc_valid = sanc > 0
    util_sanc = np.where(sanc_valid, exp / np.maximum(sanc, cfg.epsilon), 0.0)
    df["utilization_ratio_sanctioned"] = np.round(util_sanc, 4)

    # 2. Utilization against released cash installments
    rel_valid = rel > 0
    util_rel = np.where(rel_valid, exp / np.maximum(rel, cfg.epsilon), 0.0)
    df["utilization_ratio_released"] = np.round(util_rel, 4)

    # Primary default utilization ratio (against released funds if available, else sanctioned)
    df["utilization_ratio"] = np.where(rel_valid, df["utilization_ratio_released"], df["utilization_ratio_sanctioned"])

    return df


def compute_cost_deviation(
    df: pd.DataFrame,
    config: Optional[FeatureConfig] = None
) -> pd.DataFrame:
    """
    Computes absolute and percentage variances across budgetary stages.

    Formulas:
        1. Sanction Scope Deviation (Technical / Administrative Vetting Delta):
            cost_deviation_sanction = sanctioned_amount - recommended_amount
            cost_deviation_sanction_pct = (sanctioned - recommended) / recommended * 100
            (Negative value means administrative authority pruned project budget).

        2. Execution Cost Overrun (Actual vs. Sanctioned Budget):
            cost_deviation_expenditure = expenditure_amount - sanctioned_amount
            cost_deviation_expenditure_pct = (expenditure - sanctioned) / sanctioned * 100
            (Positive value indicates cost overrun beyond sanctioned ceiling).

        3. Disbursement Gap:
            unreleased_allocation = sanctioned_amount - released_amount

    Risk Engine Safety:
        - `cost_deviation_sanction` is established at sanction before construction begins:
          SAFE for pre-construction risk estimation.
        - `cost_deviation_expenditure` is an execution telemetry metric:
          SAFE for in-flight escalation; UNSAFE as feature for predicting cost overruns.
    """
    cfg = config or FeatureConfig()
    df = df.copy()

    rec_col = cfg.recommended_cost_col
    sanc_col = cfg.cost_col
    rel_col = cfg.released_cost_col
    exp_col = cfg.expenditure_col

    rec = pd.to_numeric(df[rec_col], errors="coerce").fillna(0.0) if rec_col in df.columns else pd.Series(0.0, index=df.index)
    sanc = pd.to_numeric(df[sanc_col], errors="coerce").fillna(0.0) if sanc_col in df.columns else pd.Series(0.0, index=df.index)
    rel = pd.to_numeric(df[rel_col], errors="coerce").fillna(0.0) if rel_col in df.columns else pd.Series(0.0, index=df.index)
    exp = pd.to_numeric(df[exp_col], errors="coerce").fillna(0.0) if exp_col in df.columns else pd.Series(0.0, index=df.index)

    # 1. Sanction vs Recommendation
    dev_sanction = sanc - rec
    rec_valid = rec > 0
    dev_sanction_pct = np.where(rec_valid, (dev_sanction / np.maximum(rec, cfg.epsilon)) * 100.0, 0.0)

    df["cost_deviation_sanction"] = np.round(dev_sanction, 2)
    df["cost_deviation_sanction_pct"] = np.round(dev_sanction_pct, 2)

    # 2. Expenditure vs Sanction (Cost Overrun)
    dev_exp = exp - sanc
    sanc_valid = sanc > 0
    dev_exp_pct = np.where(sanc_valid, (dev_exp / np.maximum(sanc, cfg.epsilon)) * 100.0, 0.0)

    df["cost_deviation_expenditure"] = np.round(dev_exp, 2)
    df["cost_deviation_expenditure_pct"] = np.round(dev_exp_pct, 2)
    df["cost_deviation"] = df["cost_deviation_expenditure"]  # Default alias
    df["has_cost_overrun"] = (df["cost_deviation_expenditure"] > 0)

    # 3. Unreleased Allocation
    df["unreleased_allocation"] = np.maximum(0.0, sanc - rel).round(2)

    return df
