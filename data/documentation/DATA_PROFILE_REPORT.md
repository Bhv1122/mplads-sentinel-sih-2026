# Comprehensive MPLADS Dataset & Column Profile Report
**Generated Date**: 2026-09-09 00:15:28
**Total Datasets Audited**: 13
**Total Columns Profiled**: 129

## 1. Dataset Overview & Dimensions

| Dataset Filename | Total Rows | Total Columns | Primary Key / Index Column | Key Observations |
|---|---|---|---|---|
| `esakshi_calamity_relief.csv` | 12 | 11 | `s_no` | Standardized & Clean |
| `esakshi_constituencies.csv` | 543 | 6 | `constituency_id` | Standardized & Clean |
| `esakshi_national_summary.csv` | 6 | 5 | `metric_key` | Standardized & Clean |
| `esakshi_states.csv` | 36 | 3 | `state_id` | Standardized & Clean |
| `financials.csv` | 20 | 10 | `project_id` | Standardized & Clean |
| `master_dim_states_constituencies.csv` | 36 | 14 | `state_id` | Standardized & Clean |
| `parliament_qa_state_expenditure.csv` | 36 | 12 | `state_id` | Standardized & Clean |
| `progress.csv` | 20 | 13 | `project_id` | Standardized & Clean |
| `project_history.csv` | 68 | 8 | `project_id` | Standardized & Clean |
| `projects.csv` | 20 | 20 | `project_id` | Standardized & Clean |
| `risk_factors.csv` | 22 | 8 | `risk_score_id` | Standardized & Clean |
| `risk_scores.csv` | 20 | 11 | `risk_score_id` | Standardized & Clean |
| `union_budget_mplads_1993_2025.csv` | 33 | 8 | `financial_year` | Standardized & Clean |

---

## 2. Column-by-Column Deep Profiling

### Dataset: `esakshi_calamity_relief.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `s_no` | INTEGER | 0 (0.0%) | 12 | Min: 1 | Q1: 3.75 | Med: 6.50 | Q3: 9.25 | Max: 12 | Candidate Primary Key (100% unique, 0% null) |

| 2 | `mp_name` | STRING | 0 (0.0%) | 10 | Shafi Parambil: 2 (16.7%); Shri Nk Premachandran: 2 (16.7%); Shri Gurjeet Singh Aujla: 1 (8.3%); Gurmeet Singh Meet Hayer: 1 (8.3%); and 6 other distinct values | No quality anomalies detected (Clean) |

| 3 | `house_of_parliament` | STRING | 0 (0.0%) | 1 | Lok Sabha: 12 (100.0%) | Single unique value across all rows |

| 4 | `tenure` | STRING | 0 (0.0%) | 1 | 18th Lok Sabha: 12 (100.0%) | Single unique value across all rows |

| 5 | `calamity_name` | STRING | 0 (0.0%) | 6 | Flood 2025 in Punjab: 3 (25.0%); Meppadi landslides 2024: 3 (25.0%); Vilangad Landslides 2024: 2 (16.7%); Wayanad landslides 2024: 2 (16.7%); and 2 other distinct values | No quality anomalies detected (Clean) |

| 6 | `calamity_type` | STRING | 0 (0.0%) | 2 | National Calamity: 7 (58.3%); State Calamity: 5 (41.7%) | No quality anomalies detected (Clean) |

| 7 | `consented_amount_inr` | FLOAT | 0 (0.0%) | 6 | Min: 500000.00 | Q1: 1000000.00 | Med: 2500000.00 | Q3: 3641850.00 | Max: 10000000.00 | No quality anomalies detected (Clean) |

| 8 | `consented_amount_lakhs` | FLOAT | 0 (0.0%) | 6 | Min: 5.00 | Q1: 10.00 | Med: 25.00 | Q3: 36.42 | Max: 100.00 | No quality anomalies detected (Clean) |

| 9 | `consent_date` | DATE | 0 (0.0%) | 11 | 07-Dec-2024: 2 (16.7%); 07-Dec-2025: 1 (8.3%); 03-Nov-2025: 1 (8.3%); 10-Oct-2025: 1 (8.3%); and 7 other distinct values | No quality anomalies detected (Clean) |

| 10 | `tenure_start_date` | DATE | 0 (0.0%) | 2 | Jun 4, 2024 12:00:00 AM: 10 (83.3%); Jun 5, 2024 12:00:00 AM: 2 (16.7%) | No quality anomalies detected (Clean) |

| 11 | `tenure_end_date` | DATE | 0 (0.0%) | 1 | Jun 3, 2029 11:59:59 PM: 12 (100.0%) | Single unique value across all rows |

### Dataset: `esakshi_constituencies.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `constituency_id` | INTEGER | 0 (0.0%) | 543 | Min: 1 | Q1: 138.50 | Med: 274.00 | Q3: 410.50 | Max: 548 | Candidate Primary Key (100% unique, 0% null) |

| 2 | `state_id` | INTEGER | 0 (0.0%) | 36 | Min: 1 | Q1: 16.00 | Med: 25.00 | Q3: 33.00 | Max: 130 | No quality anomalies detected (Clean) |

| 3 | `state_name` | STRING | 0 (0.0%) | 36 | Uttar Pradesh: 80 (14.7%); Maharashtra: 48 (8.8%); West Bengal: 42 (7.7%); Bihar: 40 (7.4%); and 32 other distinct values | No quality anomalies detected (Clean) |

| 4 | `constituency_name` | STRING | 0 (0.0%) | 543 | Andaman And Nicobar Islands: 1 (0.2%); Anakapalle: 1 (0.2%); Hindupur: 1 (0.2%); Vijayawada: 1 (0.2%); and 539 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 5 | `raw_caption` | STRING | 0 (0.0%) | 543 | ANDAMAN AND NICOBAR ISLANDS: 1 (0.2%); ANAKAPALLE: 1 (0.2%); HINDUPUR: 1 (0.2%); VIJAYAWADA: 1 (0.2%); and 539 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 6 | `reservation_category` | STRING | 0 (0.0%) | 3 | General: 417 (76.8%); SC: 82 (15.1%); ST: 44 (8.1%) | No quality anomalies detected (Clean) |

### Dataset: `esakshi_national_summary.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `metric_key` | STRING | 0 (0.0%) | 6 | Allocated Limit for Hon'ble MPs: 1 (16.7%); Expenditure on Completed and On-going Works as on Date: 1 (16.7%); Works Recommended: 1 (16.7%); Works Completed: 1 (16.7%); and 2 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 2 | `metric_description` | STRING | 0 (0.0%) | 6 | Allocated Limit for Hon'ble MPs: 1 (16.7%); Expenditure on Completed and On-going Works as on Date: 1 (16.7%); Works Recommended: 1 (16.7%); Works Completed: 1 (16.7%); and 2 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 3 | `count_works` | INTEGER | 2 (33.33%) | 4 | Min: 12 | Q1: 26082.00 | Med: 57232.50 | Q3: 86654.50 | Max: 107539 | Moderate missingness (33.33% null) |

| 4 | `amount_inr` | FLOAT | 0 (0.0%) | 6 | Min: 40567400.00 | Q1: 19770893726.66 | Med: 34956229731.84 | Q3: 53737165319.89 | Max: 83336673298.01 | Candidate Primary Key (100% unique, 0% null) |

| 5 | `amount_crores` | FLOAT | 0 (0.0%) | 6 | Min: 4.06 | Q1: 1977.09 | Med: 3495.62 | Q3: 5373.72 | Max: 8333.67 | Candidate Primary Key (100% unique, 0% null) |

### Dataset: `esakshi_states.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `state_id` | INTEGER | 0 (0.0%) | 36 | Min: 1 | Q1: 11.75 | Med: 20.50 | Q3: 29.25 | Max: 130 | Candidate Primary Key (100% unique, 0% null) |

| 2 | `state_name` | STRING | 0 (0.0%) | 36 | Andaman And Nicobar Islands: 1 (2.8%); Andhra Pradesh: 1 (2.8%); Arunachal Pradesh: 1 (2.8%); Assam: 1 (2.8%); and 32 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 3 | `category` | STRING | 0 (0.0%) | 2 | State: 28 (77.8%); Union Territory: 8 (22.2%) | No quality anomalies detected (Clean) |

### Dataset: `financials.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `project_id` | STRING | 0 (0.0%) | 20 | MPLADS-2024-0001: 1 (5.0%); MPLADS-2024-0002: 1 (5.0%); MPLADS-2024-0003: 1 (5.0%); MPLADS-2024-0004: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 2 | `currency` | STRING | 0 (0.0%) | 1 | INR: 20 (100.0%) | Single unique value across all rows |

| 3 | `recommended_amount` | FLOAT | 0 (0.0%) | 16 | Min: 800000.00 | Q1: 1575000.00 | Med: 2350000.00 | Q3: 3625000.00 | Max: 5000000.00 | No quality anomalies detected (Clean) |

| 4 | `sanctioned_amount` | FLOAT | 0 (0.0%) | 16 | Min: 800000.00 | Q1: 1575000.00 | Med: 2250000.00 | Q3: 3350000.00 | Max: 4800000.00 | No quality anomalies detected (Clean) |

| 5 | `released_amount` | FLOAT | 0 (0.0%) | 15 | Min: 800000.00 | Q1: 1150000.00 | Med: 1500000.00 | Q3: 2025000.00 | Max: 4000000.00 | No quality anomalies detected (Clean) |

| 6 | `expenditure_amount` | FLOAT | 0 (0.0%) | 20 | Min: 100000.00 | Q1: 710000.00 | Med: 1290000.00 | Q3: 1562500.00 | Max: 3950000.00 | Candidate Primary Key (100% unique, 0% null) |

| 7 | `utilization_rate_pct` | FLOAT | 0 (0.0%) | 18 | Min: 12.50 | Q1: 45.53 | Med: 87.50 | Q3: 97.68 | Max: 98.75 | No quality anomalies detected (Clean) |

| 8 | `cost_overrun_amount` | FLOAT | 0 (0.0%) | 2 | Min: 0.00 | Q1: 0.00 | Med: 0.00 | Q3: 0.00 | Max: 50000.00 | No quality anomalies detected (Clean) |

| 9 | `cost_overrun_pct` | FLOAT | 0 (0.0%) | 3 | Min: 0.00 | Q1: 0.00 | Med: 0.00 | Q3: 0.00 | Max: 1.32 | No quality anomalies detected (Clean) |

| 10 | `last_disbursement_date` | DATE | 0 (0.0%) | 20 | 2024-07-25: 1 (5.0%); 2024-08-20: 1 (5.0%); 2024-09-05: 1 (5.0%); 2024-07-15: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

### Dataset: `master_dim_states_constituencies.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `state_id` | INTEGER | 0 (0.0%) | 36 | Min: 1 | Q1: 11.75 | Med: 20.50 | Q3: 29.25 | Max: 130 | Candidate Primary Key (100% unique, 0% null) |

| 2 | `state_name` | STRING | 0 (0.0%) | 36 | Andaman And Nicobar Islands: 1 (2.8%); Andhra Pradesh: 1 (2.8%); Arunachal Pradesh: 1 (2.8%); Assam: 1 (2.8%); and 32 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 3 | `category` | STRING | 0 (0.0%) | 2 | State: 28 (77.8%); Union Territory: 8 (22.2%) | No quality anomalies detected (Clean) |

| 4 | `total_lok_sabha_seats` | INTEGER | 0 (0.0%) | 21 | Min: 1 | Q1: 2.00 | Med: 8.50 | Q3: 25.00 | Max: 80 | No quality anomalies detected (Clean) |

| 5 | `general_seats` | INTEGER | 0 (0.0%) | 21 | Min: 0 | Q1: 1.00 | Med: 6.00 | Q3: 18.25 | Max: 63 | No quality anomalies detected (Clean) |

| 6 | `sc_reserved_seats` | INTEGER | 0 (0.0%) | 10 | Min: 0 | Q1: 0.00 | Med: 1.00 | Q3: 3.25 | Max: 17 | No quality anomalies detected (Clean) |

| 7 | `st_reserved_seats` | INTEGER | 0 (0.0%) | 7 | Min: 0 | Q1: 0.00 | Med: 0.00 | Q3: 2.00 | Max: 6 | No quality anomalies detected (Clean) |

| 8 | `statutory_sc_allocation_pct` | FLOAT | 0 (0.0%) | 1 | Min: 15.00 | Q1: 15.00 | Med: 15.00 | Q3: 15.00 | Max: 15.00 | Constant column (zero variance); Single unique value across all rows |

| 9 | `statutory_st_allocation_pct` | FLOAT | 0 (0.0%) | 1 | Min: 7.50 | Q1: 7.50 | Med: 7.50 | Q3: 7.50 | Max: 7.50 | Constant column (zero variance); Single unique value across all rows |

| 10 | `cumulative_released_cr` | FLOAT | 0 (0.0%) | 32 | Min: 140.00 | Q1: 343.75 | Med: 1585.00 | Q3: 4308.75 | Max: 13910.00 | No quality anomalies detected (Clean) |

| 11 | `cumulative_expenditure_cr` | FLOAT | 0 (0.0%) | 36 | Min: 131.20 | Q1: 325.23 | Med: 1525.50 | Q3: 4153.01 | Max: 13120.80 | Candidate Primary Key (100% unique, 0% null) |

| 12 | `unspent_balance_cr` | FLOAT | 0 (0.0%) | 36 | Min: 2.20 | Q1: 10.07 | Med: 69.50 | Q3: 155.74 | Max: 789.20 | Candidate Primary Key (100% unique, 0% null) |

| 13 | `utilization_pct` | FLOAT | 0 (0.0%) | 34 | Min: 92.11 | Q1: 95.37 | Med: 96.29 | Q3: 96.88 | Max: 98.53 | No quality anomalies detected (Clean) |

| 14 | `works_completed_count` | INTEGER | 0 (0.0%) | 36 | Min: 2390 | Q1: 5790.00 | Med: 30350.00 | Q3: 79790.00 | Max: 241200 | Candidate Primary Key (100% unique, 0% null) |

### Dataset: `parliament_qa_state_expenditure.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `state_id` | INTEGER | 0 (0.0%) | 36 | Min: 1 | Q1: 9.75 | Med: 18.50 | Q3: 29.25 | Max: 38 | Candidate Primary Key (100% unique, 0% null) |

| 2 | `state_name` | STRING | 0 (0.0%) | 36 | Andhra Pradesh: 1 (2.8%); Arunachal Pradesh: 1 (2.8%); Assam: 1 (2.8%); Bihar: 1 (2.8%); and 32 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 3 | `entitlement_cr` | FLOAT | 0 (0.0%) | 25 | Min: 155.00 | Q1: 376.25 | Med: 1670.00 | Q3: 4582.50 | Max: 14820.00 | No quality anomalies detected (Clean) |

| 4 | `released_cr` | FLOAT | 0 (0.0%) | 32 | Min: 140.00 | Q1: 343.75 | Med: 1585.00 | Q3: 4308.75 | Max: 13910.00 | No quality anomalies detected (Clean) |

| 5 | `expenditure_cr` | FLOAT | 0 (0.0%) | 36 | Min: 131.20 | Q1: 325.23 | Med: 1525.50 | Q3: 4153.01 | Max: 13120.80 | Candidate Primary Key (100% unique, 0% null) |

| 6 | `unspent_balance_cr` | FLOAT | 0 (0.0%) | 36 | Min: 2.20 | Q1: 10.07 | Med: 69.50 | Q3: 155.74 | Max: 789.20 | Candidate Primary Key (100% unique, 0% null) |

| 7 | `utilization_rate_pct` | FLOAT | 0 (0.0%) | 34 | Min: 92.11 | Q1: 95.37 | Med: 96.29 | Q3: 96.88 | Max: 98.53 | No quality anomalies detected (Clean) |

| 8 | `works_recommended` | INTEGER | 0 (0.0%) | 36 | Min: 2600 | Q1: 6412.50 | Med: 33650.00 | Q3: 89362.50 | Max: 284500 | Candidate Primary Key (100% unique, 0% null) |

| 9 | `works_sanctioned` | INTEGER | 0 (0.0%) | 35 | Min: 2480 | Q1: 6015.00 | Med: 31600.00 | Q3: 83282.50 | Max: 259800 | No quality anomalies detected (Clean) |

| 10 | `works_completed` | INTEGER | 0 (0.0%) | 36 | Min: 2390 | Q1: 5790.00 | Med: 30350.00 | Q3: 79790.00 | Max: 241200 | Candidate Primary Key (100% unique, 0% null) |

| 11 | `sanction_rate_pct` | FLOAT | 0 (0.0%) | 34 | Min: 89.22 | Q1: 93.00 | Med: 93.73 | Q3: 94.76 | Max: 96.94 | No quality anomalies detected (Clean) |

| 12 | `completion_rate_pct` | FLOAT | 0 (0.0%) | 36 | Min: 90.38 | Q1: 93.41 | Med: 95.22 | Q3: 96.27 | Max: 97.99 | Candidate Primary Key (100% unique, 0% null) |

### Dataset: `progress.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `project_id` | STRING | 0 (0.0%) | 20 | MPLADS-2024-0001: 1 (5.0%); MPLADS-2024-0002: 1 (5.0%); MPLADS-2024-0003: 1 (5.0%); MPLADS-2024-0004: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 2 | `reported_date` | DATE | 0 (0.0%) | 1 | 2024-11-15: 20 (100.0%) | Single unique value across all rows |

| 3 | `physical_progress_pct` | FLOAT | 0 (0.0%) | 4 | Min: 10.00 | Q1: 65.00 | Med: 65.00 | Q3: 100.00 | Max: 100.00 | No quality anomalies detected (Clean) |

| 4 | `financial_progress_pct` | FLOAT | 0 (0.0%) | 18 | Min: 12.50 | Q1: 45.53 | Med: 87.50 | Q3: 97.68 | Max: 98.75 | No quality anomalies detected (Clean) |

| 5 | `current_stage` | STRING | 0 (0.0%) | 4 | Completed: 8 (40.0%); Structure: 8 (40.0%); Foundation: 2 (10.0%); Contract Awarded: 2 (10.0%) | No quality anomalies detected (Clean) |

| 6 | `days_delayed` | INTEGER | 0 (0.0%) | 2 | Min: 0 | Q1: 0.00 | Med: 0.00 | Q3: 0.00 | Max: 95 | No quality anomalies detected (Clean) |

| 7 | `milestone_status` | STRING | 0 (0.0%) | 3 | On Track: 10 (50.0%); Completed: 8 (40.0%); Critical: 2 (10.0%) | No quality anomalies detected (Clean) |

| 8 | `inspected_by` | STRING | 0 (0.0%) | 1 | District Executive Engineer: 20 (100.0%) | Single unique value across all rows |

| 9 | `inspection_date` | DATE | 0 (0.0%) | 1 | 2024-11-10: 20 (100.0%) | Single unique value across all rows |

| 10 | `inspection_remarks` | STRING | 0 (0.0%) | 4 | Site inspected. Physical execution at 100.0%. Milestone: Completed.: 8 (40.0%); Site inspected. Physical execution at 65.0%. Milestone: On Track.: 8 (40.0%); Site inspected. Physical execution at 35.0%. Milestone: Critical.: 2 (10.0%); Site inspected. Physical execution at 10.0%. Milestone: On Track.: 2 (10.0%) | No quality anomalies detected (Clean) |

| 11 | `geo_latitude` | FLOAT | 0 (0.0%) | 20 | Min: 20.59 | Q1: 22.49 | Med: 24.39 | Q3: 26.29 | Max: 28.19 | Candidate Primary Key (100% unique, 0% null) |

| 12 | `geo_longitude` | FLOAT | 0 (0.0%) | 20 | Min: 78.96 | Q1: 80.86 | Med: 82.76 | Q3: 84.66 | Max: 86.56 | Candidate Primary Key (100% unique, 0% null) |

| 13 | `photo_evidence_url` | STRING | 0 (0.0%) | 20 | https://mplads.gov.in/photos/MPLADS-2024-0001_inspection.jpg: 1 (5.0%); https://mplads.gov.in/photos/MPLADS-2024-0002_inspection.jpg: 1 (5.0%); https://mplads.gov.in/photos/MPLADS-2024-0003_inspection.jpg: 1 (5.0%); https://mplads.gov.in/photos/MPLADS-2024-0004_inspection.jpg: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

### Dataset: `project_history.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `project_id` | STRING | 0 (0.0%) | 20 | MPLADS-2024-0001: 4 (5.9%); MPLADS-2024-0004: 4 (5.9%); MPLADS-2024-0006: 4 (5.9%); MPLADS-2024-0008: 4 (5.9%); and 16 other distinct values | No quality anomalies detected (Clean) |

| 2 | `event_type` | STRING | 0 (0.0%) | 4 | Created: 20 (29.4%); Sanctioned: 20 (29.4%); Work Order Issued: 20 (29.4%); Completed: 8 (11.8%) | No quality anomalies detected (Clean) |

| 3 | `previous_status` | STRING | 20 (29.41%) | 3 | Recommended: 20 (41.7%); Sanctioned: 20 (41.7%); In Progress: 8 (16.7%) | Moderate missingness (29.41% null) |

| 4 | `new_status` | STRING | 0 (0.0%) | 4 | Recommended: 20 (29.4%); Sanctioned: 20 (29.4%); Work Order Issued: 20 (29.4%); Completed: 8 (11.8%) | No quality anomalies detected (Clean) |

| 5 | `event_timestamp` | STRING | 0 (0.0%) | 67 | 2024-07-10 14:30:00+05:30: 2 (2.9%); 2024-06-15 10:00:00+05:30: 1 (1.5%); 2024-07-25 11:15:00+05:30: 1 (1.5%); 2024-11-20 16:00:00+05:30: 1 (1.5%); and 63 other distinct values | No quality anomalies detected (Clean) |

| 6 | `performed_by` | STRING | 0 (0.0%) | 23 | District Authority / Collector: 20 (29.4%); Executive Engineer (DRDA): 20 (29.4%); District Executive Engineer: 8 (11.8%); Hon MP (Maldaha Uttar): 1 (1.5%); and 19 other distinct values | No quality anomalies detected (Clean) |

| 7 | `event_description` | STRING | 0 (0.0%) | 38 | Tender finalized and work order issued to executing agency.: 20 (29.4%); Final completion certificate and asset geo-tagging submitted.: 8 (11.8%); Administrative and financial sanction accorded for Rs. 1,500,000.00.: 2 (2.9%); Administrative and financial sanction accorded for Rs. 1,800,000.00.: 2 (2.9%); and 34 other distinct values | No quality anomalies detected (Clean) |

| 8 | `metadata_json` | STRING | 0 (0.0%) | 64 | {"source": "e-SAKSHI MP Portal", "rec_amount": 1500000.0}: 2 (2.9%); {"source": "e-SAKSHI MP Portal", "rec_amount": 4500000.0}: 2 (2.9%); {"source": "e-SAKSHI MP Portal", "rec_amount": 1800000.0}: 2 (2.9%); {"source": "e-SAKSHI MP Portal", "rec_amount": 4000000.0}: 2 (2.9%); and 60 other distinct values | No quality anomalies detected (Clean) |

### Dataset: `projects.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `project_id` | STRING | 0 (0.0%) | 20 | MPLADS-2024-0001: 1 (5.0%); MPLADS-2024-0002: 1 (5.0%); MPLADS-2024-0003: 1 (5.0%); MPLADS-2024-0004: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 2 | `project_code` | STRING | 0 (0.0%) | 20 | PRJ-34-532-001: 1 (5.0%); PRJ-33-480-002: 1 (5.0%); PRJ-28-358-003: 1 (5.0%); PRJ-34-533-004: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 3 | `project_title` | STRING | 0 (0.0%) | 20 | Community RO Plant: 1 (5.0%); Additional Classrooms in Govt High School: 1 (5.0%); Primary Health Centre Sub-centre Upgradation: 1 (5.0%); Community Sanitary Complex with Solar Power: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 4 | `project_description` | STRING | 0 (0.0%) | 20 | Community RO Plant in Maldaha Uttar Parliamentary Constituency.: 1 (5.0%); Additional Classrooms in Govt High School in Sambhal Parliamentary Constituency.: 1 (5.0%); Primary Health Centre Sub-centre Upgradation in Pali Parliamentary Constituency.: 1 (5.0%); Community Sanitary Complex with Solar Power in Medinipur Parliamentary Constituency.: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 5 | `sector` | STRING | 0 (0.0%) | 8 | Drinking Water: 4 (20.0%); Education: 3 (15.0%); Health: 3 (15.0%); Sanitation: 3 (15.0%); and 4 other distinct values | No quality anomalies detected (Clean) |

| 6 | `sub_sector` | STRING | 0 (0.0%) | 8 | Drinking Water: 4 (20.0%); Education: 3 (15.0%); Health: 3 (15.0%); Sanitation: 3 (15.0%); and 4 other distinct values | No quality anomalies detected (Clean) |

| 7 | `state_id` | INTEGER | 0 (0.0%) | 11 | Min: 1 | Q1: 6.00 | Med: 23.00 | Q3: 33.25 | Max: 36 | No quality anomalies detected (Clean) |

| 8 | `constituency_id` | INTEGER | 0 (0.0%) | 20 | Min: 8 | Q1: 84.25 | Med: 263.00 | Q3: 482.50 | Max: 533 | Candidate Primary Key (100% unique, 0% null) |

| 9 | `district_name` | STRING | 0 (0.0%) | 20 | Maldaha Uttar District: 1 (5.0%); Sambhal District: 1 (5.0%); Pali District: 1 (5.0%); Medinipur District: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 10 | `block_name` | STRING | 0 (0.0%) | 20 | Maldaha Uttar Block: 1 (5.0%); Sambhal Block: 1 (5.0%); Pali Block: 1 (5.0%); Medinipur Block: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 11 | `implementing_agency` | STRING | 0 (0.0%) | 1 | District Rural Development Agency (DRDA): 20 (100.0%) | Single unique value across all rows |

| 12 | `mp_name` | STRING | 0 (0.0%) | 20 | Hon MP of Maldaha Uttar: 1 (5.0%); Hon MP of Sambhal: 1 (5.0%); Hon MP of Pali: 1 (5.0%); Hon MP of Medinipur: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 13 | `house_of_parliament` | STRING | 0 (0.0%) | 1 | Lok Sabha: 20 (100.0%) | Single unique value across all rows |

| 14 | `financial_year` | STRING | 0 (0.0%) | 1 | 2024-25: 20 (100.0%) | Single unique value across all rows |

| 15 | `current_status` | STRING | 0 (0.0%) | 4 | Completed: 8 (40.0%); In Progress: 8 (40.0%); Stalled: 2 (10.0%); Work Order Issued: 2 (10.0%) | No quality anomalies detected (Clean) |

| 16 | `recommendation_date` | DATE | 0 (0.0%) | 20 | 2024-06-15: 1 (5.0%); 2024-06-20: 1 (5.0%); 2024-07-01: 1 (5.0%); 2024-06-10: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 17 | `sanction_date` | DATE | 0 (0.0%) | 19 | 2024-07-10: 2 (10.0%); 2024-08-01: 1 (5.0%); 2024-08-15: 1 (5.0%); 2024-06-28: 1 (5.0%); and 15 other distinct values | No quality anomalies detected (Clean) |

| 18 | `work_order_date` | DATE | 0 (0.0%) | 20 | 2024-07-25: 1 (5.0%); 2024-08-20: 1 (5.0%); 2024-09-05: 1 (5.0%); 2024-07-15: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 19 | `expected_completion_date` | DATE | 0 (0.0%) | 18 | 2025-03-31: 2 (10.0%); 2025-02-28: 2 (10.0%); 2024-11-30: 1 (5.0%); 2025-01-31: 1 (5.0%); and 14 other distinct values | No quality anomalies detected (Clean) |

| 20 | `actual_completion_date` | DATE | 12 (60.0%) | 8 | 2024-11-20: 1 (12.5%); 2024-10-10: 1 (12.5%); 2024-09-25: 1 (12.5%); 2024-08-28: 1 (12.5%); and 4 other distinct values | Critical missingness (>50% null: 60.0%) |

### Dataset: `risk_factors.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `risk_score_id` | INTEGER | 0 (0.0%) | 20 | Min: 1 | Q1: 5.25 | Med: 10.50 | Q3: 15.75 | Max: 20 | No quality anomalies detected (Clean) |

| 2 | `project_id` | STRING | 0 (0.0%) | 20 | MPLADS-2024-0005: 2 (9.1%); MPLADS-2024-0018: 2 (9.1%); MPLADS-2024-0001: 1 (4.5%); MPLADS-2024-0002: 1 (4.5%); and 16 other distinct values | No quality anomalies detected (Clean) |

| 3 | `factor_category` | STRING | 0 (0.0%) | 4 | Agency Past Performance: 16 (72.7%); Contractor Inaction: 2 (9.1%); Monsoon Seasonality: 2 (9.1%); Delay in Tendering: 2 (9.1%) | No quality anomalies detected (Clean) |

| 4 | `factor_name` | STRING | 0 (0.0%) | 4 | Experienced DRDA Division with Strong Completion Track Record: 16 (72.7%); Contractor Default on Foundation Milestone: 2 (9.1%); Heavy Seasonal Waterlogging in Excavation Pit: 2 (9.1%); Prolonged Technical Evaluation Window: 2 (9.1%) | No quality anomalies detected (Clean) |

| 5 | `factor_weight` | FLOAT | 0 (0.0%) | 4 | Min: 0.10 | Q1: 0.10 | Med: 0.10 | Q3: 0.21 | Max: 0.45 | No quality anomalies detected (Clean) |

| 6 | `factor_impact` | STRING | 0 (0.0%) | 3 | Low: 16 (72.7%); Medium: 4 (18.2%); Critical: 2 (9.1%) | No quality anomalies detected (Clean) |

| 7 | `mitigation_recommendation` | STRING | 0 (0.0%) | 4 | Maintain standard monthly progress reviews.: 16 (72.7%); Issue final contractual show-cause notice and invoke bank guarantee if unresponsive within 14 days.: 2 (9.1%); Deploy high-capacity dewatering pumps and construct diversion channel.: 2 (9.1%); Expedite site handover and advance mobilization to contractor.: 2 (9.1%) | No quality anomalies detected (Clean) |

| 8 | `is_mitigated` | STRING | 0 (0.0%) | 2 | True: 18 (81.8%); False: 4 (18.2%) | No quality anomalies detected (Clean) |

### Dataset: `risk_scores.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `risk_score_id` | INTEGER | 0 (0.0%) | 20 | Min: 1 | Q1: 5.75 | Med: 10.50 | Q3: 15.25 | Max: 20 | Candidate Primary Key (100% unique, 0% null) |

| 2 | `project_id` | STRING | 0 (0.0%) | 20 | MPLADS-2024-0001: 1 (5.0%); MPLADS-2024-0002: 1 (5.0%); MPLADS-2024-0003: 1 (5.0%); MPLADS-2024-0004: 1 (5.0%); and 16 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 3 | `overall_risk_score` | FLOAT | 0 (0.0%) | 4 | Min: 5.00 | Q1: 5.00 | Med: 28.00 | Q3: 28.00 | Max: 78.50 | No quality anomalies detected (Clean) |

| 4 | `delay_risk_score` | FLOAT | 0 (0.0%) | 4 | Min: 0.00 | Q1: 0.00 | Med: 25.00 | Q3: 25.00 | Max: 85.00 | No quality anomalies detected (Clean) |

| 5 | `cost_overrun_risk_score` | FLOAT | 0 (0.0%) | 4 | Min: 0.00 | Q1: 0.00 | Med: 20.00 | Q3: 20.00 | Max: 65.00 | No quality anomalies detected (Clean) |

| 6 | `non_completion_risk_score` | FLOAT | 0 (0.0%) | 4 | Min: 0.00 | Q1: 0.00 | Med: 15.00 | Q3: 15.00 | Max: 72.00 | No quality anomalies detected (Clean) |

| 7 | `leakage_risk_score` | FLOAT | 0 (0.0%) | 4 | Min: 5.00 | Q1: 5.00 | Med: 10.00 | Q3: 10.00 | Max: 25.00 | No quality anomalies detected (Clean) |

| 8 | `risk_level` | STRING | 0 (0.0%) | 3 | Low: 16 (80.0%); High: 2 (10.0%); Moderate: 2 (10.0%) | No quality anomalies detected (Clean) |

| 9 | `confidence_score` | FLOAT | 0 (0.0%) | 1 | Min: 0.92 | Q1: 0.92 | Med: 0.92 | Q3: 0.92 | Max: 0.92 | Constant column (zero variance); Single unique value across all rows |

| 10 | `assessment_date` | DATE | 0 (0.0%) | 1 | 2024-11-15: 20 (100.0%) | Single unique value across all rows |

| 11 | `model_version` | STRING | 0 (0.0%) | 1 | v1.0: 20 (100.0%) | Single unique value across all rows |

### Dataset: `union_budget_mplads_1993_2025.csv`

| Col # | Column Name | Type | Missing (%) | Unique | Distribution / Stats | Data Quality Findings |
|---|---|---|---|---|---|---|
| 1 | `financial_year` | STRING | 0 (0.0%) | 33 | 1993-94: 1 (3.0%); 1994-95: 1 (3.0%); 1995-96: 1 (3.0%); 1996-97: 1 (3.0%); and 29 other distinct values | Candidate Primary Key (100% unique, 0% null) |

| 2 | `entitlement_per_mp_cr` | FLOAT | 0 (0.0%) | 5 | Min: 0.00 | Q1: 2.00 | Med: 2.00 | Q3: 5.00 | Max: 5.00 | No quality anomalies detected (Clean) |

| 3 | `budget_estimate_cr` | FLOAT | 0 (0.0%) | 5 | Min: 200.00 | Q1: 1580.00 | Med: 1580.00 | Q3: 3950.00 | Max: 3965.00 | No quality anomalies detected (Clean) |

| 4 | `revised_estimate_cr` | FLOAT | 1 (3.03%) | 20 | Min: 100.00 | Q1: 1370.00 | Med: 1590.00 | Q3: 3500.00 | Max: 3950.00 | No quality anomalies detected (Clean) |

| 5 | `actual_expenditure_cr` | FLOAT | 1 (3.03%) | 32 | Min: 99.40 | Q1: 1370.00 | Med: 1590.00 | Q3: 3491.15 | Max: 3949.50 | No quality anomalies detected (Clean) |

| 6 | `be_vs_actual_variance_cr` | FLOAT | 1 (3.03%) | 31 | Min: -3865.60 | Q1: -134.54 | Med: -20.50 | Q3: -0.50 | Max: 1370.00 | No quality anomalies detected (Clean) |

| 7 | `major_head` | INTEGER | 0 (0.0%) | 1 | Min: 3475 | Q1: 3475.00 | Med: 3475.00 | Q3: 3475.00 | Max: 3475 | Constant column (zero variance); Single unique value across all rows |

| 8 | `status_notes` | STRING | 0 (0.0%) | 11 | Implemented: 23 (69.7%); Inception Year (Dec 1993): 1 (3.0%); Entitlement raised to 2 Cr: 1 (3.0%); Entitlement raised to 5 Cr: 1 (3.0%); and 7 other distinct values | No quality anomalies detected (Clean) |

