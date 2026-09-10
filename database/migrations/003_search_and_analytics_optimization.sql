-- =============================================================================
-- Migration 003: Search Optimization, Full-Text Search, & Analytical Views
-- Description: Optimizes PostgreSQL for fast project discovery and governance
--              analytics:
--              1. Enables pg_trgm for fuzzy search
--              2. Implements Full-Text Search (tsvector + GIN index)
--              3. Creates composite & performance indexes across project attributes
--              4. Creates comprehensive operational & analytical views:
--                 - v_project_overview
--                 - v_delayed_projects
--                 - v_high_risk_projects
--                 - v_projects_missing_information
--                 - v_sector_financial_summary
-- Idempotent: Safe to run repeatedly.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Full-Text Search & Fuzzy Extension Setup
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Add generated search_vector column to projects master table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'projects' AND column_name = 'search_vector'
    ) THEN
        ALTER TABLE projects ADD COLUMN search_vector TSVECTOR 
        GENERATED ALWAYS AS (
            to_tsvector('english', 
                coalesce(project_title, '') || ' ' || 
                coalesce(project_description, '') || ' ' || 
                coalesce(sector, '') || ' ' || 
                coalesce(sub_sector, '') || ' ' || 
                coalesce(district_name, '') || ' ' || 
                coalesce(implementing_agency, '') || ' ' || 
                coalesce(mp_name, '')
            )
        ) STORED;
    END IF;
END $$;

-- Full-Text Search GIN index
CREATE INDEX IF NOT EXISTS idx_projects_search_vector ON projects USING GIN(search_vector);

-- Trigram GIN indexes for fuzzy substring searches
CREATE INDEX IF NOT EXISTS idx_projects_title_trgm ON projects USING GIN (project_title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_projects_mp_trgm ON projects USING GIN (mp_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_projects_agency_trgm ON projects USING GIN (implementing_agency gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_projects_district_trgm ON projects USING GIN (district_name gin_trgm_ops);

-- -----------------------------------------------------------------------------
-- 2. High-Performance B-Tree & Composite Indexes
-- -----------------------------------------------------------------------------
-- Geo-hierarchy filtering
CREATE INDEX IF NOT EXISTS idx_projects_state_district ON projects(state_id, district_name);

-- Status & Sector composite
CREATE INDEX IF NOT EXISTS idx_projects_status_sector ON projects(current_status, sector);

-- Specific MP & Agency lookups
CREATE INDEX IF NOT EXISTS idx_projects_mp_name ON projects(mp_name);
CREATE INDEX IF NOT EXISTS idx_projects_agency ON projects(implementing_agency);

-- Financial amounts & thresholds
CREATE INDEX IF NOT EXISTS idx_financials_sanctioned ON financials(sanctioned_amount);
CREATE INDEX IF NOT EXISTS idx_financials_released ON financials(released_amount);
CREATE INDEX IF NOT EXISTS idx_financials_expenditure ON financials(expenditure_amount);
CREATE INDEX IF NOT EXISTS idx_financials_unspent ON financials(unspent_balance);
CREATE INDEX IF NOT EXISTS idx_financials_utilization_filtered ON financials(utilization_rate_pct) WHERE utilization_rate_pct IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_financials_cost_overrun_filtered ON financials(cost_overrun_amount) WHERE cost_overrun_amount > 0;

-- Progress tracking & milestone monitoring
CREATE INDEX IF NOT EXISTS idx_progress_milestone_delayed ON progress(milestone_status, days_delayed);
CREATE INDEX IF NOT EXISTS idx_progress_physical_pct ON progress(physical_progress_pct);
CREATE INDEX IF NOT EXISTS idx_progress_financial_pct ON progress(financial_progress_pct);
CREATE INDEX IF NOT EXISTS idx_progress_inspection ON progress(inspection_date) WHERE inspection_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_progress_stage ON progress(current_stage);

-- Risk analysis & ranking
CREATE INDEX IF NOT EXISTS idx_risk_scores_overall_desc ON risk_scores(overall_risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_scores_delay_desc ON risk_scores(delay_risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_scores_cost_desc ON risk_scores(cost_overrun_risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_scores_level_score ON risk_scores(risk_level, overall_risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_factors_category_impact ON risk_factors(factor_category, factor_impact);

-- Temporal history audit
CREATE INDEX IF NOT EXISTS idx_history_proj_time ON project_history(project_id, event_timestamp DESC);

-- -----------------------------------------------------------------------------
-- 3. Operational & Analytical Views
-- -----------------------------------------------------------------------------

-- View 1: Unified Project Overview
-- Combines project metadata, state, constituency, financials, latest progress, and risk scores.
CREATE OR REPLACE VIEW v_project_overview AS
SELECT 
    p.project_id,
    p.project_code,
    p.project_title,
    p.project_description,
    p.sector,
    p.sub_sector,
    p.state_id,
    s.state_name,
    s.canonical_state_key,
    p.constituency_id,
    c.constituency_name,
    c.reservation_category,
    p.district_name,
    p.block_name,
    p.implementing_agency,
    p.mp_name,
    p.house_of_parliament,
    p.financial_year,
    p.current_status,
    p.recommendation_date,
    p.sanction_date,
    p.work_order_date,
    p.expected_completion_date,
    p.actual_completion_date,
    -- Financials
    f.currency,
    f.recommended_amount,
    f.sanctioned_amount,
    f.released_amount,
    f.expenditure_amount,
    f.unspent_balance,
    f.utilization_rate_pct,
    f.cost_overrun_amount,
    f.cost_overrun_pct,
    f.last_disbursement_date,
    -- Latest Progress
    pr.reported_date AS progress_reported_date,
    pr.physical_progress_pct,
    pr.financial_progress_pct,
    pr.current_stage,
    pr.days_delayed,
    pr.milestone_status,
    pr.inspected_by,
    pr.inspection_date,
    pr.geo_latitude,
    pr.geo_longitude,
    pr.photo_evidence_url,
    -- Risk Scores
    rs.overall_risk_score,
    rs.delay_risk_score,
    rs.cost_overrun_risk_score,
    rs.non_completion_risk_score,
    rs.leakage_risk_score,
    rs.risk_level,
    rs.confidence_score,
    rs.assessment_date AS risk_assessment_date,
    -- Derived Analytical Flags
    CASE 
        WHEN pr.days_delayed > 0 OR pr.milestone_status IN ('Delayed', 'Critical') THEN TRUE
        ELSE FALSE
    END AS is_delayed,
    CASE 
        WHEN f.cost_overrun_amount > 0 THEN TRUE
        ELSE FALSE
    END AS has_cost_overrun,
    CASE 
        WHEN pr.inspection_date IS NOT NULL THEN 'Audited'
        ELSE 'Pending Inspection'
    END AS audit_status
FROM projects p
JOIN states s ON p.state_id = s.state_id
JOIN constituencies c ON p.constituency_id = c.constituency_id
LEFT JOIN financials f ON p.project_id = f.project_id
LEFT JOIN (
    SELECT DISTINCT ON (project_id) *
    FROM progress
    ORDER BY project_id, reported_date DESC
) pr ON p.project_id = pr.project_id
LEFT JOIN risk_scores rs ON p.project_id = rs.project_id;

COMMENT ON VIEW v_project_overview IS 'Unified operational project reporting view joining governance, financial accounting, physical execution, and risk assessment.';


-- View 2: Delayed Projects Monitoring View
-- Filters for delayed or stalled projects and computes delay metrics.
CREATE OR REPLACE VIEW v_delayed_projects AS
SELECT 
    v.project_id,
    v.project_code,
    v.project_title,
    v.state_name,
    v.constituency_name,
    v.district_name,
    v.mp_name,
    v.sector,
    v.implementing_agency,
    v.current_status,
    v.recommendation_date,
    v.expected_completion_date,
    v.days_delayed,
    v.milestone_status,
    v.physical_progress_pct,
    v.financial_progress_pct,
    v.sanctioned_amount,
    v.expenditure_amount,
    v.delay_risk_score,
    v.risk_level
FROM v_project_overview v
WHERE v.days_delayed > 0 OR v.milestone_status IN ('Delayed', 'Critical') OR v.current_status = 'Stalled'
ORDER BY v.days_delayed DESC, v.delay_risk_score DESC;

COMMENT ON VIEW v_delayed_projects IS 'Active operational view prioritizing delayed or stalled projects by severity of schedule overrun.';


-- View 3: High Risk Projects Alert View
-- Filters for high and critical risk projects and bundles causal factors.
CREATE OR REPLACE VIEW v_high_risk_projects AS
SELECT 
    v.project_id,
    v.project_code,
    v.project_title,
    v.state_name,
    v.constituency_name,
    v.district_name,
    v.mp_name,
    v.sector,
    v.implementing_agency,
    v.current_status,
    v.overall_risk_score,
    v.delay_risk_score,
    v.cost_overrun_risk_score,
    v.non_completion_risk_score,
    v.leakage_risk_score,
    v.risk_level,
    v.confidence_score,
    v.sanctioned_amount,
    v.expenditure_amount,
    v.days_delayed,
    v.milestone_status,
    (
        SELECT json_agg(json_build_object(
            'category', rf.factor_category,
            'factor', rf.factor_name,
            'weight', rf.factor_weight,
            'impact', rf.factor_impact,
            'recommendation', rf.mitigation_recommendation
        ))
        FROM risk_factors rf
        WHERE rf.project_id = v.project_id
    ) AS primary_risk_factors
FROM v_project_overview v
WHERE v.overall_risk_score >= 40.0 OR v.risk_level IN ('High', 'Critical')
ORDER BY v.overall_risk_score DESC;

COMMENT ON VIEW v_high_risk_projects IS 'Governance surveillance view isolating vulnerable projects with aggregated causal risk factors.';


-- View 4: Projects with Missing Information / Governance Gaps
-- Identifies records with pending completion dates, inspections, or incomplete dates.
CREATE OR REPLACE VIEW v_projects_missing_information AS
SELECT 
    v.project_id,
    v.project_code,
    v.project_title,
    v.state_name,
    v.constituency_name,
    v.current_status,
    ARRAY_REMOVE(ARRAY[
        CASE WHEN v.actual_completion_date IS NULL THEN 'Pending Actual Completion Date' ELSE NULL END,
        CASE WHEN v.sanction_date IS NULL THEN 'Missing Sanction Date' ELSE NULL END,
        CASE WHEN v.work_order_date IS NULL AND v.current_status IN ('Work Order Issued', 'In Progress', 'Completed') THEN 'Missing Work Order Date' ELSE NULL END,
        CASE WHEN v.inspection_date IS NULL THEN 'Pending Inspection Audit' ELSE NULL END,
        CASE WHEN v.geo_latitude IS NULL OR v.geo_longitude IS NULL THEN 'Missing Geo-Coordinates' ELSE NULL END,
        CASE WHEN v.photo_evidence_url IS NULL THEN 'Missing Photo Evidence' ELSE NULL END,
        CASE WHEN v.block_name IS NULL THEN 'Unspecified Administrative Block' ELSE NULL END
    ], NULL) AS missing_fields,
    CARDINALITY(ARRAY_REMOVE(ARRAY[
        CASE WHEN v.actual_completion_date IS NULL THEN 'Pending Actual Completion Date' ELSE NULL END,
        CASE WHEN v.sanction_date IS NULL THEN 'Missing Sanction Date' ELSE NULL END,
        CASE WHEN v.work_order_date IS NULL AND v.current_status IN ('Work Order Issued', 'In Progress', 'Completed') THEN 'Missing Work Order Date' ELSE NULL END,
        CASE WHEN v.inspection_date IS NULL THEN 'Pending Inspection Audit' ELSE NULL END,
        CASE WHEN v.geo_latitude IS NULL OR v.geo_longitude IS NULL THEN 'Missing Geo-Coordinates' ELSE NULL END,
        CASE WHEN v.photo_evidence_url IS NULL THEN 'Missing Photo Evidence' ELSE NULL END,
        CASE WHEN v.block_name IS NULL THEN 'Unspecified Administrative Block' ELSE NULL END
    ], NULL)) AS missing_fields_count
FROM v_project_overview v
WHERE v.actual_completion_date IS NULL 
   OR v.inspection_date IS NULL 
   OR v.geo_latitude IS NULL 
   OR v.photo_evidence_url IS NULL
   OR v.sanction_date IS NULL
ORDER BY missing_fields_count DESC, v.project_id ASC;

COMMENT ON VIEW v_projects_missing_information IS 'Quality assurance and compliance view identifying data completeness gaps for district administrations.';


-- View 5: Sector-wise Financial & Progress Summary
-- Aggregates project performance, utilization, and delay counts by sector.
CREATE OR REPLACE VIEW v_sector_financial_summary AS
SELECT 
    p.sector,
    count(p.project_id) AS total_projects,
    count(CASE WHEN p.current_status = 'Completed' THEN 1 END) AS completed_projects,
    count(CASE WHEN p.current_status = 'In Progress' THEN 1 END) AS in_progress_projects,
    count(CASE WHEN p.current_status = 'Stalled' THEN 1 END) AS stalled_projects,
    ROUND(AVG(pr.physical_progress_pct), 2) AS avg_physical_progress_pct,
    ROUND(SUM(f.sanctioned_amount), 2) AS total_sanctioned_amount,
    ROUND(SUM(f.released_amount), 2) AS total_released_amount,
    ROUND(SUM(f.expenditure_amount), 2) AS total_expenditure_amount,
    ROUND(SUM(f.unspent_balance), 2) AS total_unspent_balance,
    ROUND(
        CASE 
            WHEN SUM(f.released_amount) > 0 
            THEN (SUM(f.expenditure_amount) / SUM(f.released_amount) * 100.0)
            ELSE 0.0 
        END, 2
    ) AS overall_utilization_pct,
    ROUND(AVG(rs.overall_risk_score), 2) AS avg_sector_risk_score,
    SUM(CASE WHEN pr.days_delayed > 0 THEN 1 ELSE 0 END) AS delayed_projects_count
FROM projects p
LEFT JOIN financials f ON p.project_id = f.project_id
LEFT JOIN (
    SELECT DISTINCT ON (project_id) project_id, physical_progress_pct, days_delayed
    FROM progress
    ORDER BY project_id, reported_date DESC
) pr ON p.project_id = pr.project_id
LEFT JOIN risk_scores rs ON p.project_id = rs.project_id
GROUP BY p.sector
ORDER BY total_sanctioned_amount DESC;

COMMENT ON VIEW v_sector_financial_summary IS 'Longitudinal sector intelligence view comparing funding allocation, expenditure efficiency, and execution pace.';
