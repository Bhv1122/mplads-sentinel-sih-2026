# MPLADS PostgreSQL Database Validation Report

**Execution Timestamp**: `2026-09-09 00:15:30`  
**Database**: `mplads_db` on `localhost:5432`  
**Database Role**: `vinxy`  
**Total Checks Executed**: `63` | **Passed**: `63` (`100.0%`) | **Warnings**: `0` | **Critical Failures**: `0`  

---

## Executive Validation Summary

| Verification Area | Checks Performed | Status | Verdict |
|---|:---:|:---:|---|
| **Boundary Verification** | 4 | **PASS** | All 4 checks passed |
| **Data Preservation** | 3 | **PASS** | All 3 checks passed |
| **Domain Constraints** | 2 | **PASS** | All 2 checks passed |
| **Financial Consistency** | 3 | **PASS** | All 3 checks passed |
| **Geographic Verification** | 1 | **PASS** | All 1 checks passed |
| **Prohibited Values** | 1 | **PASS** | All 1 checks passed |
| **Project Completeness** | 3 | **PASS** | All 3 checks passed |
| **Referential Integrity** | 11 | **PASS** | All 11 checks passed |
| **Required Field Completeness** | 8 | **PASS** | All 8 checks passed |
| **Row Count Reconciliation** | 14 | **PASS** | All 14 checks passed |
| **Temporal Chronology** | 6 | **PASS** | All 6 checks passed |
| **Uniqueness Constraints** | 7 | **PASS** | All 7 checks passed |

---

## Granular Results Ledger

| Category | Test Check | Expected Condition | Actual Condition | Status | Details |
|---|---|---|---|:---:|---|
| Row Count Reconciliation | Table: projects | 20 rows (CSV) | 20 rows (DB) | **PASS** | Source: clean_projects.csv |
| Row Count Reconciliation | Table: financials | 20 rows (CSV) | 20 rows (DB) | **PASS** | Source: clean_financials.csv |
| Row Count Reconciliation | Table: progress | 20 rows (CSV) | 20 rows (DB) | **PASS** | Source: clean_progress.csv |
| Row Count Reconciliation | Table: risk_scores | 20 rows (CSV) | 20 rows (DB) | **PASS** | Source: clean_risk_scores.csv |
| Row Count Reconciliation | Table: risk_factors | 22 rows (CSV) | 22 rows (DB) | **PASS** | Source: clean_risk_factors.csv |
| Row Count Reconciliation | Table: project_history | 68 rows (CSV) | 68 rows (DB) | **PASS** | Source: clean_project_history.csv |
| Row Count Reconciliation | Table: states | 36 rows (CSV) | 36 rows (DB) | **PASS** | Source: clean_esakshi_states.csv |
| Row Count Reconciliation | Table: constituencies | 543 rows (CSV) | 543 rows (DB) | **PASS** | Source: clean_esakshi_constituencies.csv |
| Row Count Reconciliation | Table: national_summary | 6 rows (CSV) | 6 rows (DB) | **PASS** | Source: clean_esakshi_national_summary.csv |
| Row Count Reconciliation | Table: calamity_relief | 12 rows (CSV) | 12 rows (DB) | **PASS** | Source: clean_esakshi_calamity_relief.csv |
| Row Count Reconciliation | Table: union_budget | 33 rows (CSV) | 33 rows (DB) | **PASS** | Source: clean_union_budget_mplads_1993_2025.csv |
| Row Count Reconciliation | Table: parliament_qa_state_expenditure | 36 rows (CSV) | 36 rows (DB) | **PASS** | Source: clean_parliament_qa_state_expenditure.csv |
| Row Count Reconciliation | Table: master_dim_states_constituencies | 36 rows (CSV) | 36 rows (DB) | **PASS** | Source: clean_master_dim_states_constituencies.csv |
| Row Count Reconciliation | Total Ingested Relational Rows | 872 rows | 872 rows | **PASS** | Aggregated across all 13 domain tables |
| Project Completeness | Expected Project IDs Loaded | 20 expected IDs (0 missing) | 20 loaded IDs (0 missing) | **PASS** | All expected projects present |
| Project Completeness | No Unexpected / Rogue Project IDs | 0 unexpected IDs | 0 unexpected IDs | **PASS** |  |
| Project Completeness | All Project Codes Reconciled | 20 expected codes | 20 loaded codes (0 missing) | **PASS** |  |
| Uniqueness Constraints | Zero Duplicate project_id in projects | 0 duplicates | 0 duplicate IDs | **PASS** |  |
| Uniqueness Constraints | Zero Duplicate project_code in projects | 0 duplicates | 0 duplicate codes | **PASS** |  |
| Uniqueness Constraints | Zero Duplicate project_id in financials | 0 duplicates | 0 duplicate project financial records | **PASS** |  |
| Uniqueness Constraints | Unique (project_id, reported_date) in progress | 0 duplicates | 0 duplicate progress reports | **PASS** |  |
| Uniqueness Constraints | Zero Duplicate project_id in risk_scores | 0 duplicates | 0 duplicate risk score records | **PASS** |  |
| Uniqueness Constraints | Unique (risk_score_id, factor_name) in risk_factors | 0 duplicates | 0 duplicate risk factor entries | **PASS** |  |
| Uniqueness Constraints | Unique (project_id, event_type, timestamp) in project_history | 0 duplicates | 0 duplicate history entries | **PASS** |  |
| Referential Integrity | FK: projects -> states | 0 orphaned records | 0 orphaned records | **PASS** | projects.state_id -> states.state_id |
| Referential Integrity | FK: projects -> constituencies | 0 orphaned records | 0 orphaned records | **PASS** | projects.constituency_id -> constituencies.constituency_id |
| Referential Integrity | FK: financials -> projects | 0 orphaned records | 0 orphaned records | **PASS** | financials.project_id -> projects.project_id |
| Referential Integrity | FK: progress -> projects | 0 orphaned records | 0 orphaned records | **PASS** | progress.project_id -> projects.project_id |
| Referential Integrity | FK: risk_scores -> projects | 0 orphaned records | 0 orphaned records | **PASS** | risk_scores.project_id -> projects.project_id |
| Referential Integrity | FK: risk_factors -> risk_scores | 0 orphaned records | 0 orphaned records | **PASS** | risk_factors.risk_score_id -> risk_scores.risk_score_id |
| Referential Integrity | FK: risk_factors -> projects | 0 orphaned records | 0 orphaned records | **PASS** | risk_factors.project_id -> projects.project_id |
| Referential Integrity | FK: project_history -> projects | 0 orphaned records | 0 orphaned records | **PASS** | project_history.project_id -> projects.project_id |
| Referential Integrity | FK: constituencies -> states | 0 orphaned records | 0 orphaned records | **PASS** | constituencies.state_id -> states.state_id |
| Referential Integrity | FK: parliament_qa -> states | 0 orphaned records | 0 orphaned records | **PASS** | parliament_qa_state_expenditure.canonical_state_key -> states.canonical_state_key |
| Referential Integrity | FK: master_dim -> states | 0 orphaned records | 0 orphaned records | **PASS** | master_dim_states_constituencies.state_id -> states.state_id |
| Required Field Completeness | No NULLs in required fields: projects | 0 NULLs | 0 NULL records | **PASS** | Audited columns: project_id, project_code, project_title, sector... |
| Required Field Completeness | No NULLs in required fields: financials | 0 NULLs | 0 NULL records | **PASS** | Audited columns: financial_id, project_id, currency, recommended_amount... |
| Required Field Completeness | No NULLs in required fields: progress | 0 NULLs | 0 NULL records | **PASS** | Audited columns: progress_id, project_id, reported_date, physical_progress_pct... |
| Required Field Completeness | No NULLs in required fields: risk_scores | 0 NULLs | 0 NULL records | **PASS** | Audited columns: risk_score_id, project_id, overall_risk_score, delay_risk_score... |
| Required Field Completeness | No NULLs in required fields: risk_factors | 0 NULLs | 0 NULL records | **PASS** | Audited columns: factor_id, risk_score_id, project_id, factor_category... |
| Required Field Completeness | No NULLs in required fields: project_history | 0 NULLs | 0 NULL records | **PASS** | Audited columns: history_id, project_id, event_type, new_status... |
| Required Field Completeness | No NULLs in required fields: states | 0 NULLs | 0 NULL records | **PASS** | Audited columns: state_id, state_name, category, canonical_state_key... |
| Required Field Completeness | No NULLs in required fields: constituencies | 0 NULLs | 0 NULL records | **PASS** | Audited columns: constituency_id, state_id, state_name, constituency_name... |
| Temporal Chronology | Sanction Date >= Recommendation Date | 0 chronological violations | 0 violations | **PASS** |  |
| Temporal Chronology | Work Order Date >= Sanction Date | 0 chronological violations | 0 violations | **PASS** |  |
| Temporal Chronology | Actual Completion Date >= Work Order Date | 0 chronological violations | 0 violations | **PASS** |  |
| Temporal Chronology | Expected Completion Date >= Work Order Date | 0 chronological violations | 0 violations | **PASS** |  |
| Temporal Chronology | Inspection Date >= Project Recommendation Date | 0 chronological violations | 0 violations | **PASS** |  |
| Temporal Chronology | Disaster Relief Consent within MP Tenure | 0 violations | 0 violations | **PASS** |  |
| Financial Consistency | Unspent Balance Calculation (Released - Expenditure) | 0 calculation mismatches | 0 mismatches | **PASS** |  |
| Financial Consistency | Utilization Rate Percentage Formula Match | 0 formula discrepancies | 0 discrepancies | **PASS** |  |
| Financial Consistency | Cost Overrun Flagged when Expenditure > Sanctioned | 0 unflagged overruns | 0 unflagged overruns | **PASS** |  |
| Prohibited Values | Non-Negative Project Financial Amounts | 0 negative values | 0 negative values | **PASS** |  |
| Boundary Verification | Physical & Financial Progress Percentages [0, 100] | 0 out-of-bound percentages | 0 out-of-bound records | **PASS** |  |
| Boundary Verification | Days Delayed Non-Negative (>= 0) | 0 negative values | 0 negative delay values | **PASS** |  |
| Boundary Verification | Risk Score Sub-dimensions in [0, 100] | 0 out-of-bound scores | 0 out-of-bound scores | **PASS** |  |
| Boundary Verification | Confidence & Factor Weights in [0.0, 1.0] | 0 out-of-bound weights | 0 out-of-bound weights | **PASS** |  |
| Geographic Verification | Geo-tagging Coordinates within India Territory | 0 invalid coordinates | 0 invalid coordinates | **PASS** |  |
| Domain Constraints | Project Status & Parliament House Categoricals | 0 invalid categories | 0 invalid entries | **PASS** |  |
| Domain Constraints | Risk Score Levels ('Low', 'Moderate', 'High', 'Critical') | 0 invalid levels | 0 invalid levels | **PASS** |  |
| Data Preservation | Ongoing Projects Completion Date NULL (Preserved) | 12 records NULL (8 completed, 12 ongoing/stalled) | 12 records NULL | **PASS** |  |
| Data Preservation | Ongoing FY 2025-26 Actual Outlay Preserved as NULL | 1 record NULL | 1 record NULL | **PASS** |  |
| Data Preservation | Macro Financial Limit Works Count Preserved as NULL | 2 records NULL | 2 records NULL | **PASS** |  |

---

## Final Validation Verdict

### **POSTGRESQL DATABASE VALIDATION: CERTIFIED (100% PASS)**

All 13 relational tables, all 872 records, all foreign keys, unique constraints, domain limits, and date chronologies are 100% valid and verified in PostgreSQL `mplads_db`.
