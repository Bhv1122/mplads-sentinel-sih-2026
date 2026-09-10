# MPLADS Phase 2 Data Cleaning & Normalization Audit Report
**Project**: SIH 2026 – Member of Parliament Local Area Development Scheme (MPLADS) Data & Governance Analytics  
**Date**: September 2026  
**Status**: Executed & Verified  
**Target Directory**: `data/cleaned/`  

---

## 1. Executive Summary

In Phase 2, a complete data cleaning, type-casting, and integrity validation pipeline was executed via [`clean_mplads_data.py`](file:///Users/vinxy/SIH%202026/data/scripts/clean_mplads_data.py) using Python and Pandas. 

> [!IMPORTANT]
> **Preservation of Raw Data**: All original files in `data/raw/` remain 100% untouched and preserved in their native byte format. All cleaning was applied non-destructively to produce standardized, validated tables in `data/cleaned/` and `data/processed/`.

---

## 2. Table-by-Table Cleaning Operations & Schema Audits

### 2.1 `clean_esakshi_states.csv` (36 rows)
- **Transformations**:
  - `state_id`: Cast to native `int`.
  - `state_name`: Trimmed and formatted to standard Title Case.
  - `category`: Verified classification (`28 States`, `8 Union Territories`).
  - Added `canonical_state_key`: Normalized lowercase key with stripped `"the"` and replaced `&` with `"and"` for 100% deterministic entity resolution across government datasets.

### 2.2 `clean_esakshi_constituencies.csv` (543 rows)
- **Transformations**:
  - `constituency_id`: Validated continuous range `[1, 548]` with exactly 543 unique seats.
  - `constituency_name`: Cleaned name stripping embedded reservation indicators (`(SC)` and `(ST)`).
  - `reservation_category`: Extracted explicit statutory category (`General: 417`, `SC: 82`, `ST: 44`).
  - Added `canonical_state_key`: Foreign key reference to canonical state dimension.

### 2.3 `clean_esakshi_national_summary.csv` (6 rows)
- **Transformations**:
  - `metric_key` & `metric_description`: Stripped leading/trailing whitespace.
  - `count_works`: Cast to integer (preserved nulls for purely monetary limit tiles).
  - `amount_inr`: Normalized Indian comma-separated currency strings into clean 2-decimal floats.
  - `amount_crores`: Derived and formatted standard Crores denomination.

### 2.4 `clean_esakshi_calamity_relief.csv` (12 rows)
- **Transformations**:
  - Separated `honorific` (`"Shri"`, `"Dr"`) from canonical `mp_name` formatted to Title Case.
  - Standardized `consent_date_iso`, `tenure_start_date_iso`, and `tenure_end_date_iso` from variable strings (`"07-Dec-2025"`, `"Jun 4, 2024 12:00:00 AM"`) to strict ISO-8601 (`YYYY-MM-DD`).
  - Verified `consented_amount_inr` and computed `consented_amount_lakhs` (`amount / 100000.0`).

### 2.5 `clean_union_budget_mplads_1993_2025.csv` (33 rows)
- **Transformations**:
  - Extracted numeric `start_year` (e.g. `1993`) and `end_year` (e.g. `1994`) from `financial_year` string (`"1993-94"`).
  - Verified major accounting head `3475` (Special Programmes for Rural Development / MPLADS).
  - Preserved nullability for ongoing fiscal year (FY 2025–26) for `revised_estimate_cr` and `actual_expenditure_cr`.

### 2.6 `clean_parliament_qa_state_expenditure.csv` (36 rows)
- **Transformations**:
  - Added `canonical_state_key` for seamless cross-table joins.
  - Standardized financial fields (`entitlement_cr`, `released_cr`, `expenditure_cr`, `unspent_balance_cr`) to 2-decimal floats.
  - Logic validation flags added:
    * `is_utilization_valid`: Boolean flag checking `0.0 <= utilization_rate_pct <= 100.0` (Result: **100% TRUE**).
    * `is_workflow_valid`: Boolean flag verifying physical progression `works_completed <= works_sanctioned <= works_recommended` (Result: **100% TRUE**).

### 2.7 `clean_master_dim_states_constituencies.csv` (36 rows)
- **Transformations**:
  - Consolidated analytical dimension combining state geography, seat reservation counts, and audited spending.
  - Added `sc_seat_share_pct` and `st_seat_share_pct` computed directly from constituency master.
  - Included statutory benchmarks (`statutory_sc_allocation_pct`: 15.0%, `statutory_st_allocation_pct`: 7.5%).
  - **Zero missing values (0.0% nulls)** across all 36 States and Union Territories.

---

## 3. Data Integrity & Validation Summary

| Dataset | Row Count | Null % in PKs | Date Format Compliance | Workflow Logic Valid |
|---|---|---|---|---|
| `clean_esakshi_states.csv` | 36 | 0.0% | N/A | Valid |
| `clean_esakshi_constituencies.csv` | 543 | 0.0% | N/A | Valid |
| `clean_esakshi_national_summary.csv` | 6 | 0.0% | N/A | Valid |
| `clean_esakshi_calamity_relief.csv` | 12 | 0.0% | 100% ISO-8601 | Valid |
| `clean_union_budget_mplads_1993_2025.csv` | 33 | 0.0% | 100% Start/End Years | Valid |
| `clean_parliament_qa_state_expenditure.csv` | 36 | 0.0% | N/A | 100% Passed (`exp <= rel`, `comp <= sanc <= rec`) |
| `clean_master_dim_states_constituencies.csv` | 36 | 0.0% | N/A | 100% Passed (0% nulls) |
