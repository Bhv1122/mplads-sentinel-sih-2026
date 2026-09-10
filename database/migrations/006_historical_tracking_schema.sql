-- =============================================================================
-- Migration 006: Historical Tracking & Risk Evolution Schema (Phase 11)
-- Description: Creates 'project_snapshots' and 'risk_history' tables to support
--              immutable longitudinal versioning, telemetry tracking, and
--              temporal risk score trajectory analysis for MPLADS projects.
-- Idempotent: Uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Project Snapshots Table
-- Captures immutable historical point-in-time states of project execution,
-- financial progress, milestones, derived telemetry, and risk evaluations.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_snapshots (
    snapshot_id BIGSERIAL PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    snapshot_datetime TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    project_status VARCHAR(30) NOT NULL,
    
    -- Financial metrics
    recommended_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    sanctioned_amount NUMERIC(14, 2) NULL,
    released_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    expenditure_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    unspent_balance NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    utilization_rate_pct NUMERIC(6, 2) NULL,
    cost_overrun_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    
    -- Physical & financial progress
    physical_progress_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00 
        CHECK (physical_progress_pct >= 0.00 AND physical_progress_pct <= 100.00),
    financial_progress_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00 
        CHECK (financial_progress_pct >= 0.00 AND financial_progress_pct <= 100.00),
    
    -- Milestone & completion tracking
    expected_completion_date DATE NULL,
    actual_completion_date DATE NULL,
    days_delayed INTEGER NOT NULL DEFAULT 0,
    milestone_status VARCHAR(30) NOT NULL DEFAULT 'On Track',
    
    -- Derived metrics & analytics telemetry
    cost_deviation NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    progress_gap NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
    derived_metrics JSONB NULL,
    
    -- Point-in-time risk evaluation
    overall_risk_score NUMERIC(5, 2) NOT NULL DEFAULT 0.00 
        CHECK (overall_risk_score >= 0.00 AND overall_risk_score <= 100.00),
    risk_level VARCHAR(20) NOT NULL DEFAULT 'Low' 
        CHECK (risk_level IN ('Low', 'Moderate', 'Medium', 'High', 'Critical')),
    
    -- Delta explanation & audit metadata
    change_summary TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes on project_snapshots for fast temporal querying and filtering
CREATE INDEX IF NOT EXISTS idx_snapshots_project_id ON project_snapshots(project_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_datetime ON project_snapshots(snapshot_datetime);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON project_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_snapshots_proj_datetime ON project_snapshots(project_id, snapshot_datetime DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_risk_level ON project_snapshots(risk_level);
CREATE INDEX IF NOT EXISTS idx_snapshots_status ON project_snapshots(project_status);

COMMENT ON TABLE project_snapshots IS 'Immutable historical versions capturing project financial progress, physical milestone execution, telemetry, and risk states.';
COMMENT ON COLUMN project_snapshots.snapshot_id IS 'Unique serial surrogate identifier for this historical snapshot.';
COMMENT ON COLUMN project_snapshots.project_id IS 'Foreign key referencing the master project record.';
COMMENT ON COLUMN project_snapshots.snapshot_datetime IS 'Precise timestamp when the snapshot was recorded.';
COMMENT ON COLUMN project_snapshots.derived_metrics IS 'Structured JSON dictionary of derived engineering metrics, z-scores, and velocity.';
COMMENT ON COLUMN project_snapshots.change_summary IS 'Human-readable narrative or structured summary of deltas from previous snapshot.';


-- -----------------------------------------------------------------------------
-- 2. Risk History Table
-- Records the composite risk calculation and multi-engine score decomposition
-- corresponding to project snapshots over time.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_history (
    history_id BIGSERIAL PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    snapshot_id BIGINT NULL REFERENCES project_snapshots(snapshot_id) ON DELETE CASCADE,
    overall_risk_score NUMERIC(5, 2) NOT NULL 
        CHECK (overall_risk_score >= 0.00 AND overall_risk_score <= 100.00),
    risk_level VARCHAR(20) NOT NULL 
        CHECK (risk_level IN ('Low', 'Moderate', 'Medium', 'High', 'Critical')),
    
    -- Individual detector breakdown scores
    delay_risk_score NUMERIC(5, 2) NULL,
    cost_overrun_risk_score NUMERIC(5, 2) NULL,
    non_completion_risk_score NUMERIC(5, 2) NULL,
    leakage_risk_score NUMERIC(5, 2) NULL,
    
    -- Modular risk engine decomposition (cost_anomaly, delay_detection, progress_mismatch, duplicate_detection, agency_pattern, fund_utilization)
    detector_scores JSONB NULL,
    weights_used JSONB NULL,
    primary_factors JSONB NULL,
    
    -- Model & engine versions
    engine_version VARCHAR(50) NULL DEFAULT '1.0.0',
    model_version VARCHAR(50) NULL DEFAULT 'v1.0',
    
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes on risk_history for rapid trajectory and trend queries
CREATE INDEX IF NOT EXISTS idx_risk_history_project_id ON risk_history(project_id);
CREATE INDEX IF NOT EXISTS idx_risk_history_snapshot_id ON risk_history(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_risk_history_calculated_at ON risk_history(calculated_at);
CREATE INDEX IF NOT EXISTS idx_risk_history_proj_calc ON risk_history(project_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_history_risk_level ON risk_history(risk_level);

COMMENT ON TABLE risk_history IS 'Detailed risk evaluation calculations and multi-detector decompositions corresponding to project snapshots.';
COMMENT ON COLUMN risk_history.detector_scores IS 'JSON dictionary containing standardized scores, weights, and evidence from each risk engine.';
COMMENT ON COLUMN risk_history.weights_used IS 'JSON dictionary of engine weights active at time of calculation.';
COMMENT ON COLUMN risk_history.primary_factors IS 'Array of top contributing causal risk factors and diagnostic evidence.';
