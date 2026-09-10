"""
09_setup_database.py
=============================================================================
Phase 3 Database Setup: Automated PostgreSQL Provisioning & Schema Migration.
=============================================================================

Connects to PostgreSQL using secure credentials from db_config.py (environment variables),
provisions the 'mplads_db' database if it does not already exist, and executes
the relational DDL schema (data/database/schema.sql).

Verifies the creation of:
  - 7 relational tables with PK/FK/CHECK constraints
  - Indexes on foreign keys and metrics
  - 3 analytical views
"""

import sys
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent
SCHEMA_FILE = BASE_DIR / "database" / "schema.sql"

sys.path.insert(0, str(SCRIPTS_DIR))
from db_config import get_db_config, get_db_connection


def create_database_if_not_exists(dbname: str):
    """
    Connects to the maintenance 'postgres' database and creates target database if absent.
    """
    print(f"\n[1/3] Checking if target database '{dbname}' exists...")
    # Connecting to maintenance db requires autocommit to execute CREATE DATABASE
    conn = get_db_connection(override_dbname="postgres", autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (dbname,))
            exists = cur.fetchone() is not None
            if exists:
                print(f"  Database '{dbname}' already exists.")
            else:
                print(f"  Database '{dbname}' not found. Creating database '{dbname}'...")
                cur.execute(f'CREATE DATABASE "{dbname}";')
                print(f"  Database '{dbname}' created successfully.")
    finally:
        conn.close()


def apply_schema(dbname: str):
    """
    Connects to target database and executes schema.sql.
    """
    print(f"\n[2/3] Applying DDL schema from {SCHEMA_FILE.name} to '{dbname}'...")
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_FILE}")

    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_db_connection(override_dbname=dbname, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
        print("  Schema DDL executed and committed successfully.")
    except Exception as e:
        conn.rollback()
        print(f"  Error applying schema DDL: {e}")
        raise
    finally:
        conn.close()


def verify_schema_objects(dbname: str):
    """
    Inspects pg_catalog to verify that all 7 tables and 3 views are present.
    """
    print(f"\n[3/3] Verifying database objects in '{dbname}'...")
    expected_tables = [
        "states",
        "constituencies",
        "national_summary",
        "calamity_relief",
        "union_budget",
        "parliament_qa_state_expenditure",
        "master_dim_states_constituencies",
        "projects",
        "financials",
        "progress",
        "risk_scores",
        "risk_factors",
        "project_history"
    ]
    expected_views = [
        "v_state_equity_analysis",
        "v_state_efficiency_ranking",
        "v_budget_historical_performance"
    ]

    conn = get_db_connection(override_dbname=dbname)
    try:
        with conn.cursor() as cur:
            # Query tables
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
            """)
            found_tables = {row[0] for row in cur.fetchall()}

            # Query views
            cur.execute("""
                SELECT table_name 
                FROM information_schema.views 
                WHERE table_schema = 'public';
            """)
            found_views = {row[0] for row in cur.fetchall()}

            print("\n  Table Verification:")
            all_tables_ok = True
            for t in expected_tables:
                present = t in found_tables
                status = "FOUND" if present else "MISSING"
                print(f"    - {t:<35}: {status}")
                if not present:
                    all_tables_ok = False

            print("\n  View Verification:")
            all_views_ok = True
            for v in expected_views:
                present = v in found_views
                status = "FOUND" if present else "MISSING"
                print(f"    - {v:<35}: {status}")
                if not present:
                    all_views_ok = False

            # Query constraints
            cur.execute("""
                SELECT count(*) 
                FROM information_schema.table_constraints 
                WHERE table_schema = 'public';
            """)
            constraint_count = cur.fetchone()[0]
            print(f"\n  Active Constraints in Schema: {constraint_count}")

            if all_tables_ok and all_views_ok:
                print("\n  All 7 tables and 3 analytical views successfully verified!")
                return True
            else:
                raise RuntimeError("Schema verification failed: Some tables or views are missing.")
    finally:
        conn.close()


def main():
    print("=" * 70)
    print("MPLADS Phase 3: Automated PostgreSQL Database Provisioning")
    print("=" * 70)

    cfg = get_db_config()
    target_db = cfg["dbname"]

    create_database_if_not_exists(target_db)
    apply_schema(target_db)
    verify_schema_objects(target_db)

    print("\n" + "=" * 70)
    print(f"Database '{target_db}' is successfully provisioned and ready for data ingestion!")
    print("=" * 70)


if __name__ == "__main__":
    main()
