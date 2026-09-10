# MPLADS PostgreSQL Search Optimization & Query Guide
**Project**: SIH 2026 – Member of Parliament Local Area Development Scheme (MPLADS)  
**Database**: `mplads_db` (PostgreSQL 16+)  
**Status**: Production Search & Analytics Architecture Verified  

---

## 1. Executive Summary

To power interactive governance dashboards, rapid search interfaces, predictive risk monitoring, and statistical analytics, the PostgreSQL database `mplads_db` has been fully indexed, equipped with full-text search (FTS), and structured with operational and analytical views.

### Key Capabilities:
- **Full-Text Search (FTS)**: Stored generated `search_vector` `TSVECTOR` indexed with a Generalized Inverted Index (`GIN`) for millisecond keyword and phrase queries with relevance ranking (`ts_rank`).
- **Fuzzy Substring Matching**: Powered by `pg_trgm` GIN indexes for typo-tolerant matching of MPs, implementing agencies, and work titles.
- **Hierarchical & Composite Indexing**: Targeted B-Tree indexes for multi-column filtering across geography (`state_id, district_name`), project lifecycle (`current_status, sector`), and financial thresholds.
- **8 Pre-Aggregated Views**: Out-of-the-box analytical views that combine project microdata, financial disbursements, physical progress stages, and predictive risk scoring.

---

## 2. Complete Catalog of Searchable Fields & Indexes

| Search Dimension | Database Field(s) | Table | Index Type | Index Name | Primary Use Case |
|---|---|---|---|---|---|
| **Project ID** | `project_id` | `projects` | B-Tree (PK) | `projects_pkey` | Exact project point lookup |
| **Project Code** | `project_code` | `projects` | B-Tree (Unique) | `idx_projects_code` | Official administrative code lookup |
| **State** | `state_id`, `state_name` | `projects`, `states` | B-Tree / FK | `idx_projects_state_id` | State-level portfolio aggregation |
| **Constituency** | `constituency_id`, `constituency_name` | `projects`, `constituencies`| B-Tree / FK | `idx_projects_constituency_id`| Parliamentary seat query |
| **State + District** | `state_id`, `district_name` | `projects` | Composite B-Tree | `idx_projects_state_district` | District administration filtering |
| **Member of Parliament** | `mp_name` | `projects` | B-Tree + Trigram GIN | `idx_projects_mp_name`, `idx_projects_mp_trgm` | MP performance and search |
| **Implementing Agency** | `implementing_agency` | `projects` | B-Tree + Trigram GIN | `idx_projects_agency`, `idx_projects_agency_trgm` | Agency workload and audits |
| **Project Category** | `sector`, `sub_sector` | `projects` | B-Tree | `idx_projects_sector` | Developmental sector breakdown |
| **Status + Sector** | `current_status`, `sector` | `projects` | Composite B-Tree | `idx_projects_status_sector` | Active works per sector |
| **Financial Year** | `financial_year` | `projects` | B-Tree | `idx_projects_financial_year` | Annual budget cycle filtering |
| **Full Description Search** | `search_vector` | `projects` | GIN | `idx_projects_search_vector` | Natural language text search |
| **Sanctioned Amount** | `sanctioned_amount` | `financials` | B-Tree | `idx_financials_sanctioned` | High-value project threshold query |
| **Released Amount** | `released_amount` | `financials` | B-Tree | `idx_financials_released` | Central release tracking |
| **Expenditure Amount** | `expenditure_amount` | `financials` | B-Tree | `idx_financials_expenditure` | Capital expenditure auditing |
| **Utilization Rate** | `utilization_rate_pct` | `financials` | Filtered B-Tree | `idx_financials_utilization_filtered`| Fiscal efficiency filtering |
| **Cost Overrun** | `cost_overrun_amount` | `financials` | Filtered B-Tree | `idx_financials_cost_overrun_filtered`| Budget deviation detection |
| **Milestone & Delay** | `milestone_status`, `days_delayed` | `progress` | Composite B-Tree | `idx_progress_milestone_delayed` | Delay surveillance |
| **Physical Progress** | `physical_progress_pct` | `progress` | B-Tree | `idx_progress_physical_pct` | Execution pace categorization |
| **Overall Risk Score** | `overall_risk_score` | `risk_scores` | B-Tree (DESC) | `idx_risk_scores_overall_desc` | High-risk project escalation |
| **Risk Level + Score** | `risk_level`, `overall_risk_score` | `risk_scores` | Composite B-Tree | `idx_risk_scores_level_score` | Risk tier segmentation |

---

## 3. PostgreSQL Analytical Views

### 1. `v_project_overview`
A 360-degree operational view combining project metadata, state, constituency, financial accounting, latest physical progress, and risk scores:
- **Columns**: 50 columns covering all key attributes.
- **Computed Flags**:
  - `is_delayed`: `TRUE` when `days_delayed > 0` or milestone is `'Delayed'` / `'Critical'`.
  - `has_cost_overrun`: `TRUE` when `cost_overrun_amount > 0`.
  - `audit_status`: `'Audited'` if `inspection_date` is populated, else `'Pending Inspection'`.

### 2. `v_delayed_projects`
Filters for delayed or stalled projects and sorts by severity:
```sql
SELECT * FROM v_delayed_projects;
```

### 3. `v_high_risk_projects`
Filters for projects with `overall_risk_score >= 40.0` or `risk_level IN ('High', 'Critical')` and bundles contributing risk factors into a JSON structure (`primary_risk_factors`).

### 4. `v_projects_missing_information`
Audits data completeness and compliance gaps:
- Computes `missing_fields`: array of missing dates, pending inspections, or missing geo-coordinates.
- Computes `missing_fields_count`: sorted in descending order of missingness.

### 5. `v_sector_financial_summary`
Aggregates total projects, completions, average physical progress, total sanctioned/released/spent funds, overall utilization percentage, average risk score, and count of delayed projects by sector.

### 6. `v_state_equity_analysis`
Assesses SC/ST seat allocations and statutory quota compliance across 36 States/UTs.

### 7. `v_state_efficiency_ranking`
Ranks States and UTs by fund utilization and asset completion rates.

### 8. `v_budget_historical_performance`
33-year longitudinal series (1993–2025) of Union Budget Demand No. 91 allocations vs actual expenditures.

---

## 4. Production Example SQL Queries

### Query 1: Search by Project ID
```sql
SELECT 
    p.project_id,
    p.project_code,
    p.project_title,
    p.sector,
    s.state_name,
    c.constituency_name,
    p.district_name,
    p.mp_name,
    p.current_status,
    f.sanctioned_amount,
    f.expenditure_amount,
    rs.overall_risk_score,
    rs.risk_level
FROM projects p
JOIN states s ON p.state_id = s.state_id
JOIN constituencies c ON p.constituency_id = c.constituency_id
JOIN financials f ON p.project_id = f.project_id
JOIN risk_scores rs ON p.project_id = rs.project_id
WHERE p.project_id = 'MPLADS-2024-0001';
```

---

### Query 2: Search by State and District
```sql
SELECT 
    p.project_id,
    p.project_title,
    s.state_name,
    p.district_name,
    p.block_name,
    p.sector,
    p.current_status,
    f.sanctioned_amount,
    f.expenditure_amount,
    pr.physical_progress_pct
FROM projects p
JOIN states s ON p.state_id = s.state_id
JOIN financials f ON p.project_id = f.project_id
JOIN progress pr ON p.project_id = pr.project_id
WHERE s.state_name = 'Uttar Pradesh'
ORDER BY f.sanctioned_amount DESC;
```

---

### Query 3: Search by Project Status and Sector
```sql
SELECT 
    p.project_id,
    p.project_code,
    p.project_title,
    p.sector,
    p.current_status,
    p.implementing_agency,
    f.sanctioned_amount,
    f.expenditure_amount,
    f.utilization_rate_pct,
    pr.physical_progress_pct,
    pr.current_stage
FROM projects p
JOIN financials f ON p.project_id = f.project_id
JOIN progress pr ON p.project_id = pr.project_id
WHERE p.current_status = 'In Progress' AND p.sector = 'Education'
ORDER BY f.expenditure_amount DESC;
```

---

### Query 4: Find Delayed Projects
```sql
SELECT 
    project_id,
    project_title,
    state_name,
    constituency_name,
    sector,
    current_status,
    days_delayed,
    milestone_status,
    physical_progress_pct,
    sanctioned_amount,
    delay_risk_score,
    risk_level
FROM v_delayed_projects
ORDER BY days_delayed DESC;
```

---

### Query 5: Find Projects with High Expenditure
```sql
SELECT 
    p.project_id,
    p.project_title,
    s.state_name,
    p.sector,
    p.current_status,
    f.sanctioned_amount,
    f.released_amount,
    f.expenditure_amount,
    f.unspent_balance,
    f.utilization_rate_pct,
    f.cost_overrun_amount
FROM projects p
JOIN states s ON p.state_id = s.state_id
JOIN financials f ON p.project_id = f.project_id
WHERE f.expenditure_amount >= 2000000.00
ORDER BY f.expenditure_amount DESC;
```

---

### Query 6: Find Projects with Missing Information
```sql
SELECT 
    project_id,
    project_title,
    state_name,
    constituency_name,
    current_status,
    missing_fields_count,
    array_to_string(missing_fields, '; ') AS missing_fields_detail
FROM v_projects_missing_information
WHERE missing_fields_count > 0
ORDER BY missing_fields_count DESC;
```

---

### Query 7: Find High-Risk Projects
```sql
SELECT 
    project_id,
    project_title,
    state_name,
    sector,
    current_status,
    overall_risk_score,
    delay_risk_score,
    cost_overrun_risk_score,
    risk_level,
    days_delayed,
    primary_risk_factors
FROM v_high_risk_projects
ORDER BY overall_risk_score DESC;
```

---

### Query 8: Full-Text Search (FTS with GIN Index & Relevance Ranking)
```sql
SELECT 
    p.project_id,
    p.project_title,
    p.sector,
    p.district_name,
    p.mp_name,
    f.sanctioned_amount,
    ROUND(ts_rank(p.search_vector, websearch_to_tsquery('english', 'water OR solar'))::numeric, 4) AS search_relevance
FROM projects p
JOIN financials f ON p.project_id = f.project_id
WHERE p.search_vector @@ websearch_to_tsquery('english', 'water OR solar')
ORDER BY search_relevance DESC
LIMIT 10;
```

---

### Query 9: Fuzzy Substring Search (pg_trgm)
```sql
SELECT 
    p.project_id,
    p.project_title,
    p.mp_name,
    p.implementing_agency,
    p.district_name,
    similarity(p.implementing_agency, 'Rural Development DRDA') AS match_score
FROM projects p
WHERE p.implementing_agency % 'Rural Development DRDA'
   OR p.implementing_agency ILIKE '%DRDA%'
ORDER BY match_score DESC
LIMIT 5;
```

---

## 5. Benchmarking & Execution

Run the complete search and query verification suite via Python:
```bash
python3 scripts/query_search_examples.py
```

This executes all 9 queries, inspects the PostgreSQL execution plans (`EXPLAIN`), prints result rows, and verifies index efficiency.
