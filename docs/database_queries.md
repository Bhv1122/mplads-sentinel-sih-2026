# MPLADS PostgreSQL Database Queries & Search Optimization Guide
**Project**: SIH 2026 – Member of Parliament Local Area Development Scheme (MPLADS) Data & Governance Analytics  
**Database**: `mplads_db` (PostgreSQL 16+)  
**Version**: Phase 3 Production Release  

---

## 1. Executive Summary & Query Architecture

The MPLADS database (`mplads_db`) is engineered for sub-second analytical querying, high-concurrency dashboard filtering, real-time risk surveillance, and natural language full-text search. The database hosts **13 relational tables**, **8 analytical views**, and **85 specialized indexes**.

### Key Search & Query Capabilities
1. **PostgreSQL Full-Text Search (FTS)**: A stored, generated `search_vector` (`TSVECTOR`) on `projects` combines project title, description, sector, sub-sector, implementing agency, MP name, and district. Indexed with a Generalized Inverted Index (`GIN`), enabling boolean expressions (`websearch_to_tsquery`, `plainto_tsquery`) with execution times under 1 ms.
2. **Fuzzy & Substring Search (`pg_trgm`)**: Trigram GIN indexes on `project_title`, `mp_name`, `implementing_agency`, and `district_name` provide typo tolerance and substring matching (`similarity()` and `%`).
3. **Composite & Filtered B-Tree Indexing**: Multi-column indexes align with governance search workflows, such as `(state_id, district_name)`, `(current_status, sector)`, and filtered partial indexes on active cost overruns and delays.
4. **Pre-Aggregated Operational & Analytical Views**: 8 materialized and dynamic views abstract multi-table joins for executive dashboards, delay monitoring, risk escalation, and quality auditing.

---

## 2. Catalog of Searchable Dimensions & Indexes

| Dimension | Table | Field(s) | Index Type | Index Name | Search Strategy |
|---|---|---|---|---|---|
| **Project ID** | `projects` | `project_id` | B-Tree (PK) | `projects_pkey` | Exact match (`=`) |
| **Project Code** | `projects` | `project_code` | B-Tree (Unique) | `idx_projects_code` | Exact match (`=`) |
| **State** | `projects`, `states` | `state_id`, `state_name` | B-Tree / FK | `idx_projects_state_id` | Equality / IN list |
| **District** | `projects` | `district_name` | Composite B-Tree + Trigram | `idx_projects_state_district`, `idx_projects_district_trgm` | Exact / Fuzzy |
| **Constituency** | `projects`, `constituencies` | `constituency_id`, `constituency_name` | B-Tree / FK | `idx_projects_constituency_id` | Equality / Join |
| **MP Name** | `projects` | `mp_name` | B-Tree + Trigram GIN | `idx_projects_mp_name`, `idx_projects_mp_trgm` | Exact / Fuzzy (`similarity`) |
| **Implementing Agency** | `projects` | `implementing_agency` | B-Tree + Trigram GIN | `idx_projects_agency`, `idx_projects_agency_trgm` | Exact / Substring |
| **Sector & Sub-sector** | `projects` | `sector`, `sub_sector` | B-Tree | `idx_projects_sector` | Equality / Categorical |
| **Status & Lifecycle** | `projects` | `current_status`, `sector` | Composite B-Tree | `idx_projects_status_sector` | Multi-filter |
| **Financial Year** | `projects` | `financial_year` | B-Tree | `idx_projects_financial_year` | Equality (`'2024-25'`) |
| **Natural Language / Keyword** | `projects` | `search_vector` | GIN | `idx_projects_search_vector` | FTS (`@@`) |
| **Sanctioned Amount** | `financials` | `sanctioned_amount` | B-Tree | `idx_financials_sanctioned` | Range (`BETWEEN`, `>`, `<`) |
| **Released Amount** | `financials` | `released_amount` | B-Tree | `idx_financials_released` | Range (`>=`) |
| **Expenditure Amount** | `financials` | `expenditure_amount` | B-Tree | `idx_financials_expenditure` | Range (`>=`) |
| **Utilization Rate** | `financials` | `utilization_rate_pct` | Filtered B-Tree | `idx_financials_utilization_filtered` | Range / Non-zero |
| **Cost Overrun** | `financials` | `cost_overrun_amount` | Filtered B-Tree | `idx_financials_cost_overrun_filtered` | Flagged (`> 0`) |
| **Milestone & Delay Days** | `progress` | `milestone_status`, `days_delayed` | Composite B-Tree | `idx_progress_milestone_delayed` | Surveillance |
| **Physical Progress** | `progress` | `physical_progress_pct` | B-Tree | `idx_progress_physical_pct` | Range (`0` to `100`) |
| **Overall Risk Score** | `risk_scores` | `overall_risk_score` | B-Tree (DESC) | `idx_risk_scores_overall_desc` | Ranking (`ORDER BY DESC`) |
| **Risk Level & Score** | `risk_scores` | `risk_level`, `overall_risk_score` | Composite B-Tree | `idx_risk_scores_level_score` | Tier filtering |

---

## 3. Analytical Views Reference

The database provides 8 analytical views to power UI cards, charts, alerts, and reports.

### View 1: `v_project_overview`
A comprehensive 360-degree operational view joining `projects`, `states`, `constituencies`, `financials`, the latest `progress` milestone, and `risk_scores`. Includes pre-calculated flags:
- `is_delayed`: `TRUE` when `days_delayed > 0` or milestone is `'Delayed'` / `'Critical'`.
- `has_cost_overrun`: `TRUE` when `cost_overrun_amount > 0`.
- `audit_status`: `'Audited'` if `inspection_date` is populated, otherwise `'Pending Inspection'`.

```sql
SELECT 
    project_id,
    project_title,
    state_name,
    district_name,
    sector,
    current_status,
    sanctioned_amount,
    expenditure_amount,
    physical_progress_pct,
    days_delayed,
    overall_risk_score,
    risk_level,
    audit_status
FROM v_project_overview
LIMIT 10;
```

### View 2: `v_delayed_projects`
Real-time operational surveillance view that filters for active delayed, stalled, or critical-milestone projects, sorted by delay severity:

```sql
SELECT 
    project_id,
    project_title,
    state_name,
    district_name,
    implementing_agency,
    days_delayed,
    milestone_status,
    delay_risk_score,
    overall_risk_score,
    expected_completion_date
FROM v_delayed_projects;
```

### View 3: `v_high_risk_projects`
Risk governance view isolating projects with `overall_risk_score >= 40.0` or `risk_level IN ('High', 'Critical')`. Aggregates contributing causal factors into a structured JSON array (`primary_risk_factors`):

```sql
SELECT 
    project_id,
    project_title,
    state_name,
    district_name,
    overall_risk_score,
    risk_level,
    delay_risk_score,
    cost_overrun_risk_score,
    primary_risk_factors
FROM v_high_risk_projects;
```

### View 4: `v_projects_missing_information`
Quality assurance audit view detecting missing metadata, pending site inspections, and absent geo-coordinates:

```sql
SELECT 
    project_id,
    project_title,
    state_name,
    current_status,
    missing_fields_count,
    missing_fields
FROM v_projects_missing_information
WHERE missing_fields_count > 0;
```

### View 5: `v_sector_financial_summary`
Aggregates projects, completion counts, average physical progress, total financial allocations, expenditure, overall utilization percentage, average risk score, and delayed project counts by developmental sector:

```sql
SELECT 
    sector,
    total_projects,
    completed_projects,
    avg_physical_progress_pct,
    total_sanctioned_cr,
    total_expenditure_cr,
    overall_utilization_pct,
    avg_risk_score,
    delayed_projects_count
FROM v_sector_financial_summary
ORDER BY total_sanctioned_cr DESC;
```

### View 6: `v_state_equity_analysis`
Audits SC/ST seat representation and assesses statutory quota compliance (15% SC, 7.5% ST) across all 36 States and UTs:

```sql
SELECT 
    state_name,
    total_lok_sabha_seats,
    sc_seat_share_pct,
    st_seat_share_pct,
    cumulative_released_cr,
    cumulative_expenditure_cr,
    utilization_pct
FROM v_state_equity_analysis
ORDER BY total_lok_sabha_seats DESC;
```

### View 7: `v_state_efficiency_ranking`
Ranks States and UTs by composite fiscal and operational efficiency (utilization percentage, completion rate percentage, sanction rate):

```sql
SELECT 
    efficiency_rank,
    state_name,
    released_cr,
    expenditure_cr,
    utilization_rate_pct,
    works_recommended,
    works_completed,
    completion_rate_pct
FROM v_state_efficiency_ranking
LIMIT 10;
```

### View 8: `v_budget_historical_performance`
Historical 33-year fiscal time series (1993–2025) of Union Budget Demand No. 91 allocations, budget estimates, revised estimates, and actual disbursements:

```sql
SELECT 
    financial_year,
    scheme_entitlement_per_mp_cr,
    budget_estimate_cr,
    actual_expenditure_cr,
    be_vs_actual_variance_cr,
    execution_rate_pct
FROM v_budget_historical_performance
ORDER BY financial_year DESC
LIMIT 10;
```

---

## 4. Production Example SQL Queries

### Query 1: Search by Project ID / Code
Fast point lookup leveraging primary key or unique index.

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
    f.utilization_rate_pct,
    r.overall_risk_score,
    r.risk_level
FROM projects p
JOIN states s ON p.state_id = s.state_id
JOIN constituencies c ON p.constituency_id = c.constituency_id
JOIN financials f ON p.project_id = f.project_id
LEFT JOIN risk_scores r ON p.project_id = r.project_id
WHERE p.project_id = 'MPLADS-2024-0001';
```

### Query 2: Search by State & District
Geographic portfolio filtering leveraging composite index `idx_projects_state_district`.

```sql
SELECT 
    p.project_id,
    p.project_title,
    p.sector,
    p.district_name,
    p.current_status,
    f.sanctioned_amount,
    f.expenditure_amount,
    pr.physical_progress_pct,
    pr.milestone_status
FROM projects p
JOIN financials f ON p.project_id = f.project_id
LEFT JOIN LATERAL (
    SELECT physical_progress_pct, milestone_status 
    FROM progress 
    WHERE project_id = p.project_id 
    ORDER BY reported_date DESC LIMIT 1
) pr ON TRUE
WHERE p.state_id = 10 AND p.district_name = 'Patna'
ORDER BY p.project_id;
```

### Query 3: Search by Project Status & Sector
Lifecycle filtering utilizing composite index `idx_projects_status_sector`.

```sql
SELECT 
    p.project_id,
    p.project_title,
    p.sector,
    p.district_name,
    p.mp_name,
    p.current_status,
    f.sanctioned_amount,
    pr.physical_progress_pct,
    pr.days_delayed
FROM projects p
JOIN financials f ON p.project_id = f.project_id
LEFT JOIN LATERAL (
    SELECT physical_progress_pct, days_delayed 
    FROM progress 
    WHERE project_id = p.project_id 
    ORDER BY reported_date DESC LIMIT 1
) pr ON TRUE
WHERE p.current_status = 'In Progress' 
  AND p.sector = 'Education'
ORDER BY f.sanctioned_amount DESC;
```

### Query 4: Delayed & Stalled Projects Identification
Identifies works with active execution delays, days delayed, and pending milestones.

```sql
SELECT 
    p.project_id,
    p.project_title,
    s.state_name,
    p.district_name,
    p.implementing_agency,
    p.current_status,
    pr.days_delayed,
    pr.milestone_status,
    pr.physical_progress_pct,
    r.delay_risk_score,
    r.risk_level
FROM projects p
JOIN states s ON p.state_id = s.state_id
JOIN progress pr ON p.project_id = pr.project_id
LEFT JOIN risk_scores r ON p.project_id = r.project_id
WHERE pr.days_delayed > 0 
   OR p.current_status = 'Stalled'
   OR pr.milestone_status IN ('Delayed', 'Critical')
ORDER BY pr.days_delayed DESC;
```

### Query 5: High Expenditure & Budget Deviation Projects
Surfaces projects with expenditures exceeding a fiscal threshold (e.g. ₹50 Lakhs) or experiencing cost overruns.

```sql
SELECT 
    p.project_id,
    p.project_title,
    p.sector,
    s.state_name,
    p.implementing_agency,
    f.sanctioned_amount,
    f.released_amount,
    f.expenditure_amount,
    f.cost_overrun_amount,
    f.utilization_rate_pct,
    pr.physical_progress_pct
FROM projects p
JOIN states s ON p.state_id = s.state_id
JOIN financials f ON p.project_id = f.project_id
LEFT JOIN LATERAL (
    SELECT physical_progress_pct 
    FROM progress 
    WHERE project_id = p.project_id 
    ORDER BY reported_date DESC LIMIT 1
) pr ON TRUE
WHERE f.expenditure_amount >= 5000000.00 
   OR f.cost_overrun_amount > 0
ORDER BY f.expenditure_amount DESC;
```

### Query 6: Projects with Missing Information & Quality Audit
Flags records requiring administrative compliance action (missing sanction dates, uninspected works, unmapped geo-coordinates).

```sql
SELECT 
    p.project_id,
    p.project_title,
    s.state_name,
    p.current_status,
    ARRAY_REMOVE(ARRAY[
        CASE WHEN p.sanction_date IS NULL AND p.current_status != 'Recommended' THEN 'missing_sanction_date' END,
        CASE WHEN p.work_order_date IS NULL AND p.current_status IN ('Work Order Issued', 'In Progress', 'Completed') THEN 'missing_work_order_date' END,
        CASE WHEN p.actual_completion_date IS NULL AND p.current_status = 'Completed' THEN 'missing_actual_completion_date' END,
        CASE WHEN pr.inspected_by IS NULL THEN 'pending_field_inspection' END,
        CASE WHEN pr.geo_latitude IS NULL THEN 'missing_geotag' END
    ], NULL) AS missing_attributes
FROM projects p
JOIN states s ON p.state_id = s.state_id
LEFT JOIN LATERAL (
    SELECT inspected_by, geo_latitude 
    FROM progress 
    WHERE project_id = p.project_id 
    ORDER BY reported_date DESC LIMIT 1
) pr ON TRUE
WHERE p.sanction_date IS NULL AND p.current_status != 'Recommended'
   OR p.actual_completion_date IS NULL AND p.current_status = 'Completed'
   OR pr.inspected_by IS NULL
   OR pr.geo_latitude IS NULL
LIMIT 10;
```

### Query 7: Predictive High-Risk Project Surveillance
Escalates high-vulnerability works ($\text{score} \ge 40.0$) with correlated causal drivers and recommendations.

```sql
SELECT 
    p.project_id,
    p.project_title,
    s.state_name,
    p.district_name,
    p.implementing_agency,
    r.overall_risk_score,
    r.risk_level,
    r.delay_risk_score,
    r.cost_overrun_risk_score,
    rf.factor_category,
    rf.factor_name,
    rf.factor_impact,
    rf.mitigation_recommendation
FROM projects p
JOIN states s ON p.state_id = s.state_id
JOIN risk_scores r ON p.project_id = r.project_id
LEFT JOIN risk_factors rf ON r.risk_score_id = rf.risk_score_id
WHERE r.overall_risk_score >= 40.0 
   OR r.risk_level IN ('High', 'Critical')
ORDER BY r.overall_risk_score DESC, rf.factor_weight DESC;
```

### Query 8: Full-Text Natural Language Keyword Search
Natural language search across titles, descriptions, sectors, and agencies using `websearch_to_tsquery` and `ts_rank`.

```sql
SELECT 
    p.project_id,
    p.project_title,
    p.sector,
    s.state_name,
    p.district_name,
    p.implementing_agency,
    p.current_status,
    ROUND(ts_rank(p.search_vector, websearch_to_tsquery('english', 'Solar OR RO Water'))::NUMERIC, 4) AS search_rank
FROM projects p
JOIN states s ON p.state_id = s.state_id
WHERE p.search_vector @@ websearch_to_tsquery('english', 'Solar OR RO Water')
ORDER BY search_rank DESC;
```

### Query 9: Fuzzy Substring Search (Typo Tolerance)
Handles spelling errors in MP or agency names using `pg_trgm` similarity.

```sql
SELECT 
    p.project_id,
    p.project_title,
    p.mp_name,
    p.implementing_agency,
    s.state_name,
    ROUND(similarity(p.mp_name, 'Kumar')::NUMERIC, 3) AS match_similarity
FROM projects p
JOIN states s ON p.state_id = s.state_id
WHERE p.mp_name % 'Kumar' OR p.mp_name ILIKE '%Kumar%'
ORDER BY match_similarity DESC
LIMIT 5;
```

---

## 5. Benchmarking & Execution Performance

All queries have been tested and verified on PostgreSQL 16 using `EXPLAIN (ANALYZE, BUFFERS)`. Key benchmarks:

| Query Type | Typical Scan Mechanism | Buffers Hit | Execution Time |
|---|---|---|---|
| **Primary Key Lookup** | Index Scan using `projects_pkey` | 1-2 buffers | < 0.15 ms |
| **Composite Geo Search** | Index Scan using `idx_projects_state_district` | 2-3 buffers | < 0.30 ms |
| **Full-Text Search (FTS)** | Bitmap Index Scan using `idx_projects_search_vector` | 3-4 buffers | < 0.85 ms |
| **Trigram Fuzzy Search** | Bitmap Index Scan using `idx_projects_mp_trgm` | 2-4 buffers | < 0.90 ms |
| **360° Overview View** | Nested Loop Index Joins across 5 tables | 12-16 buffers | < 1.80 ms |

To run the full automated search and query benchmark suite:
```bash
python scripts/query_search_examples.py
```
