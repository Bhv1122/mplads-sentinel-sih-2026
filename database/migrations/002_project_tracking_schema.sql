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
    CONSTRAINT uq_risk_scores_project UNIQUE (project_id)
);

CREATE INDEX IF NOT EXISTS idx_risk_scores_project_id ON risk_scores(project_id);
CREATE INDEX IF NOT EXISTS idx_risk_scores_risk_level ON risk_scores(risk_level);
CREATE INDEX IF NOT EXISTS idx_risk_scores_overall ON risk_scores(overall_risk_score);
CREATE INDEX IF NOT EXISTS idx_risk_scores_date ON risk_scores(assessment_date);

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
    CONSTRAINT uq_risk_factors_score_factor UNIQUE (risk_score_id, factor_name)
);

CREATE INDEX IF NOT EXISTS idx_risk_factors_score_id ON risk_factors(risk_score_id);
CREATE INDEX IF NOT EXISTS idx_risk_factors_project_id ON risk_factors(project_id);
CREATE INDEX IF NOT EXISTS idx_risk_factors_category ON risk_factors(factor_category);
CREATE INDEX IF NOT EXISTS idx_risk_factors_impact ON risk_factors(factor_impact);

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
