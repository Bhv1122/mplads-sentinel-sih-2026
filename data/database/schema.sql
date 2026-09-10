-- =============================================================================
-- Migration 001: Initial Core MPLADS Dimension and Registry Schema
-- Description: Creates official administrative registries, macro indicators,
--              longitudinal union budget series, and parliamentary audited progress.
-- Idempotent: Uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
-- =============================================================================

-- 1. States & Union Territories Master Registry
CREATE TABLE IF NOT EXISTS states (
    state_id INTEGER PRIMARY KEY,
    state_name VARCHAR(100) NOT NULL,
    category VARCHAR(30) NOT NULL CHECK (category IN ('State', 'Union Territory')),
    canonical_state_key VARCHAR(100) NOT NULL UNIQUE
);

COMMENT ON TABLE states IS 'Master registry of all 28 States and 8 Union Territories in the Republic of India.';

-- 2. Parliamentary Constituencies Roster
CREATE TABLE IF NOT EXISTS constituencies (
    constituency_id INTEGER PRIMARY KEY,
    state_id INTEGER NOT NULL REFERENCES states(state_id) ON DELETE RESTRICT,
    state_name VARCHAR(100) NOT NULL,
    constituency_name VARCHAR(100) NOT NULL,
    raw_caption VARCHAR(150) NOT NULL,
    reservation_category VARCHAR(20) NOT NULL CHECK (reservation_category IN ('General', 'SC', 'ST')),
    canonical_state_key VARCHAR(100) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_constituencies_state_id ON constituencies(state_id);
CREATE INDEX IF NOT EXISTS idx_constituencies_reservation ON constituencies(reservation_category);
CREATE INDEX IF NOT EXISTS idx_constituencies_canonical_state ON constituencies(canonical_state_key);

-- 3. National Macro Progress Summary Tiles
CREATE TABLE IF NOT EXISTS national_summary (
    metric_key VARCHAR(150) PRIMARY KEY,
    metric_description TEXT NOT NULL,
    count_works NUMERIC(12, 0) NULL,
    amount_inr NUMERIC(16, 2) NOT NULL CHECK (amount_inr >= 0),
    amount_crores NUMERIC(12, 2) NOT NULL CHECK (amount_crores >= 0)
);

-- 4. Disaster & Calamity Relief Consents
CREATE TABLE IF NOT EXISTS calamity_relief (
    s_no INTEGER PRIMARY KEY,
    honorific VARCHAR(20) NULL,
    mp_name VARCHAR(150) NOT NULL,
    house_of_parliament VARCHAR(30) NOT NULL CHECK (house_of_parliament IN ('Lok Sabha', 'Rajya Sabha')),
    tenure VARCHAR(50) NOT NULL,
    calamity_name VARCHAR(150) NOT NULL,
    calamity_type VARCHAR(50) NOT NULL,
    consented_amount_inr NUMERIC(14, 2) NOT NULL CHECK (consented_amount_inr >= 0),
    consented_amount_lakhs NUMERIC(10, 2) NOT NULL CHECK (consented_amount_lakhs >= 0 AND consented_amount_lakhs <= 100.00),
    consent_date_iso DATE NOT NULL,
    tenure_start_date_iso DATE NOT NULL,
    tenure_end_date_iso DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_calamity_house ON calamity_relief(house_of_parliament);
CREATE INDEX IF NOT EXISTS idx_calamity_date ON calamity_relief(consent_date_iso);

-- 5. Union Budget Longitudinal Outlays (1993-94 to 2025-26)
CREATE TABLE IF NOT EXISTS union_budget (
    financial_year VARCHAR(10) PRIMARY KEY CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    start_year INTEGER NOT NULL CHECK (start_year >= 1993),
    end_year INTEGER NOT NULL CHECK (end_year > start_year),
    scheme_entitlement_per_mp_cr NUMERIC(6, 2) NOT NULL CHECK (scheme_entitlement_per_mp_cr >= 0),
    budget_estimate_cr NUMERIC(10, 2) NOT NULL CHECK (budget_estimate_cr >= 0),
    revised_estimate_cr NUMERIC(10, 2) NULL,
    actual_expenditure_cr NUMERIC(10, 2) NULL,
    be_vs_actual_variance_cr NUMERIC(10, 2) NULL,
    major_head INTEGER NOT NULL DEFAULT 3475,
    status_notes TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_budget_start_year ON union_budget(start_year);

-- 6. Parliamentary Audited State Financial & Physical Progress
CREATE TABLE IF NOT EXISTS parliament_qa_state_expenditure (
    state_id INTEGER PRIMARY KEY,
    state_name VARCHAR(100) NOT NULL,
    canonical_state_key VARCHAR(100) NOT NULL REFERENCES states(canonical_state_key) ON DELETE RESTRICT,
    entitlement_cr NUMERIC(12, 2) NOT NULL CHECK (entitlement_cr >= 0),
    released_cr NUMERIC(12, 2) NOT NULL CHECK (released_cr >= 0),
    expenditure_cr NUMERIC(12, 2) NOT NULL CHECK (expenditure_cr >= 0),
    unspent_balance_cr NUMERIC(12, 2) NOT NULL CHECK (unspent_balance_cr >= 0),
    utilization_rate_pct NUMERIC(6, 2) NOT NULL CHECK (utilization_rate_pct >= 0 AND utilization_rate_pct <= 100),
    works_recommended INTEGER NOT NULL CHECK (works_recommended >= 0),
    works_sanctioned INTEGER NOT NULL CHECK (works_sanctioned >= 0),
    works_completed INTEGER NOT NULL CHECK (works_completed >= 0),
    sanction_rate_pct NUMERIC(6, 2) NOT NULL CHECK (sanction_rate_pct >= 0 AND sanction_rate_pct <= 100),
    completion_rate_pct NUMERIC(6, 2) NOT NULL CHECK (completion_rate_pct >= 0 AND completion_rate_pct <= 100),
    is_utilization_valid BOOLEAN NOT NULL DEFAULT TRUE,
    is_workflow_valid BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_qa_workflow CHECK (works_completed <= works_sanctioned AND works_sanctioned <= works_recommended)
);

CREATE INDEX IF NOT EXISTS idx_qa_state_key ON parliament_qa_state_expenditure(canonical_state_key);
CREATE INDEX IF NOT EXISTS idx_qa_utilization ON parliament_qa_state_expenditure(utilization_rate_pct);

-- 7. Integrated Master Dimension Table
CREATE TABLE IF NOT EXISTS master_dim_states_constituencies (
    state_id INTEGER PRIMARY KEY REFERENCES states(state_id) ON DELETE RESTRICT,
    state_name VARCHAR(100) NOT NULL,
    canonical_state_key VARCHAR(100) NOT NULL REFERENCES states(canonical_state_key) ON DELETE RESTRICT,
    category VARCHAR(30) NOT NULL CHECK (category IN ('State', 'Union Territory')),
    total_lok_sabha_seats INTEGER NOT NULL CHECK (total_lok_sabha_seats > 0),
    general_seats INTEGER NOT NULL CHECK (general_seats >= 0),
    sc_reserved_seats INTEGER NOT NULL CHECK (sc_reserved_seats >= 0),
    st_reserved_seats INTEGER NOT NULL CHECK (st_reserved_seats >= 0),
    sc_seat_share_pct NUMERIC(6, 2) NOT NULL,
    st_seat_share_pct NUMERIC(6, 2) NOT NULL,
    statutory_sc_allocation_pct NUMERIC(5, 2) NOT NULL DEFAULT 15.00,
    statutory_st_allocation_pct NUMERIC(5, 2) NOT NULL DEFAULT 7.50,
    cumulative_released_cr NUMERIC(12, 2) NOT NULL CHECK (cumulative_released_cr >= 0),
    cumulative_expenditure_cr NUMERIC(12, 2) NOT NULL CHECK (cumulative_expenditure_cr >= 0),
    unspent_balance_cr NUMERIC(12, 2) NOT NULL CHECK (unspent_balance_cr >= 0),
    utilization_pct NUMERIC(6, 2) NOT NULL CHECK (utilization_pct >= 0 AND utilization_pct <= 100),
    works_completed_count INTEGER NOT NULL CHECK (works_completed_count >= 0),
    CONSTRAINT chk_seat_sum CHECK (general_seats + sc_reserved_seats + st_reserved_seats = total_lok_sabha_seats)
);

CREATE INDEX IF NOT EXISTS idx_master_category ON master_dim_states_constituencies(category);
CREATE INDEX IF NOT EXISTS idx_master_utilization ON master_dim_states_constituencies(utilization_pct);

-- Analytical Views
CREATE OR REPLACE VIEW v_state_equity_analysis AS
SELECT
    state_id,
    state_name,
    category,
    total_lok_sabha_seats,
    sc_reserved_seats,
    sc_seat_share_pct,
    statutory_sc_allocation_pct,
    (sc_seat_share_pct - statutory_sc_allocation_pct) AS sc_share_vs_statutory_delta_pct,
    st_reserved_seats,
    st_seat_share_pct,
    statutory_st_allocation_pct,
    (st_seat_share_pct - statutory_st_allocation_pct) AS st_share_vs_statutory_delta_pct,
    cumulative_released_cr,
    ROUND(cumulative_released_cr * (statutory_sc_allocation_pct / 100.0), 2) AS mandated_sc_outlay_target_cr,
    ROUND(cumulative_released_cr * (statutory_st_allocation_pct / 100.0), 2) AS mandated_st_outlay_target_cr
FROM master_dim_states_constituencies;

CREATE OR REPLACE VIEW v_state_efficiency_ranking AS
SELECT
    p.state_id,
    p.state_name,
    s.category,
    p.released_cr,
    p.expenditure_cr,
    p.unspent_balance_cr,
    p.utilization_rate_pct,
    RANK() OVER (ORDER BY p.utilization_rate_pct DESC) AS rank_utilization,
    p.sanction_rate_pct,
    RANK() OVER (ORDER BY p.sanction_rate_pct DESC) AS rank_sanction_rate,
    p.completion_rate_pct,
    RANK() OVER (ORDER BY p.completion_rate_pct DESC) AS rank_completion_rate,
    p.works_recommended,
    p.works_sanctioned,
    p.works_completed
FROM parliament_qa_state_expenditure p
JOIN states s ON p.canonical_state_key = s.canonical_state_key;

CREATE OR REPLACE VIEW v_budget_historical_performance AS
SELECT
    financial_year,
    start_year,
    scheme_entitlement_per_mp_cr,
    budget_estimate_cr,
    revised_estimate_cr,
    actual_expenditure_cr,
    be_vs_actual_variance_cr,
    CASE
        WHEN budget_estimate_cr > 0 AND actual_expenditure_cr IS NOT NULL
        THEN ROUND((actual_expenditure_cr / budget_estimate_cr * 100.0), 2)
        ELSE NULL
    END AS budget_utilization_pct,
    status_notes
FROM union_budget
ORDER BY start_year ASC;


-- =============================================================================
-- Migration 002: Project Tracking, Execution Progress, and Risk Prediction Schema
-- Description: Creates the 6 core operational tables for project lifecycle management:
--              1. projects
--              2. financials
--              3. progress
--              4. risk_scores
--              5. risk_factors
--              6. project_history
-- Idempotent: Uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Projects Master Table
-- Stores work-level attributes, administrative jurisdiction, implementing agency,
-- and chronological milestone dates.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    project_id VARCHAR(64) PRIMARY KEY,
    project_code VARCHAR(64) UNIQUE NOT NULL,
    project_title VARCHAR(255) NOT NULL,
    project_description TEXT NULL,
    sector VARCHAR(100) NOT NULL,
    sub_sector VARCHAR(100) NULL,
    state_id INTEGER NOT NULL REFERENCES states(state_id) ON DELETE RESTRICT,
    constituency_id INTEGER NOT NULL REFERENCES constituencies(constituency_id) ON DELETE RESTRICT,
    district_name VARCHAR(100) NOT NULL,
    block_name VARCHAR(100) NULL,
    implementing_agency VARCHAR(150) NOT NULL,
    mp_name VARCHAR(150) NOT NULL,
    house_of_parliament VARCHAR(30) NOT NULL CHECK (house_of_parliament IN ('Lok Sabha', 'Rajya Sabha')),
    financial_year VARCHAR(10) NOT NULL CHECK (financial_year ~ '^\d{4}-\d{2}$'),
    current_status VARCHAR(30) NOT NULL DEFAULT 'Recommended' 
        CHECK (current_status IN ('Recommended', 'Sanctioned', 'Work Order Issued', 'In Progress', 'Completed', 'Cancelled', 'Stalled')),
    recommendation_date DATE NOT NULL,
    sanction_date DATE NULL,
    work_order_date DATE NULL,
    expected_completion_date DATE NULL,
    actual_completion_date DATE NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_proj_sanction_date CHECK (sanction_date IS NULL OR sanction_date >= recommendation_date),
    CONSTRAINT chk_proj_work_order_date CHECK (work_order_date IS NULL OR sanction_date IS NULL OR work_order_date >= sanction_date),
    CONSTRAINT chk_proj_completion_date CHECK (actual_completion_date IS NULL OR work_order_date IS NULL OR actual_completion_date >= work_order_date)
);

-- Primary query and lookup indexes for projects
CREATE INDEX IF NOT EXISTS idx_projects_code ON projects(project_code);
CREATE INDEX IF NOT EXISTS idx_projects_state_id ON projects(state_id);
CREATE INDEX IF NOT EXISTS idx_projects_constituency_id ON projects(constituency_id);
CREATE INDEX IF NOT EXISTS idx_projects_district ON projects(district_name);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(current_status);
CREATE INDEX IF NOT EXISTS idx_projects_sector ON projects(sector);
CREATE INDEX IF NOT EXISTS idx_projects_financial_year ON projects(financial_year);
CREATE INDEX IF NOT EXISTS idx_projects_rec_date ON projects(recommendation_date);
CREATE INDEX IF NOT EXISTS idx_projects_actual_comp_date ON projects(actual_completion_date);

COMMENT ON TABLE projects IS 'Work-level microdata master catalog representing individual developmental projects recommended by Members of Parliament under MPLADS.';

-- -----------------------------------------------------------------------------
-- 2. Project Financials Table
-- Captures recommended costs, administrative sanctions, releases, expenditures,
-- cost overruns, and fund utilization rates.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS financials (
    financial_id BIGSERIAL PRIMARY KEY,
    project_id VARCHAR(64) UNIQUE NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    currency VARCHAR(10) NOT NULL DEFAULT 'INR',
    recommended_amount NUMERIC(14, 2) NOT NULL CHECK (recommended_amount >= 0),
    sanctioned_amount NUMERIC(14, 2) NULL CHECK (sanctioned_amount IS NULL OR sanctioned_amount >= 0),
    released_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00 CHECK (released_amount >= 0),
    expenditure_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00 CHECK (expenditure_amount >= 0),
    unspent_balance NUMERIC(14, 2) GENERATED ALWAYS AS (released_amount - expenditure_amount) STORED,
    utilization_rate_pct NUMERIC(6, 2) NULL CHECK (utilization_rate_pct IS NULL OR (utilization_rate_pct >= 0 AND utilization_rate_pct <= 100)),
    cost_overrun_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00 CHECK (cost_overrun_amount >= 0),
    cost_overrun_pct NUMERIC(6, 2) NOT NULL DEFAULT 0.00 CHECK (cost_overrun_pct >= 0),
    last_disbursement_date DATE NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_financials_project_id ON financials(project_id);
CREATE INDEX IF NOT EXISTS idx_financials_utilization ON financials(utilization_rate_pct);
CREATE INDEX IF NOT EXISTS idx_financials_cost_overrun ON financials(cost_overrun_amount);

COMMENT ON TABLE financials IS 'Granular financial allocation, disbursement, expenditure, and variance accounting per project.';

-- -----------------------------------------------------------------------------
-- 3. Project Physical & Inspection Progress Table
-- Tracks sequential progress updates, milestone stages, delay durations,
-- geo-tagging coordinates, and field inspection audits.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS progress (
    progress_id BIGSERIAL PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    reported_date DATE NOT NULL,
    physical_progress_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00 
        CHECK (physical_progress_pct >= 0.00 AND physical_progress_pct <= 100.00),
    financial_progress_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00 
        CHECK (financial_progress_pct >= 0.00 AND financial_progress_pct <= 100.00),
    current_stage VARCHAR(50) NOT NULL 
        CHECK (current_stage IN ('Feasibility', 'Tendering', 'Contract Awarded', 'Foundation', 'Structure', 'Finishing', 'Inspection', 'Commissioned', 'Completed')),
    days_delayed INTEGER NOT NULL DEFAULT 0 CHECK (days_delayed >= 0),
    milestone_status VARCHAR(30) NOT NULL DEFAULT 'On Track' 
        CHECK (milestone_status IN ('On Track', 'Delayed', 'Critical', 'Completed')),
    inspected_by VARCHAR(150) NULL,
    inspection_date DATE NULL,
    inspection_remarks TEXT NULL,
    geo_latitude NUMERIC(10, 7) NULL CHECK (geo_latitude IS NULL OR (geo_latitude >= 6.0 AND geo_latitude <= 38.0)),
    geo_longitude NUMERIC(10, 7) NULL CHECK (geo_longitude IS NULL OR (geo_longitude >= 68.0 AND geo_longitude <= 98.0)),
    photo_evidence_url VARCHAR(255) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_progress_project_date UNIQUE (project_id, reported_date)
);

CREATE INDEX IF NOT EXISTS idx_progress_project_id ON progress(project_id);
CREATE INDEX IF NOT EXISTS idx_progress_reported_date ON progress(reported_date);
CREATE INDEX IF NOT EXISTS idx_progress_milestone_status ON progress(milestone_status);
CREATE INDEX IF NOT EXISTS idx_progress_days_delayed ON progress(days_delayed);
CREATE INDEX IF NOT EXISTS idx_progress_stage ON progress(current_stage);

COMMENT ON TABLE progress IS 'Chronological physical execution updates, milestone tracking, and geo-tagged audit verifications.';

-- -----------------------------------------------------------------------------
-- 4. Project Risk Scores Table
-- AI/ML and heuristic predictive risk scoring covering overall project risk,
-- delay likelihood, budget overrun probability, and leakage susceptibility.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_scores (
    risk_score_id BIGSERIAL PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    overall_risk_score NUMERIC(5, 2) NOT NULL CHECK (overall_risk_score >= 0.00 AND overall_risk_score <= 100.00),
    delay_risk_score NUMERIC(5, 2) NOT NULL CHECK (delay_risk_score >= 0.00 AND delay_risk_score <= 100.00),
    cost_overrun_risk_score NUMERIC(5, 2) NOT NULL CHECK (cost_overrun_risk_score >= 0.00 AND cost_overrun_risk_score <= 100.00),
    non_completion_risk_score NUMERIC(5, 2) NOT NULL CHECK (non_completion_risk_score >= 0.00 AND non_completion_risk_score <= 100.00),
    leakage_risk_score NUMERIC(5, 2) NOT NULL CHECK (leakage_risk_score >= 0.00 AND leakage_risk_score <= 100.00),
    risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('Low', 'Moderate', 'High', 'Critical')),
    confidence_score NUMERIC(4, 3) NOT NULL CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000),
    assessment_date DATE NOT NULL,
    model_version VARCHAR(50) NOT NULL DEFAULT 'v1.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    weights_used JSONB NULL,
    config_version VARCHAR(50) NULL DEFAULT 'v1.0',
    engine_version VARCHAR(50) NULL DEFAULT '1.0.0',
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_risk_scores_project UNIQUE (project_id)
);

CREATE INDEX IF NOT EXISTS idx_risk_scores_project_id ON risk_scores(project_id);
CREATE INDEX IF NOT EXISTS idx_risk_scores_risk_level ON risk_scores(risk_level);
CREATE INDEX IF NOT EXISTS idx_risk_scores_overall ON risk_scores(overall_risk_score);
CREATE INDEX IF NOT EXISTS idx_risk_scores_date ON risk_scores(assessment_date);
CREATE INDEX IF NOT EXISTS idx_risk_scores_updated_at ON risk_scores(updated_at);
CREATE INDEX IF NOT EXISTS idx_risk_scores_calculated_at ON risk_scores(calculated_at);

COMMENT ON TABLE risk_scores IS 'Multi-dimensional risk assessment outputs evaluating project delay, cost overrun, and completion feasibility.';

-- -----------------------------------------------------------------------------
-- 5. Project Risk Factors Table
-- Fine-grained causal drivers and explanations contributing to a project risk score.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_factors (
    factor_id BIGSERIAL PRIMARY KEY,
    risk_score_id BIGINT NOT NULL REFERENCES risk_scores(risk_score_id) ON DELETE CASCADE,
    project_id VARCHAR(64) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    factor_category VARCHAR(50) NOT NULL 
        CHECK (factor_category IN ('Agency Past Performance', 'Delay in Tendering', 'Budget Gap', 'Slow Physical Pace', 'Monsoon Seasonality', 'Geographic Remoteness', 'Land Dispute', 'Contractor Inaction', 'Other')),
    factor_name VARCHAR(150) NOT NULL,
    factor_weight NUMERIC(4, 3) NOT NULL CHECK (factor_weight >= 0.000 AND factor_weight <= 1.000),
    factor_impact VARCHAR(20) NOT NULL CHECK (factor_impact IN ('Low', 'Medium', 'High', 'Critical')),
    mitigation_recommendation TEXT NOT NULL,
    is_mitigated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    engine_name VARCHAR(100) NULL,
    score NUMERIC(5, 2) NULL,
    risk_level VARCHAR(20) NULL,
    reason TEXT NULL,
    confidence NUMERIC(4, 3) NULL,
    details JSONB NULL,
    CONSTRAINT uq_risk_factors_score_factor UNIQUE (risk_score_id, factor_name)
);

CREATE INDEX IF NOT EXISTS idx_risk_factors_score_id ON risk_factors(risk_score_id);
CREATE INDEX IF NOT EXISTS idx_risk_factors_project_id ON risk_factors(project_id);
CREATE INDEX IF NOT EXISTS idx_risk_factors_category ON risk_factors(factor_category);
CREATE INDEX IF NOT EXISTS idx_risk_factors_impact ON risk_factors(factor_impact);
CREATE INDEX IF NOT EXISTS idx_risk_factors_engine_name ON risk_factors(engine_name);
CREATE INDEX IF NOT EXISTS idx_risk_factors_score ON risk_factors(score);
CREATE INDEX IF NOT EXISTS idx_risk_factors_proj_engine ON risk_factors(project_id, engine_name);


COMMENT ON TABLE risk_factors IS 'Granular contributing risk drivers, causal weights, and actionable mitigation recommendations.';

-- -----------------------------------------------------------------------------
-- 6. Project History & Audit Log Table
-- Immutable event ledger recording transitions, status modifications, and milestones.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_history (
    history_id BIGSERIAL PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL 
        CHECK (event_type IN ('Created', 'Sanctioned', 'Tender Floated', 'Work Order Issued', 'Fund Disbursed', 'Milestone Reached', 'Inspection Passed', 'Delay Flagged', 'Cost Revised', 'Completed', 'Cancelled', 'Status Changed')),
    previous_status VARCHAR(30) NULL,
    new_status VARCHAR(30) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    performed_by VARCHAR(100) NOT NULL,
    event_description TEXT NOT NULL,
    metadata_json JSONB NULL,
    CONSTRAINT uq_history_project_event_time UNIQUE (project_id, event_type, event_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_history_project_id ON project_history(project_id);
CREATE INDEX IF NOT EXISTS idx_history_event_type ON project_history(event_type);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON project_history(event_timestamp);

COMMENT ON TABLE project_history IS 'Immutable temporal audit log capturing every state transition and administrative intervention in the project lifecycle.';


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

-- High-Performance B-Tree & Composite Indexes
CREATE INDEX IF NOT EXISTS idx_projects_state_district ON projects(state_id, district_name);
CREATE INDEX IF NOT EXISTS idx_projects_status_sector ON projects(current_status, sector);
CREATE INDEX IF NOT EXISTS idx_projects_mp_name ON projects(mp_name);
CREATE INDEX IF NOT EXISTS idx_projects_agency ON projects(implementing_agency);

CREATE INDEX IF NOT EXISTS idx_financials_sanctioned ON financials(sanctioned_amount);
CREATE INDEX IF NOT EXISTS idx_financials_released ON financials(released_amount);
CREATE INDEX IF NOT EXISTS idx_financials_expenditure ON financials(expenditure_amount);
CREATE INDEX IF NOT EXISTS idx_financials_unspent ON financials(unspent_balance);
CREATE INDEX IF NOT EXISTS idx_financials_utilization_filtered ON financials(utilization_rate_pct) WHERE utilization_rate_pct IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_financials_cost_overrun_filtered ON financials(cost_overrun_amount) WHERE cost_overrun_amount > 0;

CREATE INDEX IF NOT EXISTS idx_progress_milestone_delayed ON progress(milestone_status, days_delayed);
CREATE INDEX IF NOT EXISTS idx_progress_physical_pct ON progress(physical_progress_pct);
CREATE INDEX IF NOT EXISTS idx_progress_financial_pct ON progress(financial_progress_pct);
CREATE INDEX IF NOT EXISTS idx_progress_inspection ON progress(inspection_date) WHERE inspection_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_progress_stage ON progress(current_stage);

CREATE INDEX IF NOT EXISTS idx_risk_scores_overall_desc ON risk_scores(overall_risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_scores_delay_desc ON risk_scores(delay_risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_scores_cost_desc ON risk_scores(cost_overrun_risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_scores_level_score ON risk_scores(risk_level, overall_risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_factors_category_impact ON risk_factors(factor_category, factor_impact);

CREATE INDEX IF NOT EXISTS idx_history_proj_time ON project_history(project_id, event_timestamp DESC);

-- View 1: Unified Project Overview
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

-- View 2: Delayed Projects Monitoring View
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

-- View 3: High Risk Projects Alert View
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

-- View 4: Projects with Missing Information
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

-- View 5: Sector-wise Financial & Progress Summary
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
