"""
clean_mplads_data.py
=============================================================================
Phase 2 Reproducible Data Cleaning & Validation Pipeline using Python and Pandas.
=============================================================================

Pipeline Architecture:
    Raw Data (Read-Only)
          ↓
      Cleaning (Explicit, readable Pandas transformations)
          ↓
     Validation (Integrity checks, ID validation, logic assertions)
          ↓
    Processed CSVs (Clean datasets saved to data/processed/ and data/cleaned/)

Mandate Checklist:
  1. Load raw MPLADS datasets without modifying them.
  2. Remove exact duplicate rows and report how many were removed.
  3. Standardize all date columns into consistent ISO format (YYYY-MM-DD).
  4. Convert currency/financial fields into numeric values.
  5. Remove currency symbols, commas, whitespace, and formatting noise.
  6. Normalize text fields (strip, collapse spaces, consistent casing).
  7. Handle missing values carefully based on column semantics (no blind zero fills).
  8. Preserve legitimate zero values.
  9. Normalize categorical values (consistent casing and terminology).
 10. Validate ID columns (check missing, duplicate, malformed, or suspicious IDs).
 11. Preserve original meaning and granularity of the data.
 12. Never silently discard records.
"""

import os
import sys
import re
import json
import datetime
import subprocess
from pathlib import Path
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Path Configuration
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent
RAW_DIR = BASE_DIR / "raw"
PROCESSED_DIR = BASE_DIR / "processed"
CLEANED_DIR = BASE_DIR / "cleaned"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
CLEANED_DIR.mkdir(parents=True, exist_ok=True)

# Import provenance tracker if available
sys.path.insert(0, str(BASE_DIR / "scripts"))
try:
    from utils_provenance import calculate_sha256, record_provenance
except ImportError:
    def calculate_sha256(filepath): return ""
    def record_provenance(*args, **kwargs): return {}


# ---------------------------------------------------------------------------
# Explicit Helper Functions (Readable & Modular)
# ---------------------------------------------------------------------------

def check_and_remove_duplicates(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    """
    Mandate 2: Inspects DataFrame for exact duplicate rows, logs findings,
    and returns deduplicated DataFrame.
    """
    initial_count = len(df)
    duplicate_mask = df.duplicated()
    duplicate_count = int(duplicate_mask.sum())
    
    if duplicate_count > 0:
        print(f"  [Deduplication] {dataset_name}: Found and removed {duplicate_count} exact duplicate rows.")
        df_cleaned = df.drop_duplicates().reset_index(drop=True)
    else:
        print(f"  [Deduplication] {dataset_name}: 0 duplicate rows found across {initial_count} records.")
        df_cleaned = df.copy()
        
    return df_cleaned


def clean_text_field(series: pd.Series) -> pd.Series:
    """
    Mandate 6: Explicit text normalization:
      - Strips leading/trailing whitespace
      - Collapses multi-spaces
      - Replaces null-like strings with empty string
    """
    # Step 1: Ensure string type and strip exterior whitespace
    s_cleaned = series.astype(str).str.strip()
    
    # Step 2: Collapse consecutive internal spaces into single space
    s_cleaned = s_cleaned.str.replace(r"\s+", " ", regex=True)
    
    # Step 3: Replace string representations of NaN
    s_cleaned = s_cleaned.replace({"nan": "", "None": "", "<NA>": ""})
    
    return s_cleaned


def to_consistent_title_case(series: pd.Series) -> pd.Series:
    """
    Mandate 6: Transforms text to clean Title Case word-by-word.
    """
    s_clean = clean_text_field(series)
    return s_clean.apply(lambda val: " ".join(word.capitalize() for word in val.split()) if val else "")


def clean_currency_to_float(series: pd.Series) -> pd.Series:
    """
    Mandates 4 & 5: Converts currency text to clean numeric float values:
      - Removes non-breaking space (\\u00a0)
      - Strips currency symbols (₹, Rs.)
      - Strips units ('Crore', 'Lakh')
      - Strips commas and extraneous whitespace
      - Preserves legitimate NaN / missing values
      - Preserves legitimate 0.0 values (Mandate 8)
    """
    def parse_single_currency(val):
        # Preserve existing nulls (Mandate 7)
        if pd.isna(val) or val is None or val == "":
            return np.nan
            
        text = str(val).strip()
        # Remove non-breaking spaces
        text = text.replace("\u00a0", " ")
        # Remove currency units case-insensitively
        text = re.sub(r"(?i)(?:crore|crores|cr|lakh|lakhs|inr|rs\.?|₹)", "", text)
        # Remove commas and spaces
        text = re.sub(r"[^\d.-]", "", text)
        
        if text == "" or text == "-":
            return np.nan
            
        try:
            return float(text)
        except ValueError:
            return np.nan

    return series.apply(parse_single_currency)


def parse_to_iso_date(series: pd.Series) -> pd.Series:
    """
    Mandate 3: Standardizes variable date strings into ISO-8601 (YYYY-MM-DD).
    Supported formats:
      - DD-Mon-YYYY (e.g. '07-Dec-2025')
      - Mon DD, YYYY HH:MM:SS AM/PM (e.g. 'Jun 4, 2024 12:00:00 AM')
      - YYYY-MM-DD (e.g. '2024-06-04')
    """
    def convert_single_date(val):
        if pd.isna(val) or val is None or str(val).strip() == "":
            return ""
        val_str = str(val).strip()
        
        # Format 1: '07-Dec-2025'
        try:
            return datetime.datetime.strptime(val_str, "%d-%b-%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
            
        # Format 2: 'Jun 4, 2024 12:00:00 AM'
        try:
            return datetime.datetime.strptime(val_str, "%b %d, %Y %I:%M:%S %p").strftime("%Y-%m-%d")
        except ValueError:
            pass
            
        # Format 3: Already ISO 'YYYY-MM-DD'
        try:
            return datetime.datetime.strptime(val_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
            
        # Fallback to pandas flexible parser
        try:
            dt = pd.to_datetime(val_str, errors="coerce")
            if pd.notna(dt):
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
            
        return val_str

    return series.apply(convert_single_date)


def generate_canonical_state_key(series: pd.Series) -> pd.Series:
    """
    Mandate 9: Generates canonical lowercase key for deterministic cross-dataset joins.
    """
    s = clean_text_field(series).str.lower()
    s = s.str.replace(r"^the\s+", "", regex=True)
    s = s.str.replace("&", "and", regex=False)
    s = s.str.replace(r"\s+", " ", regex=True)
    return s.str.strip()


# ===========================================================================
# 1. CLEANING: States Master Dataset
# ===========================================================================

def clean_states() -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("STAGE 1: CLEANING STATES REGISTRY (esakshi_states)")
    print("=" * 70)
    
    # [Mandate 1] Load raw dataset without modifying it
    raw_path = RAW_DIR / "esakshi" / "esakshi_states_raw.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    df = pd.DataFrame(raw_data)
    print(f"  [Load Raw] Ingested {len(df)} records from {raw_path.name}")
    
    # [Mandate 2] Deduplication
    df = check_and_remove_duplicates(df, "esakshi_states")
    
    # [Mandate 10] ID Validation
    df["state_id"] = pd.to_numeric(df["STATE_ID"], errors="coerce")
    assert df["state_id"].notna().all(), "Validation Error: Missing or non-numeric state_id found!"
    df["state_id"] = df["state_id"].astype(int)
    assert df["state_id"].is_unique, "Validation Error: Duplicate state_id found in states master!"
    
    # [Mandate 6] Text Normalization
    df["state_name"] = to_consistent_title_case(df["STATE_NAME"])
    
    # [Mandate 9] Categorical Normalization (State vs Union Territory)
    ut_keywords = ["islands", "chandigarh", "delhi", "haveli", "ladakh", "lakshadweep", "puducherry", "jammu and kashmir"]
    df["category"] = df["state_name"].apply(
        lambda name: "Union Territory" if any(ut in name.lower() for ut in ut_keywords) else "State"
    )
    
    # Cross-dataset canonical key
    df["canonical_state_key"] = generate_canonical_state_key(df["state_name"])
    
    # Validation
    assert len(df) == 36, f"Validation Error: Expected 36 States/UTs, found {len(df)}"
    assert (df["category"] == "State").sum() == 28, "Validation Error: Expected 28 States"
    assert (df["category"] == "Union Territory").sum() == 8, "Validation Error: Expected 8 UTs"
    print(f"  [Validation] 36 States/UTs verified (28 States, 8 UTs). IDs unique and valid.")
    
    # Select and order columns
    df_clean = df[["state_id", "state_name", "category", "canonical_state_key"]].copy()
    
    # Save outputs
    out_clean = CLEANED_DIR / "clean_esakshi_states.csv"
    out_proc = PROCESSED_DIR / "esakshi_states.csv"
    df_clean.to_csv(out_clean, index=False)
    df_clean.to_csv(out_proc, index=False)
    print(f"  [Output] Saved clean dataset to {out_clean.name} ({len(df_clean)} rows)")
    return df_clean


# ===========================================================================
# 2. CLEANING: Parliamentary Constituencies Dataset
# ===========================================================================

def clean_constituencies() -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("STAGE 2: CLEANING PARLIAMENTARY CONSTITUENCIES (esakshi_constituencies)")
    print("=" * 70)
    
    # [Mandate 1] Load raw dataset without modifying it
    raw_path = RAW_DIR / "esakshi" / "esakshi_constituencies_by_state_raw.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    records = []
    for state_name, state_dict in raw_data.items():
        sid = state_dict.get("state_id")
        for c in state_dict.get("constituencies", []):
            records.append({
                "constituency_id": c.get("ID"),
                "state_id": sid,
                "state_name": state_name,
                "raw_caption": c.get("CAPTION", "")
            })
    df = pd.DataFrame(records)
    print(f"  [Load Raw] Ingested {len(df)} constituency records across 36 states")
    
    # [Mandate 2] Deduplication
    df = check_and_remove_duplicates(df, "esakshi_constituencies")
    
    # [Mandate 10] ID Validation
    df["constituency_id"] = pd.to_numeric(df["constituency_id"], errors="coerce")
    assert df["constituency_id"].notna().all(), "Validation Error: Null constituency_id detected!"
    df["constituency_id"] = df["constituency_id"].astype(int)
    assert df["constituency_id"].is_unique, "Validation Error: Duplicate constituency_id detected!"
    
    df["state_id"] = pd.to_numeric(df["state_id"], errors="coerce").astype(int)
    assert df["state_id"].notna().all(), "Validation Error: Null state_id detected in constituencies!"
    
    # [Mandate 6] Text Normalization
    df["state_name"] = to_consistent_title_case(df["state_name"])
    df["raw_caption"] = clean_text_field(df["raw_caption"]).str.upper()
    
    # [Mandate 9 & 11] Reservation extraction & clean constituency name
    def parse_reservation(caption: str) -> str:
        if "(SC)" in caption:
            return "SC"
        elif "(ST)" in caption:
            return "ST"
        return "General"
        
    def parse_clean_name(caption: str) -> str:
        cleaned = re.sub(r"\s*\((?:SC|ST)\)\s*", "", caption).strip()
        return " ".join(w.capitalize() for w in cleaned.split())
        
    df["reservation_category"] = df["raw_caption"].apply(parse_reservation)
    df["constituency_name"] = df["raw_caption"].apply(parse_clean_name)
    df["canonical_state_key"] = generate_canonical_state_key(df["state_name"])
    
    # Validation Suite
    assert len(df) == 543, f"Validation Error: Expected 543 Lok Sabha seats, found {len(df)}"
    res_counts = df["reservation_category"].value_counts().to_dict()
    assert res_counts.get("General") == 417, f"Validation Error: Expected 417 General, got {res_counts.get('General')}"
    assert res_counts.get("SC") == 82, f"Validation Error: Expected 82 SC, got {res_counts.get('SC')}"
    assert res_counts.get("ST") == 44, f"Validation Error: Expected 44 ST, got {res_counts.get('ST')}"
    print(f"  [Validation] Exactly 543 seats (417 General, 82 SC, 44 ST). Constituency IDs valid & unique.")
    
    # Select and order columns
    df_clean = df[[
        "constituency_id", "state_id", "state_name", "constituency_name",
        "raw_caption", "reservation_category", "canonical_state_key"
    ]].copy()
    
    # Save outputs
    out_clean = CLEANED_DIR / "clean_esakshi_constituencies.csv"
    out_proc = PROCESSED_DIR / "esakshi_constituencies.csv"
    df_clean.to_csv(out_clean, index=False)
    df_clean.to_csv(out_proc, index=False)
    print(f"  [Output] Saved clean dataset to {out_clean.name} ({len(df_clean)} rows)")
    return df_clean


# ===========================================================================
# 3. CLEANING: National Progress KPI Summary
# ===========================================================================

def clean_national_summary() -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("STAGE 3: CLEANING NATIONAL SUMMARY TILES (esakshi_national_summary)")
    print("=" * 70)
    
    # [Mandate 1] Load raw dataset without modifying it
    raw_path = RAW_DIR / "esakshi" / "esakshi_national_tiles_raw.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    records = []
    for k, v in raw_data.items():
        if k == "Current Tenure":
            continue
        cnt = np.nan
        amt_inr = np.nan
        amt_cr = np.nan
        if isinstance(v, list):
            if len(v) == 2:
                amt_inr = clean_currency_to_float(pd.Series([v[0]])).iloc[0]
                amt_cr = clean_currency_to_float(pd.Series([v[1]])).iloc[0]
            elif len(v) == 3:
                try:
                    cnt = int(v[0])
                except ValueError:
                    cnt = np.nan
                amt_inr = clean_currency_to_float(pd.Series([v[1]])).iloc[0]
                amt_cr = clean_currency_to_float(pd.Series([v[2]])).iloc[0]
                
        records.append({
            "metric_key": k,
            "metric_description": k,
            "count_works": cnt,
            "amount_inr": amt_inr,
            "amount_crores": amt_cr
        })
    df = pd.DataFrame(records)
    print(f"  [Load Raw] Ingested {len(df)} macro progress indicators")
    
    # [Mandate 2] Deduplication
    df = check_and_remove_duplicates(df, "esakshi_national_summary")
    
    # [Mandate 6] Text Normalization
    df["metric_key"] = clean_text_field(df["metric_key"])
    df["metric_description"] = clean_text_field(df["metric_description"])
    
    # [Mandate 7 & 8] Context-Aware Missing Value Handling
    # Note: Pure financial limit tiles (Allocated Limit & Expenditure) do not count individual works.
    # We do NOT replace count_works with 0 because that would falsely indicate zero works created!
    
    # Validation
    assert len(df) == 6, f"Validation Error: Expected 6 macro indicators, got {len(df)}"
    assert df["amount_inr"].notna().all(), "Validation Error: Null currency amount detected!"
    assert (df["amount_inr"] > 0).all(), "Validation Error: Negative or zero amount detected!"
    print(f"  [Validation] All 6 macro financial values positive and non-null.")
    
    # Save outputs
    out_clean = CLEANED_DIR / "clean_esakshi_national_summary.csv"
    out_proc = PROCESSED_DIR / "esakshi_national_summary.csv"
    df.to_csv(out_clean, index=False)
    df.to_csv(out_proc, index=False)
    print(f"  [Output] Saved clean dataset to {out_clean.name} ({len(df)} rows)")
    return df


# ===========================================================================
# 4. CLEANING: Disaster Relief Consents
# ===========================================================================

def clean_calamity_relief() -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("STAGE 4: CLEANING CALAMITY RELIEF CONSENTS (esakshi_calamity_relief)")
    print("=" * 70)
    
    # [Mandate 1] Load raw dataset without modifying it
    raw_path = RAW_DIR / "esakshi" / "esakshi_calamity_relief_raw.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    items = raw_data.get("Total Calimity Consent", [])
    if isinstance(items, str):
        items = json.loads(items)
        
    df_raw = pd.DataFrame(items)
    print(f"  [Load Raw] Ingested {len(df_raw)} records (including aggregate footer) from {raw_path.name}")
    
    # [Mandate 12] Never silently discard records:
    # Separate the API aggregate footer row into validation logic rather than blindly dropping it
    footer_row = df_raw[df_raw["Sno"].isna()]
    reported_total = float(footer_row["Total_Amt"].iloc[0]) if not footer_row.empty else np.nan
    
    # Filter to itemized records
    df = df_raw[df_raw["Sno"].notna()].copy()
    print(f"  [Record Separation] Separated {len(df)} itemized records from 1 summary footer row")
    
    # [Mandate 2] Deduplication
    df = check_and_remove_duplicates(df, "esakshi_calamity_relief")
    
    # [Mandate 10] ID Validation
    df["s_no"] = pd.to_numeric(df["Sno"], errors="coerce")
    assert df["s_no"].notna().all(), "Validation Error: Null Sno detected!"
    df["s_no"] = df["s_no"].astype(int)
    assert df["s_no"].is_unique, "Validation Error: Duplicate Sno detected in calamity consents!"
    
    # [Mandate 6] Text Normalization & Honorific Extraction
    def extract_mp_honorific(name_str):
        clean = clean_text_field(pd.Series([name_str])).iloc[0]
        honorific = ""
        for h in ["Shri ", "Smt ", "Dr ", "DR "]:
            if clean.lower().startswith(h.lower()):
                honorific = h.strip().title()
                clean = clean[len(h):].strip()
                break
        clean_title = " ".join(w.capitalize() for w in clean.split())
        return pd.Series([honorific, clean_title], index=["honorific", "mp_name"])
        
    name_info = df["MP_NAME"].apply(extract_mp_honorific)
    df["honorific"] = name_info["honorific"]
    df["mp_name"] = name_info["mp_name"]
    
    # [Mandate 9] Categorical Normalization
    df["house_of_parliament"] = df["HOUSE_OF_PARLIAMENT"].apply(lambda h: "Lok Sabha" if h == 2 else "Rajya Sabha")
    df["tenure"] = clean_text_field(df["TENURE"])
    df["calamity_name"] = clean_text_field(df["CALAMITY_NAME"])
    df["calamity_type"] = clean_text_field(df["TYPE"])
    
    # [Mandate 4 & 5] Currency Cleaning
    df["consented_amount_inr"] = clean_currency_to_float(df["CONSENTED_AMOUNT"])
    df["consented_amount_lakhs"] = (df["consented_amount_inr"] / 100000.0).round(2)
    
    # [Mandate 3] Date Standardization to ISO-8601
    df["consent_date_iso"] = parse_to_iso_date(df["CRT_DT"])
    df["tenure_start_date_iso"] = parse_to_iso_date(df["TENURE_START_DATE"])
    df["tenure_end_date_iso"] = parse_to_iso_date(df["TENURE_END_DATE"])
    
    # Validation Suite
    iso_pattern = r"^\d{4}-\d{2}-\d{2}$"
    assert df["consent_date_iso"].str.match(iso_pattern).all(), "Validation Error: Non-ISO consent date!"
    assert df["tenure_start_date_iso"].str.match(iso_pattern).all(), "Validation Error: Non-ISO tenure start date!"
    assert df["tenure_end_date_iso"].str.match(iso_pattern).all(), "Validation Error: Non-ISO tenure end date!"
    
    # Mathematical assertion: sum of consents equals reported Total_Amt
    computed_sum = df["consented_amount_inr"].sum()
    assert abs(computed_sum - reported_total) < 0.01, f"Validation Error: Sum {computed_sum} != reported {reported_total}"
    print(f"  [Validation] Itemized sum (₹{computed_sum:,.2f}) perfectly matches reported total.")
    
    # Statutory cap validation: Para 3.12 permits <= ₹100 Lakhs
    assert (df["consented_amount_lakhs"] <= 100.0).all(), "Validation Error: Consented amount exceeds ₹100 Lakhs cap!"
    print(f"  [Validation] All 12 consents adhere to statutory cap (<= ₹1.00 Crore). Dates conform to ISO-8601.")
    
    # Select and order columns
    df_clean = df[[
        "s_no", "honorific", "mp_name", "house_of_parliament", "tenure",
        "calamity_name", "calamity_type", "consented_amount_inr",
        "consented_amount_lakhs", "consent_date_iso", "tenure_start_date_iso",
        "tenure_end_date_iso"
    ]].copy()
    
    # Save outputs
    out_clean = CLEANED_DIR / "clean_esakshi_calamity_relief.csv"
    out_proc = PROCESSED_DIR / "esakshi_calamity_relief.csv"
    df_clean.to_csv(out_clean, index=False)
    df_clean.to_csv(out_proc, index=False)
    print(f"  [Output] Saved clean dataset to {out_clean.name} ({len(df_clean)} rows)")
    return df_clean


# ===========================================================================
# 5. CLEANING: Union Budget Longitudinal Series
# ===========================================================================

def clean_union_budget() -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("STAGE 5: CLEANING UNION BUDGET SERIES (union_budget_mplads)")
    print("=" * 70)
    
    # [Mandate 1] Load raw dataset without modifying it
    raw_path = RAW_DIR / "union_budget" / "union_budget_mospi_demand91_raw.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    df = pd.DataFrame(raw_data)
    print(f"  [Load Raw] Ingested {len(df)} fiscal years from {raw_path.name}")
    
    # [Mandate 2] Deduplication
    df = check_and_remove_duplicates(df, "union_budget_mplads")
    
    # [Mandate 10] ID Validation
    df["major_head"] = pd.to_numeric(df["major_head"], errors="coerce").astype(int)
    assert (df["major_head"] == 3475).all(), "Validation Error: Unexpected major_head code!"
    
    # [Mandate 3] Temporal Decomposition
    def extract_fiscal_years(fy_str):
        m = re.match(r"^(\d{4})-(\d{2})$", str(fy_str).strip())
        if m:
            s_yr = int(m.group(1))
            e_yr = s_yr + 1
            return pd.Series([s_yr, e_yr], index=["start_year", "end_year"])
        return pd.Series([np.nan, np.nan], index=["start_year", "end_year"])
        
    years_df = df["financial_year"].apply(extract_fiscal_years)
    df["start_year"] = years_df["start_year"].astype(int)
    df["end_year"] = years_df["end_year"].astype(int)
    
    # [Mandate 4 & 5] Numeric and Currency Fields
    df["scheme_entitlement_per_mp_cr"] = clean_currency_to_float(df["scheme_entitlement_per_mp_cr"])
    df["budget_estimate_cr"] = clean_currency_to_float(df["budget_estimate_cr"])
    df["revised_estimate_cr"] = clean_currency_to_float(df["revised_estimate_cr"])
    df["actual_expenditure_cr"] = clean_currency_to_float(df["actual_expenditure_cr"])
    
    # [Mandate 7 & 8] Careful Missing Value Handling:
    # In FY 2025-26, revised_estimate_cr and actual_expenditure_cr are naturally NaN because the fiscal year is in progress.
    # Do NOT blindly replace with zero!
    df["be_vs_actual_variance_cr"] = (df["actual_expenditure_cr"] - df["budget_estimate_cr"]).round(2)
    
    # [Mandate 6] Text Normalization
    df["status_notes"] = clean_text_field(df["status"])
    
    # Validation Suite
    assert len(df) == 33, f"Validation Error: Expected 33 fiscal years, got {len(df)}"
    assert df["financial_year"].is_unique, "Validation Error: Duplicate financial_year found!"
    assert df["start_year"].min() == 1993 and df["start_year"].max() == 2025, "Validation Error: Fiscal year range incomplete!"
    print(f"  [Validation] Continuous 33-year series (1993–94 to 2025–26). Major Head 3475 verified.")
    
    # Select and order columns
    df_clean = df[[
        "financial_year", "start_year", "end_year", "scheme_entitlement_per_mp_cr",
        "budget_estimate_cr", "revised_estimate_cr", "actual_expenditure_cr",
        "be_vs_actual_variance_cr", "major_head", "status_notes"
    ]].copy()
    
    # Save outputs
    out_clean = CLEANED_DIR / "clean_union_budget_mplads_1993_2025.csv"
    out_proc = PROCESSED_DIR / "union_budget_mplads_1993_2025.csv"
    df_clean.to_csv(out_clean, index=False)
    df_clean.to_csv(out_proc, index=False)
    print(f"  [Output] Saved clean dataset to {out_clean.name} ({len(df_clean)} rows)")
    return df_clean


# ===========================================================================
# 6. CLEANING: Parliamentary Audited State Financials
# ===========================================================================

def clean_parliament_qa() -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("STAGE 6: CLEANING PARLIAMENTARY STATE OUTLAYS (parliament_qa_state_expenditure)")
    print("=" * 70)
    
    # [Mandate 1] Load raw dataset without modifying it
    raw_path = RAW_DIR / "parliament_sansad" / "parliament_qa_state_expenditures_raw.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    df = pd.DataFrame(raw_data)
    print(f"  [Load Raw] Ingested {len(df)} records from {raw_path.name}")
    
    # [Mandate 2] Deduplication
    df = check_and_remove_duplicates(df, "parliament_qa_state_expenditure")
    
    # [Mandate 10] ID Validation
    df["state_id"] = pd.to_numeric(df["state_id"], errors="coerce").astype(int)
    assert df["state_id"].is_unique, "Validation Error: Duplicate state_id found in parliamentary QA!"
    
    # [Mandate 6] Text Normalization & Canonical Key
    df["state_name"] = to_consistent_title_case(df["state_name"])
    df["canonical_state_key"] = generate_canonical_state_key(df["state_name"])
    
    # [Mandate 4 & 5] Financial and Numeric Conversion
    fin_cols = ["entitlement_cr", "released_cr", "expenditure_cr", "unspent_balance_cr"]
    for c in fin_cols:
        df[c] = clean_currency_to_float(df[c]).round(2)
        
    cnt_cols = ["works_recommended", "works_sanctioned", "works_completed"]
    for c in cnt_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(int)
        
    # Derived Rates & Calculations
    df["utilization_rate_pct"] = np.where(
        df["released_cr"] > 0,
        (df["expenditure_cr"] / df["released_cr"] * 100).round(2),
        0.0
    )
    df["sanction_rate_pct"] = np.where(
        df["works_recommended"] > 0,
        (df["works_sanctioned"] / df["works_recommended"] * 100).round(2),
        0.0
    )
    df["completion_rate_pct"] = np.where(
        df["works_sanctioned"] > 0,
        (df["works_completed"] / df["works_sanctioned"] * 100).round(2),
        0.0
    )
    
    # Logical Validation Flags
    df["is_utilization_valid"] = (df["utilization_rate_pct"] >= 0.0) & (df["utilization_rate_pct"] <= 100.0)
    df["is_workflow_valid"] = (df["works_completed"] <= df["works_sanctioned"]) & (df["works_sanctioned"] <= df["works_recommended"])
    
    # Validation Suite
    assert len(df) == 36, f"Validation Error: Expected 36 States/UTs, found {len(df)}"
    assert df["is_utilization_valid"].all(), "Validation Error: Invalid utilization percentage detected!"
    assert df["is_workflow_valid"].all(), "Validation Error: Physical asset progression order violated!"
    print(f"  [Validation] 36 State profiles. All utilization rates [0, 100%]. Workflow order passed.")
    
    # Select and order columns
    df_clean = df[[
        "state_id", "state_name", "canonical_state_key", "entitlement_cr",
        "released_cr", "expenditure_cr", "unspent_balance_cr", "utilization_rate_pct",
        "works_recommended", "works_sanctioned", "works_completed",
        "sanction_rate_pct", "completion_rate_pct", "is_utilization_valid",
        "is_workflow_valid"
    ]].copy()
    
    # Save outputs
    out_clean = CLEANED_DIR / "clean_parliament_qa_state_expenditure.csv"
    out_proc = PROCESSED_DIR / "parliament_qa_state_expenditure.csv"
    df_clean.to_csv(out_clean, index=False)
    df_clean.to_csv(out_proc, index=False)
    print(f"  [Output] Saved clean dataset to {out_clean.name} ({len(df_clean)} rows)")
    return df_clean


# ===========================================================================
# 7. CLEANING: Integrated Master Dimension Table
# ===========================================================================

def clean_master_dimension(df_states: pd.DataFrame, df_const: pd.DataFrame, df_qa: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("STAGE 7: BUILDING CLEAN MASTER DIMENSION (master_dim_states_constituencies)")
    print("=" * 70)
    
    # Aggregate constituency reservations by canonical key
    seat_stats = df_const.groupby("canonical_state_key").agg(
        total_lok_sabha_seats=("constituency_id", "count"),
        general_seats=("reservation_category", lambda s: (s == "General").sum()),
        sc_reserved_seats=("reservation_category", lambda s: (s == "SC").sum()),
        st_reserved_seats=("reservation_category", lambda s: (s == "ST").sum())
    ).reset_index()
    
    # Join States with Seat Statistics
    master = pd.merge(df_states, seat_stats, on="canonical_state_key", how="left")
    
    # Join with Parliamentary QA spending data
    qa_slice = df_qa[[
        "canonical_state_key", "released_cr", "expenditure_cr", "unspent_balance_cr",
        "utilization_rate_pct", "works_completed"
    ]].rename(columns={
        "released_cr": "cumulative_released_cr",
        "expenditure_cr": "cumulative_expenditure_cr",
        "utilization_rate_pct": "utilization_pct",
        "works_completed": "works_completed_count"
    })
    
    master = pd.merge(master, qa_slice, on="canonical_state_key", how="left")
    
    # Derived quota share and statutory benchmarks
    master["sc_seat_share_pct"] = (master["sc_reserved_seats"] / master["total_lok_sabha_seats"] * 100).round(2)
    master["st_seat_share_pct"] = (master["st_reserved_seats"] / master["total_lok_sabha_seats"] * 100).round(2)
    master["statutory_sc_allocation_pct"] = 15.0
    master["statutory_st_allocation_pct"] = 7.5
    
    # Validation Suite
    assert len(master) == 36, f"Validation Error: Expected 36 states, got {len(master)}"
    assert master["cumulative_released_cr"].notna().all(), "Validation Error: Unmatched state in financial join!"
    assert master["total_lok_sabha_seats"].sum() == 543, f"Validation Error: Total seats sum != 543!"
    print(f"  [Validation] Master Dimension built for 36 States/UTs with 0% missingness. Exactly 543 seats total.")
    
    # Select and order columns
    df_clean = master[[
        "state_id", "state_name", "canonical_state_key", "category",
        "total_lok_sabha_seats", "general_seats", "sc_reserved_seats",
        "st_reserved_seats", "sc_seat_share_pct", "st_seat_share_pct",
        "statutory_sc_allocation_pct", "statutory_st_allocation_pct",
        "cumulative_released_cr", "cumulative_expenditure_cr", "unspent_balance_cr",
        "utilization_pct", "works_completed_count"
    ]].copy()
    
    # Save outputs
    out_clean = CLEANED_DIR / "clean_master_dim_states_constituencies.csv"
    out_proc = PROCESSED_DIR / "master_dim_states_constituencies.csv"
    df_clean.to_csv(out_clean, index=False)
    df_clean.to_csv(out_proc, index=False)
    print(f"  [Output] Saved clean dataset to {out_clean.name} ({len(df_clean)} rows)")
    return df_clean


# ===========================================================================
# MASTER EXECUTION CONTROLLER
# ===========================================================================

def main():
    print("#" * 75)
    print("# MPLADS Phase 2: Python & Pandas Reproducible Data Cleaning Pipeline")
    print(f"# Cleaned Output Directory : {CLEANED_DIR}")
    print(f"# Processed Output Directory: {PROCESSED_DIR}")
    print("#" * 75)
    
    df_states = clean_states()
    df_const = clean_constituencies()
    df_summary = clean_national_summary()
    df_calamity = clean_calamity_relief()
    df_budget = clean_union_budget()
    df_qa = clean_parliament_qa()
    df_master = clean_master_dimension(df_states, df_const, df_qa)
    
    print("\n" + "=" * 70)
    print("RECORDING CRYPTOGRAPHIC PROVENANCE FOR CLEANED DATASETS")
    print("=" * 70)
    for cf in sorted(CLEANED_DIR.glob("*.csv")):
        record_provenance(
            source_name=f"Cleaned Dataset: {cf.name}",
            source_url="Local Reproducible Cleaning Pipeline (clean_mplads_data.py)",
            raw_filepath=str(cf),
            http_status=200,
            http_method="LOCAL_PANDAS_TRANSFORMATION",
            notes=f"Cleaned, validated, and type-cast dataset with {len(pd.read_csv(cf))} rows"
        )
        
    print("\n" + "#" * 75)
    print("# Phase 2 Data Cleaning Complete! All 12 Mandates Met.")
    print("#" * 75)
    
    # Trigger dedicated post-cleaning validation & quality reporting engine
    print("\n" + "=" * 70)
    print("TRIGGERING DEDICATED POST-CLEANING VALIDATION & QUALITY REPORT ENGINE")
    print("=" * 70)
    val_script = SCRIPTS_DIR / "07_validate_cleaned_data.py"
    if val_script.exists():
        subprocess.run([sys.executable, str(val_script)], check=True)

if __name__ == "__main__":
    main()
