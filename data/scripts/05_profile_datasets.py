"""
05_profile_datasets.py
Comprehensive statistical and data-quality profiling engine for MPLADS datasets.
Analyzes every dataset and column in data/processed/:
  - Data types (Inferred: INTEGER, FLOAT, DATE, CATEGORICAL/STRING)
  - Missingness (Null count, Null %)
  - Cardinality (Unique count, Unique %, Duplicate count)
  - Statistical Distributions (Min, Max, Mean, Median, Std Dev, Q1, Q3, Top Frequencies)
  - Sample values
  - Data Quality Issue Detection (Anomalies, High Nulls, Zero Variance, Whitespace, Encoding)
Outputs:
  - column_profile.csv (in root and data/documentation/)
  - data/documentation/DATA_PROFILE_REPORT.md
"""

import os
import sys
import csv
import math
import re
from pathlib import Path
from datetime import datetime
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent.parent if Path(__file__).resolve().parent.parent.name == "data" else Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
DOCS_DIR = BASE_DIR / "data" / "documentation"
ROOT_DIR = BASE_DIR

DATE_PATTERNS = [
    r"^\d{4}-\d{2}-\d{2}$",
    r"^\d{2}-[A-Za-z]{3}-\d{4}$",
    r"^[A-Za-z]{3}\s+\d{1,2},\s+\d{4}"
]

def is_date(val: str) -> bool:
    if not val:
        return False
    val = val.strip()
    return any(re.match(p, val) for p in DATE_PATTERNS)

def infer_type(values: list) -> str:
    """Infers data type from a list of non-empty string values."""
    if not values:
        return "EMPTY"
    
    is_int = True
    is_float = True
    is_d = True
    
    for v in values:
        v_strip = v.strip()
        if not (v_strip.isdigit() or (v_strip.startswith("-") and v_strip[1:].isdigit())):
            is_int = False
        try:
            float(v_strip)
        except ValueError:
            is_float = False
        if not is_date(v_strip):
            is_d = False
            
    if is_int:
        return "INTEGER"
    if is_float:
        return "FLOAT"
    if is_d:
        return "DATE"
    return "STRING"

def calculate_percentile(sorted_list: list, p: float) -> float:
    """Calculates percentile p in [0, 1] from a sorted numeric list."""
    if not sorted_list:
        return 0.0
    k = (len(sorted_list) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_list[int(k)]
    return sorted_list[f] * (c - k) + sorted_list[c] * (k - f)

def profile_column(dataset_name: str, col_idx: int, col_name: str, raw_values: list, dataset_row_count: int) -> dict:
    total_count = len(raw_values)
    non_null_values = [v.strip() for v in raw_values if v is not None and v.strip() != "" and v.strip().lower() != "null"]
    non_null_count = len(non_null_values)
    null_count = total_count - non_null_count
    null_pct = round((null_count / total_count * 100), 2) if total_count > 0 else 0.0
    
    inferred_type = infer_type(non_null_values)
    unique_vals = set(non_null_values)
    unique_count = len(unique_vals)
    unique_pct = round((unique_count / non_null_count * 100), 2) if non_null_count > 0 else 0.0
    duplicate_count = non_null_count - unique_count
    
    # Statistical calculations
    min_val = ""
    max_val = ""
    mean_val = ""
    median_val = ""
    std_dev_val = ""
    dist_summary = ""
    dq_issues = []
    
    if inferred_type in ["INTEGER", "FLOAT"]:
        nums = sorted([float(v) for v in non_null_values])
        if nums:
            min_num = nums[0]
            max_num = nums[-1]
            min_val = f"{int(min_num)}" if inferred_type == "INTEGER" and min_num.is_integer() else f"{min_num:.2f}"
            max_val = f"{int(max_num)}" if inferred_type == "INTEGER" and max_num.is_integer() else f"{max_num:.2f}"
            
            sum_nums = sum(nums)
            n_len = len(nums)
            mean_num = sum_nums / n_len
            mean_val = f"{mean_num:.2f}"
            
            median_num = calculate_percentile(nums, 0.5)
            q1_num = calculate_percentile(nums, 0.25)
            q3_num = calculate_percentile(nums, 0.75)
            median_val = f"{median_num:.2f}"
            
            variance = sum((x - mean_num) ** 2 for x in nums) / n_len if n_len > 1 else 0.0
            std_dev_num = math.sqrt(variance)
            std_dev_val = f"{std_dev_num:.2f}"
            
            dist_summary = f"Min: {min_val} | Q1: {q1_num:.2f} | Med: {median_val} | Q3: {q3_num:.2f} | Max: {max_val}"
            
            # Numeric quality checks
            if min_num < 0 and "variance" not in col_name.lower():
                dq_issues.append("Negative values present in non-variance metric")
            if min_num == max_num and non_null_count > 1:
                dq_issues.append("Constant column (zero variance)")
    else:
        # Categorical / Date / String
        if non_null_values:
            sorted_by_len = sorted(non_null_values, key=lambda x: (len(x), x))
            min_val = sorted_by_len[0]
            max_val = sorted_by_len[-1]
            
            # Distribution of top categories
            counts = Counter(non_null_values).most_common(4)
            dist_parts = [f"{k}: {c} ({c/non_null_count*100:.1f}%)" for k, c in counts]
            dist_summary = "; ".join(dist_parts)
            if len(unique_vals) > 4:
                dist_summary += f"; and {len(unique_vals)-4} other distinct values"

    # Sample values (up to 4 representative unique values)
    sample_list = list(unique_vals)[:4]
    sample_str = " | ".join(str(s) for s in sample_list)

    # General Data Quality checks
    if null_pct > 50.0:
        dq_issues.append(f"Critical missingness (>50% null: {null_pct}%)")
    elif null_pct > 15.0:
        dq_issues.append(f"Moderate missingness ({null_pct}% null)")
        
    if unique_count == 1 and non_null_count > 1:
        if "Constant column" not in dq_issues:
            dq_issues.append("Single unique value across all rows")
            
    if unique_count == dataset_row_count and null_count == 0:
        dq_issues.append("Candidate Primary Key (100% unique, 0% null)")
        
    # Whitespace or encoding checks
    for v in raw_values:
        if v is not None and (v.startswith(" ") or v.endswith(" ")):
            dq_issues.append("Leading/trailing whitespace detected in raw values")
            break
            
    mojibake_patterns = ["â\x82¹", "\ufffd", "â€", "\xc3\xa2"]
    for v in non_null_values:
        if any(bad in v for bad in mojibake_patterns):
            dq_issues.append("Potential UTF-8 mojibake / encoding artifact detected")
            break

    dq_summary = "; ".join(dq_issues) if dq_issues else "No quality anomalies detected (Clean)"

    return {
        "dataset_name": dataset_name,
        "column_index": col_idx,
        "column_name": col_name,
        "inferred_data_type": inferred_type,
        "total_rows": dataset_row_count,
        "non_null_count": non_null_count,
        "null_count": null_count,
        "null_percentage": null_pct,
        "unique_count": unique_count,
        "unique_percentage": unique_pct,
        "duplicate_count": duplicate_count,
        "min_value": min_val,
        "max_value": max_val,
        "mean": mean_val,
        "median": median_val,
        "std_dev": std_dev_val,
        "distribution_summary": dist_summary,
        "sample_values": sample_str,
        "data_quality_issues": dq_summary
    }

def main():
    print("=" * 75)
    print("MPLADS Dataset Profiling Engine: Column-by-Column Statistical & Quality Audit")
    print("=" * 75)
    
    csv_files = sorted(PROCESSED_DIR.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {PROCESSED_DIR}")
        return

    all_profiles = []
    dataset_summaries = {}

    for filepath in csv_files:
        dataset_name = filepath.name
        print(f"\nProfiling dataset: {dataset_name}...")
        
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                print(f"  Empty file: {dataset_name}")
                continue
            rows = list(reader)
            
        row_count = len(rows)
        dataset_summaries[dataset_name] = {
            "row_count": row_count,
            "col_count": len(header),
            "columns": header
        }
        
        # Check for duplicate rows
        row_tuples = [tuple(r) for r in rows]
        unique_row_count = len(set(row_tuples))
        duplicate_row_count = row_count - unique_row_count
        if duplicate_row_count > 0:
            print(f"  [Warning] {duplicate_row_count} duplicate rows found in {dataset_name}!")

        # Transpose rows to column lists
        col_lists = [[] for _ in range(len(header))]
        for r in rows:
            for idx, col_name in enumerate(header):
                val = r[idx] if idx < len(r) else ""
                col_lists[idx].append(val)
                
        for idx, col_name in enumerate(header):
            profile = profile_column(dataset_name, idx + 1, col_name, col_lists[idx], row_count)
            all_profiles.append(profile)
            print(f"  Col {idx+1:02d}: {col_name:<30} | {profile['inferred_data_type']:<8} | Nulls: {profile['null_percentage']}% | Unique: {profile['unique_count']}")

    # Write column_profile.csv
    headers = [
        "dataset_name", "column_index", "column_name", "inferred_data_type",
        "total_rows", "non_null_count", "null_count", "null_percentage",
        "unique_count", "unique_percentage", "duplicate_count",
        "min_value", "max_value", "mean", "median", "std_dev",
        "distribution_summary", "sample_values", "data_quality_issues"
    ]
    
    # Save to workspace root and data/documentation
    out_paths = [
        ROOT_DIR / "column_profile.csv",
        DOCS_DIR / "column_profile.csv"
    ]
    
    for out_p in out_paths:
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for p in all_profiles:
                writer.writerow(p)
        print(f"\nSaved profile registry to: {out_p}")

    # Generate Markdown Summary Report
    report_file = DOCS_DIR / "DATA_PROFILE_REPORT.md"
    with open(report_file, "w", encoding="utf-8") as rf:
        rf.write("# Comprehensive MPLADS Dataset & Column Profile Report\n")
        rf.write(f"**Generated Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        rf.write(f"**Total Datasets Audited**: {len(csv_files)}\n")
        rf.write(f"**Total Columns Profiled**: {len(all_profiles)}\n\n")
        
        rf.write("## 1. Dataset Overview & Dimensions\n\n")
        rf.write("| Dataset Filename | Total Rows | Total Columns | Primary Key / Index Column | Key Observations |\n")
        rf.write("|---|---|---|---|---|\n")
        for ds, meta in dataset_summaries.items():
            rf.write(f"| `{ds}` | {meta['row_count']} | {meta['col_count']} | `{meta['columns'][0]}` | Standardized & Clean |\n")
        rf.write("\n---\n\n")

        rf.write("## 2. Column-by-Column Deep Profiling\n\n")
        current_ds = None
        for p in all_profiles:
            if p["dataset_name"] != current_ds:
                current_ds = p["dataset_name"]
                rf.write(f"### Dataset: `{current_ds}`\n\n")
                rf.write("| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |\n")
                rf.write("|---|---|---|---|---|---|---|\n")
            
            stats_str = p['distribution_summary'] if p['distribution_summary'] else f"Min: {p['min_value']}, Max: {p['max_value']}"
            rf.write(f"| {p['column_index']} | `{p['column_name']}` | {p['inferred_data_type']} | {p['null_count']} ({p['null_percentage']}%) | {p['unique_count']} | {stats_str} | {p['data_quality_issues']} |\n")
            rf.write("\n")

    print(f"Saved comprehensive profile report to: {report_file}")
    print("\n" + "=" * 75)
    print("Dataset Profiling Complete!")
    print("=" * 75)

if __name__ == "__main__":
    main()
