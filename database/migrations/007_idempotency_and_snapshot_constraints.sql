-- =============================================================================
-- Migration 007: Phase 11 Historical Tracking Idempotency & Concurrency Schema
-- Description: Adds unique constraint to ensure exactly one risk_history record
--              can be linked to any project snapshot, preventing duplicate
--              risk records under concurrent or repeated execution.
-- Idempotent: Uses CREATE UNIQUE INDEX IF NOT EXISTS.
-- =============================================================================

-- Enforce strict 1-to-1 relationship between snapshot_id and risk_history
CREATE UNIQUE INDEX IF NOT EXISTS uq_risk_history_snapshot_id 
ON risk_history(snapshot_id) 
WHERE snapshot_id IS NOT NULL;
