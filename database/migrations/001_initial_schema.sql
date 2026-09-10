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
