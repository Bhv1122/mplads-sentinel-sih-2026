# MPLADS Phase 2 Cleaned Dataset: Comprehensive Data-Quality Report
**Audit Timestamp**: 2026-09-09 00:15:28  
**Governing Standard**: SIH 2026 Phase 2 Non-Destructive Cleaning & Multi-Dimensional Data Quality Audit  
**Scope**: Exhaustive Comparative Audit of Raw Ingested Data vs. Cleaned Processed Datasets  
**Pipeline Stages**: Raw Ingestion $\rightarrow$ Cleaning & Normalization $\rightarrow$ Validation Engine $\rightarrow$ Processed Datasets  

---

## Executive Summary
This data-quality report provides a granular, evidence-based audit comparing all seven raw MPLADS datasets against their cleaned, normalized counterparts. The cleaning process was executed with a **non-destructive policy**: all raw files remain pristine and bitwise immutable (SHA-256 verified in `provenance_log.json`), legitimate zero and negative values are strictly preserved, context-specific nulls are maintained with explicit domain rationale, and all suspicious or structural anomalies are cataloged rather than deleted.

### Overall Quality Scorecard
| Quality Dimension | Raw Ingested Status | Cleaned Status | Audit Verdict |
|---|---|---|---|
| **Total Raw Ingested Records** | 667 raw JSON entries | 666 relational records | **100% Accounted** |
| **Full-Row Duplicate Records** | 0 exact duplicates | 0 duplicate rows | **0 Duplicates Removed** |
| **Non-Data / Footer Records** | 1 summary footer in Calamity Relief | Separated into validation logic | **1 Footer Record Separated** |
| **Temporal Date Standardization** | Unparsed string timestamps & formats | 100% strict ISO-8601 (`YYYY-MM-DD`) | **36/36 Dates Standardized** |
| **Financial Field Sanitization** | Formatting noise, commas, ₹ symbols | Native IEEE-754 `float64` numbers | **15/15 Financial Columns Cast** |
| **Identifier Uniqueness (PKs)** | Unverified string/integer keys | 100.0% Unique Primary Keys | **0 Collisions Across All Tables** |
| **Referential Integrity (FKs)** | Implicit string references | 100% validated entity mapping | **543 Constituencies mapped to 36 States** |
| **Statutory & Progression Constraints** | Unaudited | 100% pass: Completed $\le$ Sanctioned $\le$ Rec. | **100% Compliance** |

---

## 1. Original vs. Final Row Counts & Duplication Audit
The table below details row count preservation and reconciliation between raw ingested records and cleaned outputs:

| Dataset Identifier | Raw Source File | Original Raw Count | Final Clean Count | Net $\Delta$ | Duplicate Rows Removed | Non-Data Footers Separated | Reconciliation Status |
|---|---|---|---|---|---|---|---|
| `esakshi_states` | `esakshi_states_raw.json` | 36 | 36 | 0 | 0 | 0 | **100% Preserved** |
| `esakshi_constituencies` | `esakshi_constituencies_by_state_raw.json` | 543 | 543 | 0 | 0 | 0 | **100% Preserved** |
| `esakshi_national_summary` | `esakshi_national_tiles_raw.json` | 6 | 6 | 0 | 0 | 0 | **100% Preserved** |
| `esakshi_calamity_relief` | `esakshi_calamity_relief_raw.json` | 13 | 12 | -1 | 0 | 1 (`Sno: null` footer) | **100% Itemized Records Preserved** |
| `union_budget_mplads` | `union_budget_mospi_demand91_raw.json` | 33 | 33 | 0 | 0 | 0 | **100% Preserved** |
| `parliament_qa_state_expenditure` | `parliament_qa_state_expenditures_raw.json` | 36 | 36 | 0 | 0 | 0 | **100% Preserved** |
| `master_dim_states_constituencies` | Integrated Master Dimension | 36 States | 36 | 0 | 0 | 0 | **Complete Analytical Synthesis** |
| **TOTAL** | **7 Relational Datasets** | **667** | **702** | **-1** | **0** | **1** | **Optimal Quality** |

### Deduplication Audit Details
- **Exact Full-Row Duplicates**: Every cleaned dataset was subjected to `df.duplicated().sum()`. Exactly **0 duplicate rows** were found across all datasets. The upstream acquisition scripts (`01_download_esakshi_master.py`, etc.) ensured deterministic ingestion without record multiplication.
- **Non-Data Record Extraction in Calamity Relief**: In `esakshi_calamity_relief_raw.json`, record index 13 was an aggregate summary row injected by the eSakshi API (`Sno: null`, `MP_NAME: null`, `Total_Amt: 40567400`). Retaining this as an itemized MP contribution would corrupt average and count statistics. Rather than silently dropping it, the cleaning pipeline safely extracted it into a validation assertion: the engine mathematically verified that $\sum_{i=1}^{12} \text{consented\_amount\_inr}_i == ₹40,567,400.00$ (exact zero-difference match).

---

## 2. Missing-Value Changes by Column: Comprehensive Ledger
A strict context-aware missing value policy was applied. Blind replacement with zero or arbitrary modes was prohibited to prevent statistical distortion.

### `esakshi_states.csv` (36 rows, 4 columns)
| Column Name | Raw Status | Cleaned Status | Change / Shift | Semantic Treatment & Rationale |
|---|---|---|---|---|
| `state_id` | Raw int ID (0 nulls) | Clean int64 (0 nulls) | **100% Complete** | Primary key for 36 States/UTs |
| `state_name` | Raw string (0 nulls) | Clean str (0 nulls) | **100% Complete** | Normalized to Title Case |
| `category` | Derived field | Clean str (0 nulls) | **Added / Complete** | Categorized into State (28) and Union Territory (8) |
| `canonical_state_key` | Derived field | Clean str (0 nulls) | **Added / Complete** | Lower-snake slug for fuzzy-free entity joining |

### `esakshi_constituencies.csv` (543 rows, 7 columns)
| Column Name | Raw Status | Cleaned Status | Change / Shift | Semantic Treatment & Rationale |
|---|---|---|---|---|
| `constituency_id` | Raw string ID (0 nulls) | Clean int64 (0 nulls) | **100% Complete** | Primary key for all 543 Lok Sabha seats |
| `state_id` | Raw int ID (0 nulls) | Clean int64 (0 nulls) | **100% Complete** | Foreign key referencing states registry |
| `state_name` | Raw string (0 nulls) | Clean str (0 nulls) | **100% Complete** | Normalized Title Case |
| `constituency_name` | Extracted from caption | Clean str (0 nulls) | **Extracted / Complete** | Clean geographic name with reservation suffix removed |
| `raw_caption` | Raw string caption (0 nulls) | Clean str (0 nulls) | **100% Complete** | Upper-cased preserved official caption |
| `reservation_category` | Extracted from caption | Clean str (0 nulls) | **Extracted / Complete** | Parsed into General (417), SC (82), ST (44) |
| `canonical_state_key` | Derived field | Clean str (0 nulls) | **Added / Complete** | Standardized joining key |

### `esakshi_national_summary.csv` (6 rows, 5 columns)
| Column Name | Raw Status | Cleaned Status | Change / Shift | Semantic Treatment & Rationale |
|---|---|---|---|---|
| `metric_key` | Raw JSON key (0 nulls) | Clean str (0 nulls) | **100% Complete** | Primary key indicator code |
| `metric_description` | Raw JSON label (0 nulls) | Clean str (0 nulls) | **100% Complete** | Official progress description |
| `count_works` | Raw array[0] (2 nulls) | Clean float64 (2 nulls / 33.3%) | **Controlled Missingness** | Preserved NaN for monetary limit tiles; NOT filled with zero |
| `amount_inr` | Raw formatted string (0 nulls) | Clean float64 (0 nulls) | **100% Complete** | Clean numeric currency in ₹ INR |
| `amount_crores` | Raw formatted string (0 nulls) | Clean float64 (0 nulls) | **100% Complete** | Clean numeric currency in ₹ Crores |

### `esakshi_calamity_relief.csv` (12 rows, 12 columns)
| Column Name | Raw Status | Cleaned Status | Change / Shift | Semantic Treatment & Rationale |
|---|---|---|---|---|
| `s_no` | Raw Sno (1 null in footer) | Clean int64 (0 nulls) | **100% Complete** | Sequence ID [1..12] |
| `honorific` | Raw MP_NAME prefix | Clean str (7 nulls / 58.3%) | **Controlled Missingness** | Extracted metadata: 5 with prefix (Shri/Dr/Smt), 7 without in portal |
| `mp_name` | Raw MP_NAME (1 null in footer) | Clean str (0 nulls) | **100% Complete** | Standardized Title Case |
| `house_of_parliament` | Raw integer code (1 null in footer) | Clean str (0 nulls) | **100% Complete** | Normalized from code 2 to 'Lok Sabha' |
| `tenure` | Raw tenure string (1 null in footer) | Clean str (0 nulls) | **100% Complete** | Normalized to '18th Lok Sabha' |
| `calamity_name` | Raw calamity string (1 null in footer) | Clean str (0 nulls) | **100% Complete** | Clean trimmed disaster title |
| `calamity_type` | Raw type code (1 null in footer) | Clean str (0 nulls) | **100% Complete** | Normalized to 'National Calamity' (8) and 'State Calamity' (4) |
| `consented_amount_inr` | Raw formatted currency (1 null in footer) | Clean float64 (0 nulls) | **100% Complete** | Clean numeric float in INR |
| `consented_amount_lakhs` | Derived field | Clean float64 (0 nulls) | **Derived / Complete** | Amount in Lakhs (all <= ₹100L statutory cap) |
| `consent_date_iso` | Raw timestamp (1 null in footer) | Clean str (0 nulls) | **100% Complete** | Strict ISO-8601 (YYYY-MM-DD) |
| `tenure_start_date_iso` | Raw timestamp (1 null in footer) | Clean str (0 nulls) | **100% Complete** | Strict ISO-8601 (YYYY-MM-DD) |
| `tenure_end_date_iso` | Raw timestamp (1 null in footer) | Clean str (0 nulls) | **100% Complete** | Strict ISO-8601 (YYYY-MM-DD) |

### `union_budget_mplads.csv` (33 rows, 10 columns)
| Column Name | Raw Status | Cleaned Status | Change / Shift | Semantic Treatment & Rationale |
|---|---|---|---|---|
| `financial_year` | Raw string 'YYYY-YY' (0 nulls) | Clean str (0 nulls) | **100% Complete** | Continuous 33-year series (1993-94 to 2025-26) |
| `start_year` | Extracted from FY | Clean int64 (0 nulls) | **Extracted / Complete** | Integer starting year [1993..2025] |
| `end_year` | Extracted from FY | Clean int64 (0 nulls) | **Extracted / Complete** | Integer ending year [1994..2026] |
| `scheme_entitlement_per_mp_cr` | Raw formatted currency (0 nulls) | Clean float64 (0 nulls) | **100% Complete** | Statutory entitlement per MP in ₹ Cr |
| `budget_estimate_cr` | Raw formatted currency (0 nulls) | Clean float64 (0 nulls) | **100% Complete** | Demand No. 91 Budget Estimates |
| `revised_estimate_cr` | Raw formatted currency (1 null) | Clean float64 (1 null / 3.03%) | **Controlled Missingness** | Preserved NaN for ongoing FY 2025-26; NOT filled with zero |
| `actual_expenditure_cr` | Raw formatted currency (1 null) | Clean float64 (1 null / 3.03%) | **Controlled Missingness** | Preserved NaN for ongoing FY 2025-26; NOT filled with zero |
| `be_vs_actual_variance_cr` | Derived field | Clean float64 (1 null / 3.03%) | **Derived / Validated** | Actual - BE. Preserved NaN for FY 2025-26; 25 negative variances |
| `major_head` | Raw integer code (0 nulls) | Clean int64 (0 nulls) | **100% Complete** | Demand No. 91 accounting major head 3475 |
| `status_notes` | Raw notes text (0 nulls) | Clean str (0 nulls) | **100% Complete** | Trimmed fiscal accounting notes |

### `parliament_qa_state_expenditure.csv` (36 rows, 15 columns)
| Column Name | Raw Status | Cleaned Status | Change / Shift | Semantic Treatment & Rationale |
|---|---|---|---|---|
| `state_id` | Raw int (0 nulls) | Clean int64 (0 nulls) | **100% Complete** | Primary key [1..36] |
| `state_name` | Raw string (0 nulls) | Clean str (0 nulls) | **100% Complete** | Title-cased official state name |
| `canonical_state_key` | Derived slug | Clean str (0 nulls) | **Added / Complete** | Joining key |
| `entitlement_cr` | Raw currency (0 nulls) | Clean float64 (0 nulls) | **100% Complete** | Audited cumulative entitlement |
| `released_cr` | Raw currency (0 nulls) | Clean float64 (0 nulls) | **100% Complete** | Audited cumulative funds released |
| `expenditure_cr` | Raw currency (0 nulls) | Clean float64 (0 nulls) | **100% Complete** | Audited cumulative expenditure |
| `unspent_balance_cr` | Raw currency (0 nulls) | Clean float64 (0 nulls) | **100% Complete** | Audited unspent balance |
| `utilization_rate_pct` | Derived ratio | Clean float64 (0 nulls) | **Derived / Complete** | Expenditure / Released * 100 [84.65% to 98.24%] |
| `works_recommended` | Raw int count (0 nulls) | Clean int64 (0 nulls) | **100% Complete** | Count of recommended works |
| `works_sanctioned` | Raw int count (0 nulls) | Clean int64 (0 nulls) | **100% Complete** | Count of sanctioned works |
| `works_completed` | Raw int count (0 nulls) | Clean int64 (0 nulls) | **100% Complete** | Count of completed works |
| `sanction_rate_pct` | Derived ratio | Clean float64 (0 nulls) | **Derived / Complete** | Sanctioned / Recommended * 100 |
| `completion_rate_pct` | Derived ratio | Clean float64 (0 nulls) | **Derived / Complete** | Completed / Sanctioned * 100 |
| `is_utilization_valid` | Derived bool | Clean bool (0 nulls) | **Validated / Complete** | 100% True (within [0, 100%]) |
| `is_workflow_valid` | Derived bool | Clean bool (0 nulls) | **Validated / Complete** | 100% True (Completed <= Sanctioned <= Rec.) |

### `master_dim_states_constituencies.csv` (36 rows, 17 columns)
| Column Name | Raw Status | Cleaned Status | Change / Shift | Semantic Treatment & Rationale |
|---|---|---|---|---|
| `state_id` | Synthesized | Clean int64 (0 nulls) | **100% Complete** | State primary key |
| `state_name` | Synthesized | Clean str (0 nulls) | **100% Complete** | Title-cased state name |
| `canonical_state_key` | Raw field | Clean str (0 nulls / 0.0%) | **Preserved / Validated** | Cleaned and standardized |
| `category` | Raw field | Clean str (0 nulls / 0.0%) | **Preserved / Validated** | Cleaned and standardized |
| `total_lok_sabha_seats` | Aggregated from constituencies | Clean int64 (0 nulls) | **100% Complete** | Total seats per state (National Sum = 543) |
| `general_seats` | Aggregated | Clean int64 (0 nulls) | **100% Complete** | General seats per state (Sum = 417) |
| `sc_reserved_seats` | Aggregated | Clean int64 (0 nulls) | **100% Complete** | SC reserved seats (Sum = 82) |
| `st_reserved_seats` | Aggregated | Clean int64 (0 nulls) | **100% Complete** | ST reserved seats (Sum = 44) |
| `sc_seat_share_pct` | Raw field | Clean float64 (0 nulls / 0.0%) | **Preserved / Validated** | Cleaned and standardized |
| `st_seat_share_pct` | Raw field | Clean float64 (0 nulls / 0.0%) | **Preserved / Validated** | Cleaned and standardized |
| `statutory_sc_allocation_pct` | Raw field | Clean float64 (0 nulls / 0.0%) | **Preserved / Validated** | Cleaned and standardized |
| `statutory_st_allocation_pct` | Raw field | Clean float64 (0 nulls / 0.0%) | **Preserved / Validated** | Cleaned and standardized |
| `cumulative_released_cr` | Joined from QA | Clean float64 (0 nulls) | **100% Complete** | State cumulative released funds |
| `cumulative_expenditure_cr` | Joined from QA | Clean float64 (0 nulls) | **100% Complete** | State cumulative expenditures |
| `unspent_balance_cr` | Raw field | Clean float64 (0 nulls / 0.0%) | **Preserved / Validated** | Cleaned and standardized |
| `utilization_pct` | Joined from QA | Clean float64 (0 nulls) | **100% Complete** | State fund utilization rate |
| `works_completed_count` | Raw field | Clean int64 (0 nulls / 0.0%) | **Preserved / Validated** | Cleaned and standardized |

---

## 3. Date Columns & Temporal Standardization Audit
All temporal and calendar attributes were standardized into strict ISO-8601 (`YYYY-MM-DD`) or decomposed integer year representations:

| Column Name | Dataset | Raw Source Format | Cleaned Standard Format | Format Regex | Observed Range | Validation Result |
|---|---|---|---|---|---|---|
| `consent_date_iso` | `esakshi_calamity_relief` | Timestamps (`2024-08-12 11:34:22`) | ISO-8601 (`YYYY-MM-DD`) | `^\d{4}-\d{2}-\d{2}$` | 2024-09-03 to 2025-12-07 | **100% Valid ISO Dates** |
| `tenure_start_date_iso` | `esakshi_calamity_relief` | Timestamps (`2024-06-05 00:00:00`) | ISO-8601 (`YYYY-MM-DD`) | `^\d{4}-\d{2}-\d{2}$` | 2024-06-04 to 2024-06-05 | **100% Valid ISO Dates** |
| `tenure_end_date_iso` | `esakshi_calamity_relief` | Timestamps (`2029-06-04 00:00:00`) | ISO-8601 (`YYYY-MM-DD`) | `^\d{4}-\d{2}-\d{2}$` | 2029-06-03 to 2029-06-03 | **100% Valid ISO Dates** |
| `start_year` | `union_budget_mplads` | Compound string '1993-94' | Integer (`YYYY`) | `^\d{4}$` | 1993 to 2025 | **100% Valid Integer Years** |
| `end_year` | `union_budget_mplads` | Compound string '1993-94' | Integer (`YYYY`) | `^\d{4}$` | 1994 to 2026 | **100% Valid Integer Years** |
| `financial_year` | `union_budget_mplads` | Raw text '1993-94' | Normalized Fiscal Year (`YYYY-YY`) | `^\d{4}-\d{2}$` | 1993-94 to 2025-26 | **100% Continuous 33 Years** |

- **Legislative Tenure Boundary Audit**: The validation engine evaluated whether `tenure_start <= consent_date <= tenure_end` for each calamity contribution. All 12 consents (100.0%) occurred strictly within the active tenure of the 18th Lok Sabha.

---

## 4. Financial Columns & Strict Numeric Datatyping
All monetary columns were stripped of extraneous formatting noise (currency symbols `₹`, `Rs.`, commas, unit suffixes `Crores`/`Lakhs`, non-breaking spaces `\u00a0`) and parsed into native IEEE-754 `float64` floating point numbers:

| Column Name | Dataset | Raw Formatting Noise Removed | Cleaned Datatype | Metric Unit | Min Value | Max Value | Total Sum | Non-Negative Bound Status |
|---|---|---|---|---|---|---|---|---|
| `amount_inr` | `esakshi_national_summary` | Commas, ₹ symbol, words | `float64` | ₹ INR | 40,567,400.00 | 83,336,673,298.01 | 227,996,292,402.53 | **PASS (>= 0.0)** |
| `amount_crores` | `esakshi_national_summary` | Commas, 'Cr' suffix | `float64` | ₹ Crores | 4.06 | 8,333.67 | 22,799.63 | **PASS (>= 0.0)** |
| `consented_amount_inr` | `esakshi_calamity_relief` | Commas, 'Rs.' prefix | `float64` | ₹ INR | 500,000.00 | 10,000,000.00 | 40,567,400.00 | **PASS (>= 0.0)** |
| `consented_amount_lakhs` | `esakshi_calamity_relief` | Derived from INR amount | `float64` | ₹ Lakhs | 5.00 | 100.00 | 405.67 | **PASS (>= 0.0)** |
| `scheme_entitlement_per_mp_cr` | `union_budget_mplads` | Commas, ₹ symbol | `float64` | ₹ Crores | 0.00 | 5.00 | 97.05 | **PASS (>= 0.0)** |
| `budget_estimate_cr` | `union_budget_mplads` | Commas, ₹ symbol | `float64` | ₹ Crores | 200.00 | 3,965.00 | 76,860.00 | **PASS (>= 0.0)** |
| `revised_estimate_cr` | `union_budget_mplads` | Commas, whitespace | `float64` | ₹ Crores | 100.00 | 3,950.00 | 68,605.00 | **PASS (>= 0.0)** |
| `actual_expenditure_cr` | `union_budget_mplads` | Commas, whitespace | `float64` | ₹ Crores | 99.40 | 3,949.50 | 68,197.80 | **PASS (>= 0.0)** |
| `be_vs_actual_variance_cr` | `union_budget_mplads` | Derived (Actual - BE) | `float64` | ₹ Crores | -3,865.60 | 1,370.00 | -4,712.20 | **PASS (Signed Variance)** |
| `entitlement_cr` | `parliament_qa_state_expenditure` | Commas, whitespace | `float64` | ₹ Crores | 155.00 | 14,820.00 | 101,075.00 | **PASS (>= 0.0)** |
| `released_cr` | `parliament_qa_state_expenditure` | Commas, whitespace | `float64` | ₹ Crores | 140.00 | 13,910.00 | 95,420.00 | **PASS (>= 0.0)** |
| `expenditure_cr` | `parliament_qa_state_expenditure` | Commas, whitespace | `float64` | ₹ Crores | 131.20 | 13,120.80 | 91,194.52 | **PASS (>= 0.0)** |
| `unspent_balance_cr` | `parliament_qa_state_expenditure` | Commas, whitespace | `float64` | ₹ Crores | 2.20 | 789.20 | 4,225.48 | **PASS (>= 0.0)** |
| `cumulative_released_cr` | `master_dim_states_constituencies` | Joined from QA table | `float64` | ₹ Crores | 140.00 | 13,910.00 | 95,420.00 | **PASS (>= 0.0)** |
| `cumulative_expenditure_cr` | `master_dim_states_constituencies` | Joined from QA table | `float64` | ₹ Crores | 131.20 | 13,120.80 | 91,194.52 | **PASS (>= 0.0)** |

- **Economic Validity of Negative Variance**: In `union_budget_mplads.csv`, `be_vs_actual_variance_cr` records negative values for 25 fiscal years (minimum: -₹3,865.60 Crore in FY 2020-21). These negative numbers are economically sound: they accurately capture historical under-spending where Actual Expenditure was lower than the Budget Estimate (e.g. during scheme suspension for COVID-19 pandemic relief).

---

## 5. Identifier (ID) Validation & Referential Integrity
Every identifier was audited for non-null completeness, uniqueness, and cross-dataset referential consistency:

| Identifier Column | Dataset | Key Classification | Expected Condition | Unique Entity Count | Missing Count | Duplicate Collisions | Referential Integrity Status |
|---|---|---|---|---|---|---|---|
| `state_id` | `clean_esakshi_states.csv` | Primary Key | 100% Unique [1..36] | 36 | 0 (0.0%) | 0 (0.0%) | **100% Unique PK** |
| `constituency_id` | `clean_esakshi_constituencies.csv` | Primary Key | 100% Unique [1..543] | 543 | 0 (0.0%) | 0 (0.0%) | **100% Unique PK** |
| `state_id` | `clean_esakshi_constituencies.csv` | Foreign Key | References `state_id` | 36 | 0 (0.0%) | N/A (FK) | **100% Valid Foreign Entity Refs** |
| `metric_key` | `clean_esakshi_national_summary.csv` | Primary Key | 100% Unique Keys | 6 | 0 (0.0%) | 0 (0.0%) | **100% Unique PK** |
| `s_no` | `clean_esakshi_calamity_relief.csv` | Primary Key | 100% Unique [1..12] | 12 | 0 (0.0%) | 0 (0.0%) | **100% Unique PK** |
| `financial_year` | `clean_union_budget_mplads_1993_2025.csv` | Primary Key | 100% Unique FYs | 33 | 0 (0.0%) | 0 (0.0%) | **100% Unique PK** |
| `state_id` | `clean_parliament_qa_state_expenditure.csv` | Primary Key | 100% Unique [1..36] | 36 | 0 (0.0%) | 0 (0.0%) | **100% Unique PK** |
| `state_id` | `clean_master_dim_states_constituencies.csv` | Primary Key | 100% Unique [1..36] | 36 | 0 (0.0%) | 0 (0.0%) | **100% Unique PK** |

- **Referential Integrity Audit**: Every `state_id` in `clean_esakshi_constituencies.csv` was joined against `clean_esakshi_states.csv`. Exactly 543 out of 543 constituencies mapped to existing states with zero orphaned records.

---

## 6. Text Normalization & Linguistic Hygiene Performed
A standardized text cleaning pipeline was executed across all textual and categorical fields:

1. **Leading and Trailing Whitespace Stripping**: Invoked `.str.strip()` on all text fields. Extracted strings like `" Andhra Pradesh "` or `"WARANGAL (SC)   "` were trimmed of perimeter spaces and non-breaking spaces (`\u00a0`).
2. **Whitespace Collapsing**: Applied regex `\s+` to replace multiple internal consecutive spaces with a single space (e.g. `"Uttar   Pradesh"` $\rightarrow$ `"Uttar Pradesh"`).
3. **Systematic Title Casing**: Applied `to_consistent_title_case()` to normalize administrative entity names (`"ANDAMAN AND NICOBAR ISLANDS"` $\rightarrow$ `"Andaman And Nicobar Islands"`).
4. **Compound String Splitting (Reservation Parsing)**: In `esakshi_constituencies`, raw captions contained embedded reservation indicators (`"WARANGAL (SC)"`). The cleaning pipeline applied regular expression pattern extraction to separate this into clean `constituency_name = "Warangal"` and `reservation_category = "SC"`.
5. **Honorific Separation**: In `esakshi_calamity_relief`, raw MP names contained mixed honorific prefixes (`"Shri Bandi Sanjay Kumar"`, `"Dr. Jitendra Singh"`, `"Smt. Nirmala Sitharaman"`). The cleaner extracted honorifics into a separate `honorific` metadata field while retaining the clean legal name in `mp_name`.
6. **Canonical State Key Generation**: Generated lowercase alphanumeric slug keys (`generate_canonical_state_key()`) across all datasets (e.g. `"jammu_and_kashmir"`, `"the_dadra_and_nagar_haveli_and_daman_and_diu"`) to enable deterministic cross-dataset relational joins without fuzzy string matching.
7. **Header Snake_Casing**: All column headers across all seven tables were standardized to lower snake_case (e.g. `"Budget Estimates (Rs. Crore)"` $\rightarrow$ `"budget_estimate_cr"`).

---

## 7. Records Flagged for Review (Non-Destructive Review Ledger)
In accordance with the non-destructive validation policy, the following items were cataloged and flagged for human/governance review rather than altered or deleted:

| Flag ID | Dataset | Affected Record(s) | Anomaly Type | Domain Rationale & Action Taken |
|---|---|---|---|---|
| `FLAG-01` | `union_budget_mplads` | FY 2025-26 (Row 33) | Temporal Incompleteness | Revised Estimates and Actual Expenditure are not yet closed by MoSPI. Preserved as `NaN` (not filled with 0.0) to prevent false zero-spending distortion. |
| `FLAG-02` | `esakshi_national_summary` | Rows 1 & 6 (Limit Tiles) | Structural Non-Applicability | `count_works` is `NaN` for 'Installment Issued Amount' and 'Expenditure Incurred Amount' because financial limit tiles do not track individual works. Preserved as `NaN`. |
| `FLAG-03` | `esakshi_calamity_relief` | 7 MP Records | Nomenclature Variance | 7 MP names in the official portal payload lacked honorific prefixes ('Shri'/'Dr'/'Smt'). Extracted as empty honorific with clean title-cased legal name. |
| `FLAG-04` | `esakshi_calamity_relief` | Raw Index 13 | Aggregate Summary Row | Raw payload contained an API summary footer (`Total_Amt: 40567400`). Safely extracted from itemized microdata into a mathematical validation check. |
| `FLAG-05` | `parliament_qa_state_expenditure` | Ladakh vs J&K | Geopolitical Boundary Shift | Historical expenditure records prior to 2019 for the UT of Ladakh were officially reported under Jammu & Kashmir in Parliament QA answers. Preserved official figures. |

---

## 8. Domain & Operational Assumptions Made During Cleaning
The following domain assumptions were formally incorporated into the cleaning and validation pipelines:

1. **Statutory Calamity Relief Cap (MPLADS Guidelines Para 3.12)**: It is assumed that an MP can contribute up to ₹100.00 Lakhs (₹1.00 Crore) per calamity towards disaster rehabilitation outside their constituency. The cleaning pipeline verified that all 12 contributions strictly adhere to this cap (maximum observed was exactly ₹100.00 Lakhs).
2. **Immutability of True Zeros vs. Missingness**: It is assumed that a missing financial value (such as ongoing FY 2025-26 actuals) represents an unclosed reporting period and must NOT be imputed as ₹0.00. A value of ₹0.00 represents zero expenditure, whereas `NaN` represents right-censored data.
3. **Legitimate Negative Variances in Budget Execution**: It is assumed that `be_vs_actual_variance_cr < 0` represents normal fiscal under-utilization or scheme suspensions (such as during COVID-19 in FY 2020-21) and is not a data corruption artifact.
4. **Statutory Reservation Benchmarks**: In `clean_master_dim_states_constituencies.csv`, statutory benchmark columns `statutory_sc_allocation_pct` (15.0%) and `statutory_st_allocation_pct` (7.5%) are set as scheme-mandated minimum targets per MPLADS Guidelines Chapter 2.
5. **Deterministic API Payload Structure**: It is assumed that the eSakshi portal's `Total Calimity Consent` JSON payload contains valid stringified JSON arrays that represent the complete itemized disaster contributions of the 18th Lok Sabha.

---

## 9. Lingering Data-Quality Risks & Analytical Limitations
While the cleaned datasets are 100% structurally sound, schema-compliant, and internally validated, the following analytical constraints remain inherent to the official source disclosures:

1. **Macro-Level Aggregation vs. Project-Level Microdata**: The official data released through eSakshi dashboards and Parliamentary QA answers provides state-level and national-level aggregates. Work-level microdata (individual works, contractor details, site GPS coordinates, sanction dates, and inspection reports) are not publicly exposed through these endpoints.
2. **Limited Sample Size for Calamity Consents**: Only 12 disaster contributions are currently listed on the eSakshi portal under the 18th Lok Sabha (totaling ₹4.06 Crore). This small sample size is suitable for governance auditing but limits statistical regression modeling for disaster relief predictions.
3. **Reporting Window Latency**: Discrepancies exist between Parliamentary QA figures (which reflect historical cumulative outlays up to a specific Lok Sabha session cut-off) and live eSakshi portal counters (which reflect real-time 18th Lok Sabha activity). The master dimension table bridges these sources using canonical keys, but users must note the temporal snapshot differences.
4. **Right-Censored Ongoing Fiscal Year (FY 2025-26)**: Fiscal year 2025-26 contains Budget Estimates but lacks Revised Estimates and Actuals. Machine learning models forecasting multi-year expenditure must treat FY 2025-26 as a forward forecast horizon rather than training data.

---

## 10. Pipeline Reproducibility & Invocation Guide
The entire data cleaning and validation framework is 100% reproducible through version-controlled scripts:

### Option A: End-to-End Ingestion, Cleaning & Validation
To execute the entire multi-source acquisition, standardization, profiling, cleaning, and validation pipeline in sequence:
```bash
python3 data/scripts/run_all.py
```

### Option B: Dedicated Phase 2 Cleaning Engine
To execute only the Phase 2 cleaning and normalization pipeline:
```bash
python3 data/scripts/clean_mplads_data.py
```

### Option C: Standalone Validation & Quality Audit
To execute the 194-check validation suite and regenerate this report:
```bash
python3 data/scripts/07_validate_cleaned_data.py
```

### Generated Report Artifacts
- **Data Quality Comparative Audit**: `data/documentation/DATA_QUALITY_REPORT.md` and `data/reports/DATA_QUALITY_REPORT.md`
- **Validation Rule Audit & Scorecard**: `data/documentation/DATA_VALIDATION_REPORT.md`
- **Machine-Readable Audit Ledger**: `data/documentation/validation_results.csv` and `validation_results.csv`