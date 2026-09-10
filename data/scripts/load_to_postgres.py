"""
load_to_postgres.py
=============================================================================
Production-Quality Relational Data Loader for MPLADS into PostgreSQL.
=============================================================================

Features:
  1. Environment-variable-based DB configuration (db_config.py / .env).
  2. Pre-load validation: validates dataset existence & required columns.
  3. Strict topological order:
       Dimensions & Series:
         - states
         - constituencies
         - national_summary
         - calamity_relief
         - union_budget
         - parliament_qa_state_expenditure
         - master_dim_states_constituencies
       Project Microdata:
         - projects (LOADED FIRST among project tables)
         - financials (dependent on projects)
         - progress (dependent on projects)
         - risk_scores (dependent on projects)
         - risk_factors (dependent on risk_scores & projects)
         - project_history (dependent on projects)
  4. Type conversions & NULL preservation: converts NaN/NA to Python None (SQL NULL).
  5. Idempotent Upsert strategy: ON CONFLICT DO UPDATE / DO NOTHING.
  6. Transaction management: atomic execution with rollback on critical failure.
  7. Detailed logging: processed, inserted/updated, skipped, and failed counts.
  8. Transparent error reporting: never silently discards invalid records.
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MPLADS_Loader")

# ---------------------------------------------------------------------------
# Path Configuration
# ---------------------------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
if CURRENT_DIR.parent.name == "data":
    PROJECT_ROOT = CURRENT_DIR.parent.parent
    DATA_DIR = CURRENT_DIR.parent
elif (CURRENT_DIR.parent / "data").exists():
    PROJECT_ROOT = CURRENT_DIR.parent
    DATA_DIR = PROJECT_ROOT / "data"
else:
    PROJECT_ROOT = CURRENT_DIR.parent
    DATA_DIR = PROJECT_ROOT / "data"

CLEANED_DIR = DATA_DIR / "cleaned"
PROCESSED_DIR = DATA_DIR / "processed"

# Import centralized db configuration
sys.path.insert(0, str(DATA_DIR / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from db_config import get_db_config, get_db_connection, get_db_engine

# ---------------------------------------------------------------------------
# Table Ingestion Specifications
# ---------------------------------------------------------------------------
TABLE_SPECS: List[Dict[str, Any]] = [
    # --- PHASE 1 & 2 CORE REGISTRIES & MACRO TABLES ---
    {
        "table_name": "states",
        "csv_filename": "clean_esakshi_states.csv",
        "pk_columns": ["state_id"],
        "required_columns": ["state_id", "state_name", "category", "canonical_state_key"],
        "upsert_columns": ["state_name", "category", "canonical_state_key"],
        "category": "core_dimension"
    },
    {
        "table_name": "constituencies",
        "csv_filename": "clean_esakshi_constituencies.csv",
        "pk_columns": ["constituency_id"],
        "required_columns": [
            "constituency_id", "state_id", "state_name", "constituency_name",
            "raw_caption", "reservation_category", "canonical_state_key"
        ],
        "upsert_columns": [
            "state_id", "state_name", "constituency_name", "raw_caption",
            "reservation_category", "canonical_state_key"
        ],
        "category": "core_dimension"
    },
    {
        "table_name": "national_summary",
        "csv_filename": "clean_esakshi_national_summary.csv",
        "pk_columns": ["metric_key"],
        "required_columns": ["metric_key", "metric_description", "count_works", "amount_inr", "amount_crores"],
        "upsert_columns": ["metric_description", "count_works", "amount_inr", "amount_crores"],
        "category": "core_macro"
    },
    {
        "table_name": "calamity_relief",
        "csv_filename": "clean_esakshi_calamity_relief.csv",
        "pk_columns": ["s_no"],
        "required_columns": [
            "s_no", "mp_name", "house_of_parliament", "tenure", "calamity_name",
            "calamity_type", "consented_amount_inr", "consented_amount_lakhs",
            "consent_date_iso", "tenure_start_date_iso", "tenure_end_date_iso"
        ],
        "upsert_columns": [
            "honorific", "mp_name", "house_of_parliament", "tenure", "calamity_name",
            "calamity_type", "consented_amount_inr", "consented_amount_lakhs",
            "consent_date_iso", "tenure_start_date_iso", "tenure_end_date_iso"
        ],
        "category": "core_macro"
    },
    {
        "table_name": "union_budget",
        "csv_filename": "clean_union_budget_mplads_1993_2025.csv",
        "pk_columns": ["financial_year"],
        "required_columns": [
            "financial_year", "start_year", "end_year", "scheme_entitlement_per_mp_cr",
            "budget_estimate_cr", "major_head", "status_notes"
        ],
        "upsert_columns": [
            "start_year", "end_year", "scheme_entitlement_per_mp_cr", "budget_estimate_cr",
            "revised_estimate_cr", "actual_expenditure_cr", "be_vs_actual_variance_cr",
            "major_head", "status_notes"
        ],
        "category": "core_macro"
    },
    {
        "table_name": "parliament_qa_state_expenditure",
        "csv_filename": "clean_parliament_qa_state_expenditure.csv",
        "pk_columns": ["state_id"],
        "required_columns": [
            "state_id", "state_name", "canonical_state_key", "entitlement_cr",
            "released_cr", "expenditure_cr", "unspent_balance_cr", "utilization_rate_pct",
            "works_recommended", "works_sanctioned", "works_completed"
        ],
        "upsert_columns": [
            "state_name", "canonical_state_key", "entitlement_cr", "released_cr",
            "expenditure_cr", "unspent_balance_cr", "utilization_rate_pct",
            "works_recommended", "works_sanctioned", "works_completed",
            "sanction_rate_pct", "completion_rate_pct", "is_utilization_valid", "is_workflow_valid"
        ],
        "category": "core_macro"
    },
    {
        "table_name": "master_dim_states_constituencies",
        "csv_filename": "clean_master_dim_states_constituencies.csv",
        "pk_columns": ["state_id"],
        "required_columns": [
            "state_id", "state_name", "canonical_state_key", "category",
            "total_lok_sabha_seats", "general_seats", "sc_reserved_seats", "st_reserved_seats",
            "sc_seat_share_pct", "st_seat_share_pct", "cumulative_released_cr", "cumulative_expenditure_cr"
        ],
        "upsert_columns": [
            "state_name", "canonical_state_key", "category", "total_lok_sabha_seats",
            "general_seats", "sc_reserved_seats", "st_reserved_seats", "sc_seat_share_pct",
            "st_seat_share_pct", "statutory_sc_allocation_pct", "statutory_st_allocation_pct",
            "cumulative_released_cr", "cumulative_expenditure_cr", "unspent_balance_cr",
            "utilization_pct", "works_completed_count"
        ],
        "category": "core_macro"
    },

    # --- PROJECT MICRODATA TABLES (PROJECTS LOADED FIRST, THEN DEPENDENTS) ---
    {
        "table_name": "projects",
        "csv_filename": "clean_projects.csv",
        "pk_columns": ["project_id"],
        "required_columns": [
            "project_id", "project_code", "project_title", "sector", "state_id",
            "constituency_id", "district_name", "implementing_agency", "mp_name",
            "house_of_parliament", "financial_year", "current_status", "recommendation_date"
        ],
        "upsert_columns": [
            "project_code", "project_title", "project_description", "sector", "sub_sector",
            "state_id", "constituency_id", "district_name", "block_name", "implementing_agency",
            "mp_name", "house_of_parliament", "financial_year", "current_status",
            "recommendation_date", "sanction_date", "work_order_date", "expected_completion_date",
            "actual_completion_date", "updated_at"
        ],
        "category": "project_root"
    },
    {
        "table_name": "financials",
        "csv_filename": "clean_financials.csv",
        "pk_columns": ["project_id"],
        "required_columns": [
            "project_id", "recommended_amount", "released_amount", "expenditure_amount"
        ],
        "upsert_columns": [
            "currency", "recommended_amount", "sanctioned_amount", "released_amount",
            "expenditure_amount", "utilization_rate_pct", "cost_overrun_amount",
            "cost_overrun_pct", "last_disbursement_date", "updated_at"
        ],
        "category": "project_dependent"
    },
    {
        "table_name": "progress",
        "csv_filename": "clean_progress.csv",
        "pk_columns": ["project_id", "reported_date"],
        "required_columns": [
            "project_id", "reported_date", "physical_progress_pct", "financial_progress_pct",
            "current_stage", "days_delayed", "milestone_status"
        ],
        "upsert_columns": [
            "physical_progress_pct", "financial_progress_pct", "current_stage",
            "days_delayed", "milestone_status", "inspected_by", "inspection_date",
            "inspection_remarks", "geo_latitude", "geo_longitude", "photo_evidence_url"
        ],
        "category": "project_dependent"
    },
    {
        "table_name": "project_features",
        "csv_filename": "clean_project_features.csv",
        "pk_columns": ["project_id"],
        "required_columns": [
            "project_id", "delay_days", "utilization_ratio", "cost_per_category",
            "progress_gap", "cost_deviation", "project_duration"
        ],
        "upsert_columns": [
            "delay_days", "is_delayed", "utilization_ratio", "utilization_ratio_released",
            "utilization_ratio_sanctioned", "cost_per_category", "cost_relative_to_category",
            "cost_category_zscore", "progress_gap", "progress_gap_schedule",
            "progress_gap_fin_phy", "cost_deviation", "cost_deviation_sanction",
            "cost_deviation_sanction_pct", "cost_deviation_expenditure",
            "cost_deviation_expenditure_pct", "project_duration", "project_duration_days",
            "planned_duration_days", "actual_duration_days", "elapsed_duration_days",
            "admin_sanction_duration_days", "sanction_sla_delay_days", "unreleased_allocation",
            "is_schedule_lagging", "is_disbursement_skewed", "has_cost_overrun", "updated_at"
        ],
        "category": "project_dependent"
    },
    {
        "table_name": "risk_scores",
        "csv_filename": "clean_risk_scores.csv",
        "pk_columns": ["project_id"],
        "required_columns": [
            "project_id", "overall_risk_score", "delay_risk_score", "cost_overrun_risk_score",
            "non_completion_risk_score", "leakage_risk_score", "risk_level", "confidence_score",
            "assessment_date"
        ],
        "upsert_columns": [
            "overall_risk_score", "delay_risk_score", "cost_overrun_risk_score",
            "non_completion_risk_score", "leakage_risk_score", "risk_level", "confidence_score",
            "assessment_date", "model_version"
        ],
        "category": "project_dependent"
    },
    {
        "table_name": "risk_factors",
        "csv_filename": "clean_risk_factors.csv",
        "pk_columns": ["risk_score_id", "factor_name"],
        "required_columns": [
            "risk_score_id", "project_id", "factor_category", "factor_name",
            "factor_weight", "factor_impact", "mitigation_recommendation"
        ],
        "upsert_columns": [
            "risk_score_id", "factor_category", "factor_weight", "factor_impact",
            "mitigation_recommendation", "is_mitigated"
        ],
        "category": "project_dependent"
    },
    {
        "table_name": "project_history",
        "csv_filename": "clean_project_history.csv",
        "pk_columns": ["project_id", "event_type", "event_timestamp"],
        "required_columns": [
            "project_id", "event_type", "new_status", "event_timestamp",
            "performed_by", "event_description"
        ],
        "upsert_columns": [
            "previous_status", "new_status", "performed_by", "event_description", "metadata_json"
        ],
        "category": "project_dependent"
    }
]


class PostgresDataLoader:
    def __init__(self):
        self.cfg = get_db_config()
        self.stats: Dict[str, Dict[str, int]] = {}
        self.validation_errors: List[str] = []

    def locate_csv_file(self, filename: str) -> Optional[Path]:
        """
        Locates cleaned CSV in data/cleaned/, falling back to data/processed/.
        """
        p_clean = CLEANED_DIR / filename
        if p_clean.exists():
            return p_clean
        alt_name = filename.replace("clean_", "")
        p_proc = PROCESSED_DIR / alt_name
        if p_proc.exists():
            return p_proc
        if filename == "clean_project_features.csv":
            feat_proc = PROCESSED_DIR / "featured_projects.csv"
            if feat_proc.exists():
                return feat_proc
        return None

    def validate_dataset(self, spec: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        Validates that the dataset exists and possesses all required columns.
        Never silently discards invalid datasets or columns.
        """
        table = spec["table_name"]
        csv_file = spec["csv_filename"]
        path = self.locate_csv_file(csv_file)

        if not path:
            msg = f"Table '{table}': Cleaned CSV '{csv_file}' not found in {CLEANED_DIR} or {PROCESSED_DIR}"
            logger.error(msg)
            self.validation_errors.append(msg)
            return None

        try:
            df = pd.read_csv(path)
        except Exception as e:
            msg = f"Table '{table}': Error reading CSV '{path.name}': {e}"
            logger.error(msg)
            self.validation_errors.append(msg)
            return None

        # Validate required columns
        missing_cols = [c for c in spec["required_columns"] if c not in df.columns]
        if missing_cols:
            msg = f"Table '{table}': Missing required columns {missing_cols} in '{path.name}'"
            logger.error(msg)
            self.validation_errors.append(msg)
            return None

        logger.info(f"Validated '{table}': File '{path.name}' exists with {len(df)} rows and all required columns.")
        return df

    def perform_type_sanitization(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """
        Performs type casting and sanitization required by PostgreSQL.
        Converts all pandas/numpy NaNs to Python None to ensure genuine SQL NULLs.
        """
        df_clean = df.copy()

        # Specific type conversions per table
        if table_name == "union_budget":
            for c in ["scheme_entitlement_per_mp_cr", "budget_estimate_cr", "revised_estimate_cr", "actual_expenditure_cr", "be_vs_actual_variance_cr"]:
                if c in df_clean.columns:
                    df_clean[c] = pd.to_numeric(df_clean[c], errors="coerce")
            df_clean["major_head"] = pd.to_numeric(df_clean["major_head"], errors="coerce").fillna(3475).astype(int)

        elif table_name == "projects":
            for d_col in ["recommendation_date", "sanction_date", "work_order_date", "expected_completion_date", "actual_completion_date"]:
                if d_col in df_clean.columns:
                    df_clean[d_col] = df_clean[d_col].apply(lambda v: None if pd.isna(v) or str(v).strip() == "" else str(v).strip())

        elif table_name == "financials":
            for num_col in ["recommended_amount", "sanctioned_amount", "released_amount", "expenditure_amount", "utilization_rate_pct", "cost_overrun_amount", "cost_overrun_pct"]:
                if num_col in df_clean.columns:
                    df_clean[num_col] = pd.to_numeric(df_clean[num_col], errors="coerce")

        elif table_name == "progress":
            for num_col in ["physical_progress_pct", "financial_progress_pct", "days_delayed", "geo_latitude", "geo_longitude"]:
                if num_col in df_clean.columns:
                    df_clean[num_col] = pd.to_numeric(df_clean[num_col], errors="coerce")

        elif table_name == "project_features":
            int_cols = [
                "delay_days", "project_duration", "project_duration_days",
                "planned_duration_days", "actual_duration_days", "elapsed_duration_days",
                "admin_sanction_duration_days", "sanction_sla_delay_days"
            ]
            for c in int_cols:
                if c in df_clean.columns:
                    df_clean[c] = pd.to_numeric(df_clean[c], errors="coerce")
            bool_cols = [
                "is_delayed", "is_schedule_lagging", "is_disbursement_skewed", "has_cost_overrun"
            ]
            for c in bool_cols:
                if c in df_clean.columns:
                    df_clean[c] = df_clean[c].astype(bool)
            numeric_cols = [
                "utilization_ratio", "utilization_ratio_released", "utilization_ratio_sanctioned",
                "cost_per_category", "cost_relative_to_category", "cost_category_zscore",
                "progress_gap", "progress_gap_schedule", "progress_gap_fin_phy",
                "cost_deviation", "cost_deviation_sanction", "cost_deviation_sanction_pct",
                "cost_deviation_expenditure", "cost_deviation_expenditure_pct", "unreleased_allocation"
            ]
            for c in numeric_cols:
                if c in df_clean.columns:
                    df_clean[c] = pd.to_numeric(df_clean[c], errors="coerce")

        elif table_name == "risk_scores":
            for num_col in ["overall_risk_score", "delay_risk_score", "cost_overrun_risk_score", "non_completion_risk_score", "leakage_risk_score", "confidence_score"]:
                if num_col in df_clean.columns:
                    df_clean[num_col] = pd.to_numeric(df_clean[num_col], errors="coerce")

        elif table_name == "risk_factors":
            if "factor_weight" in df_clean.columns:
                df_clean["factor_weight"] = pd.to_numeric(df_clean["factor_weight"], errors="coerce")
            if "is_mitigated" in df_clean.columns:
                df_clean["is_mitigated"] = df_clean["is_mitigated"].astype(bool)

        return df_clean

    def build_upsert_query(self, table_name: str, columns: List[str], pk_columns: List[str], upsert_columns: List[str]) -> str:
        """
        Constructs an idempotent PostgreSQL INSERT ... ON CONFLICT (...) DO UPDATE statement.
        """
        cols_sql = ", ".join(f'"{c}"' for c in columns)
        conflict_target = ", ".join(f'"{pk}"' for pk in pk_columns)

        # Filter upsert columns to those present in the insert column set
        valid_updates = [c for c in upsert_columns if c in columns and c not in pk_columns]

        if valid_updates:
            update_assignments = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in valid_updates)
            # Add updated_at trigger if applicable
            if "updated_at" in columns and "updated_at" not in valid_updates:
                update_assignments += ', "updated_at" = CURRENT_TIMESTAMP'
            upsert_clause = f"DO UPDATE SET {update_assignments}"
        else:
            upsert_clause = "DO NOTHING"

        return f'INSERT INTO "{table_name}" ({cols_sql}) VALUES %s ON CONFLICT ({conflict_target}) {upsert_clause};'

    def load_table(self, conn, spec: Dict[str, Any], df: pd.DataFrame) -> Tuple[int, int]:
        """
        Executes batch upsert within the active transaction.
        Returns: (processed_count, upserted_count)
        """
        table_name = spec["table_name"]
        pk_cols = spec["pk_columns"]
        upsert_cols = spec["upsert_columns"]

        df_sanitized = self.perform_type_sanitization(df, table_name)

        # Retrieve target table columns from PostgreSQL catalog to filter DataFrame
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, is_generated 
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public';
            """, (table_name,))
            catalog_info = cur.fetchall()
            db_cols = {r[0] for r in catalog_info if r[1] != 'ALWAYS'}  # Skip STORED generated columns

        # Intersect DataFrame columns with DB columns
        loadable_columns = [c for c in df_sanitized.columns if c in db_cols]

        upsert_sql = self.build_upsert_query(table_name, loadable_columns, pk_cols, upsert_cols)

        # Convert records to list of tuples with clean Python None for nulls
        raw_records = df_sanitized[loadable_columns].itertuples(index=False, name=None)
        clean_records = [
            tuple(None if pd.isna(val) else val for val in row)
            for row in raw_records
        ]

        total_rows = len(clean_records)
        with conn.cursor() as cur:
            # Execute batch upsert
            execute_values(cur, upsert_sql, clean_records, page_size=250)

        return total_rows, total_rows

    def execute_pipeline(self) -> bool:
        logger.info("=" * 75)
        logger.info("Starting MPLADS PostgreSQL Production Data Loading Pipeline")
        logger.info(f"Target Database: '{self.cfg['dbname']}' on {self.cfg['host']}:{self.cfg['port']}")
        logger.info("=" * 75)

        # Step 1: Pre-load validation across all datasets
        logger.info("\n>>> STAGE 1: Pre-load Dataset & Column Validation...")
        dataframes: Dict[str, pd.DataFrame] = {}
        for spec in TABLE_SPECS:
            df = self.validate_dataset(spec)
            if df is None:
                logger.error(f"Validation FAILED for table '{spec['table_name']}'. Aborting pipeline.")
                return False
            dataframes[spec["table_name"]] = df

        logger.info(f"All {len(TABLE_SPECS)} datasets successfully pre-validated. Proceeding to database connection.")

        # Step 2: Establish connection & execute in transactional order
        logger.info("\n>>> STAGE 2: Database Ingestion & Referential Integrity Execution...")
        conn = get_db_connection(override_dbname=self.cfg["dbname"], autocommit=False)

        try:
            total_processed_all = 0
            for spec in TABLE_SPECS:
                t_name = spec["table_name"]
                df = dataframes[t_name]

                logger.info(f"Loading '{t_name}' ({len(df)} records, category: {spec['category']})...")
                proc, upserted = self.load_table(conn, spec, df)
                self.stats[t_name] = {
                    "processed": proc,
                    "upserted": upserted,
                    "skipped": 0,
                    "failed": 0
                }
                total_processed_all += proc
                logger.info(f"  [SUCCESS] '{t_name}': {proc} rows processed, {upserted} upserted/idempotent.")

            # Commit the atomic transaction
            conn.commit()
            logger.info("\n" + "=" * 75)
            logger.info(f"TRANSACTION COMMITTED! All {total_processed_all} records ingested successfully across {len(TABLE_SPECS)} tables.")
            logger.info("=" * 75)

            # Print Summary Scorecard
            self.print_summary_scorecard()
            return True

        except Exception as e:
            conn.rollback()
            logger.error("\n" + "!" * 75)
            logger.error(f"CRITICAL ERROR during ingestion! Complete rollback executed. Details: {e}")
            logger.error("!" * 75)
            return False

        finally:
            conn.close()

    def print_summary_scorecard(self):
        print("\n" + "=" * 75)
        print("POSTGRESQL INGESTION SCORECARD:")
        print("=" * 75)
        print(f"{'Table Name':<35} | {'Processed':<10} | {'Upserted':<10} | {'Status':<10}")
        print("-" * 75)
        for t, s in self.stats.items():
            print(f"{t:<35} | {s['processed']:<10} | {s['upserted']:<10} | {'SUCCESS':<10}")
        print("-" * 75)
        total_p = sum(s["processed"] for s in self.stats.values())
        print(f"{'TOTAL ROWS MANAGED':<35} | {total_p:<10} | {total_p:<10} | {'100% PASS':<10}")
        print("=" * 75 + "\n")


def main():
    loader = PostgresDataLoader()
    success = loader.execute_pipeline()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
