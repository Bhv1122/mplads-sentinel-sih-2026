-- =============================================================================
-- Migration 004: Project Engineered Features Schema
-- Description: Creates the 'project_features' table to store derived analytical
--              and telemetry features engineered in Phase 5 for downstream
--              consumption by the predictive risk-scoring engine.
-- Idempotent: Uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
-- =============================================================================

CREATE TABLE IF NOT EXISTS project_features (
    project_id VARCHAR(64) PRIMARY KEY REFERENCES projects(project_id) ON DELETE CASCADE,
    
    -- 1. Core Required Engineered Features
    delay_days INTEGER NOT NULL DEFAULT 0,
    is_delayed BOOLEAN NOT NULL DEFAULT FALSE,
    utilization_ratio NUMERIC(6, 4) NOT NULL DEFAULT 0.0000,
    utilization_ratio_released NUMERIC(6, 4) NOT NULL DEFAULT 0.0000,
    utilization_ratio_sanctioned NUMERIC(6, 4) NOT NULL DEFAULT 0.0000,
    cost_per_category NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    cost_relative_to_category NUMERIC(6, 4) NOT NULL DEFAULT 1.0000,
    cost_category_zscore NUMERIC(6, 4) NOT NULL DEFAULT 0.0000,
    progress_gap NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
    progress_gap_schedule NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
    progress_gap_fin_phy NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
    cost_deviation NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    cost_deviation_sanction NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    cost_deviation_sanction_pct NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
    cost_deviation_expenditure NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    cost_deviation_expenditure_pct NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
    project_duration INTEGER NOT NULL DEFAULT 0,
    project_duration_days INTEGER NOT NULL DEFAULT 0,
    
    -- 2. Additional Lifecycle & Administrative Telemetry
    planned_duration_days INTEGER NULL,
    actual_duration_days INTEGER NULL,
    elapsed_duration_days INTEGER NOT NULL DEFAULT 0,
    admin_sanction_duration_days INTEGER NULL,
    sanction_sla_delay_days INTEGER NOT NULL DEFAULT 0,
    unreleased_allocation NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    is_schedule_lagging BOOLEAN NOT NULL DEFAULT FALSE,
    is_disbursement_skewed BOOLEAN NOT NULL DEFAULT FALSE,
    has_cost_overrun BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for accelerated risk-scoring queries, surveillance filtering, and reporting
CREATE INDEX IF NOT EXISTS idx_proj_feat_delay_days ON project_features(delay_days);
CREATE INDEX IF NOT EXISTS idx_proj_feat_is_delayed ON project_features(is_delayed);
CREATE INDEX IF NOT EXISTS idx_proj_feat_utilization ON project_features(utilization_ratio);
CREATE INDEX IF NOT EXISTS idx_proj_feat_progress_gap ON project_features(progress_gap);
CREATE INDEX IF NOT EXISTS idx_proj_feat_cost_dev ON project_features(cost_deviation);
CREATE INDEX IF NOT EXISTS idx_proj_feat_duration ON project_features(project_duration);
CREATE INDEX IF NOT EXISTS idx_proj_feat_lagging ON project_features(is_schedule_lagging);
CREATE INDEX IF NOT EXISTS idx_proj_feat_disbursement_skewed ON project_features(is_disbursement_skewed);

COMMENT ON TABLE project_features IS 'Stores derived Phase 5 mathematical and telemetry features per project for downstream consumption by the predictive risk-scoring engine.';
