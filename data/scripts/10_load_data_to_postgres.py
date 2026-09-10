"""
10_load_data_to_postgres.py
=============================================================================
Phase 3 Ingestion: Relational ETL Loading Cleaned MPLADS Data into PostgreSQL.
=============================================================================

Reads cleaned CSV files from data/cleaned/ (or data/processed/), prepares records,
and loads them into 'mplads_db' in strict topological dependency order:
  1. states (36 rows)
  2. constituencies (543 rows)
  3. parliament_qa_state_expenditure (36 rows)
  4. master_dim_states_constituencies (36 rows)
  5. national_summary (6 rows)
  6. calamity_relief (12 rows)
  7. union_budget (33 rows)

Total expected rows: 702 rows.

Data Preservation Policy:
  - Legitimate nulls are preserved as SQL NULL (no blind zero-fills).
  - Transactions ensure atomic ingestion: any failure rolls back completely.
  - Verifies loaded counts match source CSV counts exactly.
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_batch

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent
CLEANED_DIR = BASE_DIR / "cleaned"
PROCESSED_DIR = BASE_DIR / "processed"

sys.path.insert(0, str(SCRIPTS_DIR))
from db_config import get_db_config, get_db_connection


# Ingestion manifest specifying source CSV, target table, and primary key
LOAD_MANIFEST: List[Dict[str, str]] = [
    {
        "table_name": "states",
        "csv_filename": "clean_esakshi_states.csv",
        "expected_rows": 36,
        "pk": "state_id"
    },
    {
        "table_name": "constituencies",
        "csv_filename": "clean_esakshi_constituencies.csv",
        "expected_rows": 543,
        "pk": "constituency_id"
    },
    {
        "table_name": "parliament_qa_state_expenditure",
        "csv_filename": "clean_parliament_qa_state_expenditure.csv",
        "expected_rows": 36,
        "pk": "state_id"
    },
    {
        "table_name": "master_dim_states_constituencies",
        "csv_filename": "clean_master_dim_states_constituencies.csv",
        "expected_rows": 36,
        "pk": "state_id"
    },
    {
        "table_name": "national_summary",
        "csv_filename": "clean_esakshi_national_summary.csv",
        "expected_rows": 6,
        "pk": "metric_key"
    },
    {
        "table_name": "calamity_relief",
        "csv_filename": "clean_esakshi_calamity_relief.csv",
        "expected_rows": 12,
        "pk": "s_no"
    },
    {
        "table_name": "union_budget",
        "csv_filename": "clean_union_budget_mplads_1993_2025.csv",
        "expected_rows": 33,
        "pk": "financial_year"
    }
]


def load_dataframe_for_table(csv_filename: str) -> pd.DataFrame:
    """
    Locates and reads the cleaned dataset, falling back to processed if needed.
    Replaces NaN/NA with None for SQL NULL compatibility.
    """
    path = CLEANED_DIR / csv_filename
    if not path.exists():
        # Fallback to processed dir
        alt_name = csv_filename.replace("clean_", "")
        path = PROCESSED_DIR / alt_name

    if not path.exists():
        raise FileNotFoundError(f"Source file {csv_filename} not found in {CLEANED_DIR} or {PROCESSED_DIR}")

    df = pd.read_csv(path)
    # Convert numpy/pandas nulls to Python None (preserves SQL NULL semantics)
    df = df.where(pd.notna(df), None)
    return df


def insert_table_data(conn, table_name: str, df: pd.DataFrame):
    """
    Inserts DataFrame records into the PostgreSQL table using execute_batch.
    """
    columns = list(df.columns)
    col_names_sql = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f'INSERT INTO "{table_name}" ({col_names_sql}) VALUES ({placeholders});'

    # Convert DataFrame records to list of tuples, explicitly casting any NaN to Python None for SQL NULL
    records = [
        tuple(None if pd.isna(val) else val for val in row)
        for row in df.itertuples(index=False, name=None)
    ]

    with conn.cursor() as cur:
        # Clear existing records
        cur.execute(f'TRUNCATE TABLE "{table_name}" CASCADE;')
        execute_batch(cur, insert_sql, records, page_size=200)


def verify_row_count(conn, table_name: str, expected_count: int) -> int:
    """
    Verifies that the target table contains exactly the expected number of records.
    """
    with conn.cursor() as cur:
        cur.execute(f'SELECT count(*) FROM "{table_name}";')
        actual_count = cur.fetchone()[0]
        if actual_count != expected_count:
            raise AssertionError(
                f"Row count mismatch for '{table_name}': expected {expected_count}, found {actual_count}"
            )
        return actual_count


def main():
    print("=" * 70)
    print("MPLADS Phase 3: Relational Data Ingestion into PostgreSQL")
    print("=" * 70)

    cfg = get_db_config()
    target_db = cfg["dbname"]
    print(f"Connecting to database '{target_db}'...")

    conn = get_db_connection(override_dbname=target_db, autocommit=False)
    total_inserted = 0

    try:
        print("\nIngesting tables in topological relational order:\n")
        for item in LOAD_MANIFEST:
            t_name = item["table_name"]
            csv_name = item["csv_filename"]
            exp_rows = item["expected_rows"]

            df = load_dataframe_for_table(csv_name)
            print(f"  --> Loading '{t_name}' from {csv_name} ({len(df)} rows)...", end="", flush=True)

            insert_table_data(conn, t_name, df)
            actual_rows = verify_row_count(conn, t_name, exp_rows)
            print(f" SUCCESS! Verified {actual_rows} rows in PostgreSQL.")
            total_inserted += actual_rows

        # Commit all transactions atomically
        conn.commit()
        print("\n" + "=" * 70)
        print(f"TRANSACTION COMMITTED! All {total_inserted} rows loaded across {len(LOAD_MANIFEST)} tables.")
        print("=" * 70)

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Ingestion failed! Transaction rolled back completely: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
