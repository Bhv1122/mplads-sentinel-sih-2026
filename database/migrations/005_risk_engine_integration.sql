-- =============================================================================
-- Migration 005: Risk Engine Integration & Enhanced Audit Schema
-- Description: Extends 'risk_scores' and 'risk_factors' tables to support
--              the Six Risk Engines and Central Risk Aggregation Engine.
--              Adds timestamps, engine identifiers, JSONB details, weights,
--              and audit metadata while preserving all existing project data.
-- Idempotent: Uses ALTER TABLE ... ADD COLUMN IF NOT EXISTS.
-- =============================================================================

-- 1. Extend risk_scores
ALTER TABLE risk_scores ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE risk_scores ADD COLUMN IF NOT EXISTS weights_used JSONB NULL;
ALTER TABLE risk_scores ADD COLUMN IF NOT EXISTS config_version VARCHAR(50) NULL DEFAULT 'v1.0';
ALTER TABLE risk_scores ADD COLUMN IF NOT EXISTS engine_version VARCHAR(50) NULL DEFAULT '1.0.0';
ALTER TABLE risk_scores ADD COLUMN IF NOT EXISTS calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- Create index on updated_at for query tracking
CREATE INDEX IF NOT EXISTS idx_risk_scores_updated_at ON risk_scores(updated_at);
CREATE INDEX IF NOT EXISTS idx_risk_scores_calculated_at ON risk_scores(calculated_at);

-- 2. Extend risk_factors
ALTER TABLE risk_factors ADD COLUMN IF NOT EXISTS engine_name VARCHAR(100) NULL;
ALTER TABLE risk_factors ADD COLUMN IF NOT EXISTS score NUMERIC(5, 2) NULL;
ALTER TABLE risk_factors ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20) NULL;
ALTER TABLE risk_factors ADD COLUMN IF NOT EXISTS reason TEXT NULL;
ALTER TABLE risk_factors ADD COLUMN IF NOT EXISTS confidence NUMERIC(4, 3) NULL;
ALTER TABLE risk_factors ADD COLUMN IF NOT EXISTS details JSONB NULL;

-- Create indexes on risk_factors for fast multi-engine querying
CREATE INDEX IF NOT EXISTS idx_risk_factors_engine_name ON risk_factors(engine_name);
CREATE INDEX IF NOT EXISTS idx_risk_factors_score ON risk_factors(score);
CREATE INDEX IF NOT EXISTS idx_risk_factors_proj_engine ON risk_factors(project_id, engine_name);

COMMENT ON COLUMN risk_scores.weights_used IS 'JSON dictionary of active engine weights applied during calculation.';
COMMENT ON COLUMN risk_scores.calculated_at IS 'Timestamp when the risk calculation was executed.';
COMMENT ON COLUMN risk_factors.engine_name IS 'Canonical identifier of the risk engine producing this factor.';
COMMENT ON COLUMN risk_factors.details IS 'Structured diagnostic indicators and factual evidence emitted by the engine.';
