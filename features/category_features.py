"""
features/category_features.py
=============================================================================
Categorical cost benchmarking and normalization:
1. cost_per_category (sector-level mean, median, min, max, count)
2. cost_relative_to_category (project cost normalized by sector benchmark)
3. cost_category_zscore (standard deviations from category mean)
=============================================================================
"""

import pandas as pd
import numpy as np
from typing import Optional, List

from features.config import FeatureConfig


def compute_cost_per_category(
    df: pd.DataFrame,
    config: Optional[FeatureConfig] = None,
    group_col: Optional[str] = None,
    cost_col: Optional[str] = None
) -> pd.DataFrame:
    """
    Computes statistical cost benchmarks grouped by developmental category / sector,
    and normalizes individual project costs against their peer groups.

    Formulas:
        1. Category Baseline Metrics:
            category_mean_cost = MEAN(cost) per category
            category_median_cost = MEDIAN(cost) per category
            category_std_cost = STD(cost) per category (0.0 if group size == 1)

        2. Relative Category Cost Index:
            cost_relative_to_category = project_cost / category_mean_cost
            - Ratio > 1.0: Project budget is higher than the category norm.
            - Ratio == 1.0: Project matches exact category average.
            - Ratio < 1.0: Project is more economical than category norm.

        3. Category Cost Z-Score:
            cost_category_zscore = (project_cost - category_mean_cost) / (category_std_cost + epsilon)

    Preservation Guarantee:
        - 100% of original cost columns (recommended, sanctioned, released, expenditure)
          are strictly preserved without modification.

    Risk Engine Safety:
        - HIGHLY SAFE: Normative benchmarking without target leakage.
        - Safe to use at MP recommendation time, sanction vetting, and audit surveillance.
    """
    cfg = config or FeatureConfig()
    df = df.copy()

    cat_col = group_col or cfg.category_col
    cost_name = cost_col or cfg.cost_col

    # Ensure category column exists and sanitize missing strings
    if cat_col not in df.columns:
        cat_series = pd.Series("All Sectors", index=df.index)
    else:
        cat_series = df[cat_col].fillna("Uncategorized").astype(str).str.strip()

    # Determine cost values (prioritize sanctioned, fallback to recommended)
    if cost_name in df.columns:
        cost_series = pd.to_numeric(df[cost_name], errors="coerce")
    else:
        cost_series = pd.Series(np.nan, index=df.index)

    if cfg.recommended_cost_col in df.columns:
        rec_series = pd.to_numeric(df[cfg.recommended_cost_col], errors="coerce")
        effective_cost = cost_series.fillna(rec_series).fillna(0.0).clip(lower=0.0)
    else:
        effective_cost = cost_series.fillna(0.0).clip(lower=0.0)

    # Compute group aggregates using transform to maintain DataFrame alignment
    grp = effective_cost.groupby(cat_series)

    mean_cost = grp.transform("mean")
    median_cost = grp.transform("median")
    std_cost = grp.transform("std").fillna(0.0)
    min_cost = grp.transform("min")
    max_cost = grp.transform("max")
    count_projects = grp.transform("count")

    # Relative normalized cost index
    safe_mean = np.maximum(mean_cost, cfg.epsilon)
    rel_cost = effective_cost / safe_mean

    # Z-Score
    safe_std = np.maximum(std_cost, cfg.epsilon)
    cost_zscore = (effective_cost - mean_cost) / safe_std
    cost_zscore = np.where(std_cost < cfg.epsilon, 0.0, cost_zscore)

    # Assign derived columns
    df["category_mean_cost"] = np.round(mean_cost, 2)
    df["category_median_cost"] = np.round(median_cost, 2)
    df["category_std_cost"] = np.round(std_cost, 2)
    df["category_min_cost"] = np.round(min_cost, 2)
    df["category_max_cost"] = np.round(max_cost, 2)
    df["category_project_count"] = count_projects.astype(int)

    # Primary aliases
    df["cost_per_category"] = df["category_mean_cost"]
    df["cost_relative_to_category"] = np.round(rel_cost, 4)
    df["cost_category_zscore"] = np.round(cost_zscore, 4)

    return df
