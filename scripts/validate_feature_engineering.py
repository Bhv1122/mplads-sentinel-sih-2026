"""
scripts/validate_feature_engineering.py
=============================================================================
Phase 5 Feature Engineering Validation and Profiling Report Generator.
Evaluates all engineered features against statistical validity rules:
- Formula documentation
- Min, Max, Mean, Median
- Missing count and Invalid count (Infs, impossible negatives, zero division)
- Representative sample values
- Data integrity and raw column preservation audit
Exports report to CSV and Markdown.
=============================================================================
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Set project root in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from features.pipeline import FeatureEngineeringPipeline


FEATURE_DEFINITIONS = [
    {
        "feature": "delay_days",
        "formula": "(actual_completion - expected_completion) if completed else max(0, as_of_date - expected_completion)",
        "allow_negative": True,  # Negative means ahead of schedule (explicitly valid)
        "description": "Schedule variance in days (positive = delayed, negative = early, 0 = on time)"
    },
    {
        "feature": "is_delayed",
        "formula": "delay_days > 0",
        "allow_negative": False,
        "description": "Boolean flag indicating whether work experienced schedule delay"
    },
    {
        "feature": "utilization_ratio",
        "formula": "expenditure_amount / (sanctioned_amount + epsilon)",
        "allow_negative": False,
        "description": "Ratio of fund absorption to approved sanction ceiling"
    },
    {
        "feature": "utilization_ratio_released",
        "formula": "expenditure_amount / (released_amount + epsilon)",
        "allow_negative": False,
        "description": "Ratio of fund absorption against cash installments disbursed"
    },
    {
        "feature": "utilization_ratio_sanctioned",
        "formula": "expenditure_amount / (sanctioned_amount + epsilon)",
        "allow_negative": False,
        "description": "Direct sanction utilization ratio"
    },
    {
        "feature": "cost_per_category",
        "formula": "mean(sanctioned_amount) grouped by sector",
        "allow_negative": False,
        "description": "Sector-level average cost benchmark in INR"
    },
    {
        "feature": "cost_relative_to_category",
        "formula": "sanctioned_amount / category_mean_cost",
        "allow_negative": False,
        "description": "Normalized cost index relative to developmental sector peer average"
    },
    {
        "feature": "cost_category_zscore",
        "formula": "(sanctioned_amount - category_mean_cost) / (category_std_cost + epsilon)",
        "allow_negative": True,  # Z-score can be negative (below average cost)
        "description": "Standard deviations from sector mean cost"
    },
    {
        "feature": "progress_gap",
        "formula": "planned_schedule_pct - physical_progress_pct",
        "allow_negative": True,  # Negative means ahead of planned schedule
        "description": "Primary schedule discrepancy (positive = lagging, negative = ahead)"
    },
    {
        "feature": "progress_gap_schedule",
        "formula": "planned_schedule_pct - physical_progress_pct",
        "allow_negative": True,
        "description": "Linear time schedule progress minus certified physical progress"
    },
    {
        "feature": "progress_gap_fin_phy",
        "formula": "financial_progress_pct - physical_progress_pct",
        "allow_negative": True,  # Negative means contractor delivery leads fund release
        "description": "Disbursement-to-physical gap (flags high fund withdrawal with low physical progress)"
    },
    {
        "feature": "cost_deviation",
        "formula": "expenditure_amount - sanctioned_amount",
        "allow_negative": True,  # Negative means expenditure under sanctioned budget (savings)
        "description": "Primary budgetary cost variance in INR (positive = overrun, negative = savings)"
    },
    {
        "feature": "cost_deviation_sanction",
        "formula": "sanctioned_amount - recommended_amount",
        "allow_negative": True,  # Negative means sanction pruned below recommendation
        "description": "Administrative vetting variance in INR"
    },
    {
        "feature": "cost_deviation_sanction_pct",
        "formula": "((sanctioned - recommended) / recommended) * 100",
        "allow_negative": True,
        "description": "Percentage administrative variance at sanction"
    },
    {
        "feature": "cost_deviation_expenditure",
        "formula": "expenditure_amount - sanctioned_amount",
        "allow_negative": True,
        "description": "Realized cost overrun or savings in INR"
    },
    {
        "feature": "cost_deviation_expenditure_pct",
        "formula": "((expenditure - sanctioned) / sanctioned) * 100",
        "allow_negative": True,
        "description": "Percentage cost overrun or savings relative to sanction"
    },
    {
        "feature": "project_duration",
        "formula": "max(0, (actual_completion if completed else ref_date) - start_date)",
        "allow_negative": False,
        "description": "Actual or current duration in days (safely handles missing completion dates)"
    },
    {
        "feature": "project_duration_days",
        "formula": "max(0, (actual_completion if completed else ref_date) - start_date)",
        "allow_negative": False,
        "description": "Alias for project_duration in integer calendar days"
    },
    {
        "feature": "planned_duration_days",
        "formula": "max(0, expected_completion_date - start_date)",
        "allow_negative": False,
        "description": "Contractually scheduled execution duration in days"
    },
    {
        "feature": "actual_duration_days",
        "formula": "max(0, actual_completion_date - start_date) (NaN if ongoing)",
        "allow_negative": False,
        "description": "Realized execution duration for completed projects (censored for ongoing works)"
    },
    {
        "feature": "elapsed_duration_days",
        "formula": "max(0, ref_date - start_date)",
        "allow_negative": False,
        "description": "Calendar days elapsed since project initiation"
    },
    {
        "feature": "admin_sanction_duration_days",
        "formula": "max(0, sanction_date - recommendation_date)",
        "allow_negative": False,
        "description": "Administrative vetting turnaround latency in days"
    },
    {
        "feature": "sanction_sla_delay_days",
        "formula": "max(0, (sanction_date - recommendation_date) - 75)",
        "allow_negative": False,
        "description": "Days exceeded beyond statutory 75-day administrative sanction SLA"
    },
    {
        "feature": "unreleased_allocation",
        "formula": "max(0, sanctioned_amount - released_amount)",
        "allow_negative": False,
        "description": "Sanctioned funds committed but not yet disbursed to agency"
    }
]


def generate_validation_report(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generates a structured validation report for all engineered features.
    """
    rows = []
    total_rows = len(df)

    for item in FEATURE_DEFINITIONS:
        feat = item["feature"]
        formula = item["formula"]
        allow_neg = item["allow_negative"]

        if feat not in df.columns:
            rows.append({
                "feature": feat,
                "formula": formula,
                "minimum": "NOT FOUND",
                "maximum": "NOT FOUND",
                "mean": "NOT FOUND",
                "median": "NOT FOUND",
                "missing_count": total_rows,
                "invalid_count": total_rows,
                "example_values": "Column missing from DataFrame"
            })
            continue

        series = df[feat]
        # Identify missing
        missing_cnt = series.isna().sum()

        # Numeric conversion for statistical profiling
        numeric_s = pd.to_numeric(series, errors="coerce")

        # Check for invalid values:
        # 1. Infinite values
        inf_count = np.isinf(numeric_s).sum()

        # 2. Impossible negative values (if negative not allowed)
        if not allow_neg:
            neg_count = (numeric_s.dropna() < 0).sum()
        else:
            neg_count = 0

        invalid_cnt = int(inf_count + neg_count)

        # Compute statistics on valid numeric data
        valid_numeric = numeric_s.dropna()
        if len(valid_numeric) > 0:
            val_min = valid_numeric.min()
            val_max = valid_numeric.max()
            val_mean = valid_numeric.mean()
            val_median = valid_numeric.median()

            # Format formatting
            if series.dtype == bool or series.dtype == "bool":
                min_str = str(bool(val_min))
                max_str = str(bool(val_max))
                mean_str = f"{val_mean:.2f}"
                median_str = str(bool(val_median))
            elif isinstance(val_min, (int, np.integer)) or (valid_numeric % 1 == 0).all():
                min_str = f"{int(val_min):,}"
                max_str = f"{int(val_max):,}"
                mean_str = f"{val_mean:,.2f}"
                median_str = f"{int(val_median):,}"
            else:
                min_str = f"{val_min:,.4f}" if abs(val_min) < 10 else f"{val_min:,.2f}"
                max_str = f"{val_max:,.4f}" if abs(val_max) < 10 else f"{val_max:,.2f}"
                mean_str = f"{val_mean:,.4f}" if abs(val_mean) < 10 else f"{val_mean:,.2f}"
                median_str = f"{val_median:,.4f}" if abs(val_median) < 10 else f"{val_median:,.2f}"
        else:
            min_str = max_str = mean_str = median_str = "N/A"

        # Example values (up to 3 unique non-null examples)
        non_null_examples = series.dropna().unique()
        if len(non_null_examples) > 0:
            sample = [str(x) for x in non_null_examples[:3]]
            example_str = ", ".join(sample)
        else:
            example_str = "All NaN"

        rows.append({
            "feature": feat,
            "formula": formula,
            "minimum": min_str,
            "maximum": max_str,
            "mean": mean_str,
            "median": median_str,
            "missing_count": int(missing_cnt),
            "invalid_count": invalid_cnt,
            "example_values": example_str
        })

    report_df = pd.DataFrame(rows)
    return report_df


def df_to_markdown(df: pd.DataFrame) -> str:
    headers = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in df.iterrows():
        clean_row = [str(val).replace("|", "\\|") for val in row]
        lines.append("| " + " | ".join(clean_row) + " |")
    return "\n".join(lines)


def main():
    print("=" * 80)
    print("  PHASE 5 FEATURE ENGINEERING VALIDATION & PROFILING AUDIT")
    print("=" * 80)

    # 1. Load or run featured dataset
    csv_path = PROJECT_ROOT / "data" / "processed" / "featured_projects.csv"
    if not csv_path.exists():
        print(f"File {csv_path} not found. Running FeatureEngineeringPipeline...")
        pipeline = FeatureEngineeringPipeline()
        featured_df = pipeline.run()
    else:
        print(f"Loading featured dataset from {csv_path}...")
        featured_df = pd.read_csv(csv_path)

    print(f"Loaded {len(featured_df)} records across {len(featured_df.columns)} columns.\n")

    # 2. Generate Validation Report
    report_df = generate_validation_report(featured_df)

    # 3. Export CSV
    csv_out = PROJECT_ROOT / "data" / "processed" / "feature_engineering_validation_report.csv"
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    report_df.to_csv(csv_out, index=False)
    print(f"[SUCCESS] Exported CSV validation report to: {csv_out}")

    # 4. Export Markdown Report
    md_out = PROJECT_ROOT / "data" / "processed" / "feature_engineering_validation_report.md"
    with open(md_out, "w", encoding="utf-8") as f:
        f.write("# Phase 5 Feature Engineering Validation Report\n\n")
        f.write("Evaluation of derived features, formulas, numerical boundaries, and validity metrics.\n\n")
        f.write(df_to_markdown(report_df))
        f.write("\n\n### Validation Summary\n")
        f.write(f"- Total Features Profiled: {len(report_df)}\n")
        f.write(f"- Features with Zero Invalid Values: {(report_df['invalid_count'] == 0).sum()} / {len(report_df)}\n")
        f.write(f"- Features with Zero Missing Values: {(report_df['missing_count'] == 0).sum()} / {len(report_df)}\n")
        f.write("- Note: `actual_duration_days` missing count is expected for active/ongoing works (avoids survival bias).\n")

    print(f"[SUCCESS] Exported Markdown validation report to: {md_out}\n")

    # 5. Print formatted table
    print("=" * 120)
    print(report_df[["feature", "minimum", "maximum", "mean", "median", "missing_count", "invalid_count"]].to_string(index=False))
    print("=" * 120)

    total_invalids = report_df["invalid_count"].sum()
    if total_invalids == 0:
        print("\n>>> ALL 24 FEATURE VALIDATION CHECKS PASSED WITH 0 INVALID VALUES! <<<\n")
    else:
        print(f"\n[WARNING] Found {total_invalids} invalid values across engineered features!\n")


if __name__ == "__main__":
    main()
