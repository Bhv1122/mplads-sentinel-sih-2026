"""
migrate.py
=============================================================================
Versioned Database Migration Engine for MPLADS Project (PostgreSQL).
=============================================================================

Discovers and executes SQL migration scripts from database/migrations/ in
lexicographical order. Tracks applied migrations in a 'schema_migrations'
audit table to ensure idempotent, repeatable, safe execution during development.

Never drops existing databases or tables.
"""

import sys
import os
from pathlib import Path
from typing import List
import psycopg2

DATABASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DATABASE_DIR.parent
MIGRATIONS_DIR = DATABASE_DIR / "migrations"
SCRIPTS_DIR = PROJECT_ROOT / "data" / "scripts"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "data" / "scripts"))

from scripts.db_config import get_db_config, get_db_connection




def ensure_migrations_table(conn):
    """
    Creates the schema_migrations tracking table if it does not already exist.
    """
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.commit()


def get_applied_migrations(conn) -> set:
    """
    Retrieves the set of already applied migration filenames.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT migration_name FROM schema_migrations;")
        return {row[0] for row in cur.fetchall()}


def run_migrations():
    print("=" * 70)
    print("MPLADS Database Migration Engine: Executing Versioned Migrations")
    print("=" * 70)

    cfg = get_db_config()
    target_db = cfg["dbname"]
    print(f"Connecting to database '{target_db}'...")

    conn = get_db_connection(override_dbname=target_db, autocommit=False)
    try:
        ensure_migrations_table(conn)
        applied = get_applied_migrations(conn)

        if not MIGRATIONS_DIR.exists():
            raise FileNotFoundError(f"Migrations directory not found at {MIGRATIONS_DIR}")

        migration_files: List[Path] = sorted(MIGRATIONS_DIR.glob("*.sql"))
        print(f"Discovered {len(migration_files)} migration files in {MIGRATIONS_DIR.name}/:\n")

        new_applied_count = 0
        for mf in migration_files:
            fname = mf.name
            if fname in applied:
                print(f"  [SKIPPED]  {fname:<40} (Already applied)")
                continue

            print(f"  [APPLYING] {fname:<40} ...", end="", flush=True)
            with open(mf, "r", encoding="utf-8") as f:
                sql_content = f.read()

            with conn.cursor() as cur:
                cur.execute(sql_content)
                cur.execute("INSERT INTO schema_migrations (migration_name) VALUES (%s);", (fname,))
            conn.commit()
            print(" SUCCESS!")
            new_applied_count += 1

        print("\n" + "=" * 70)
        if new_applied_count > 0:
            print(f"Migration completed successfully! Applied {new_applied_count} new migration(s).")
        else:
            print("All migrations are already up to date. No new changes applied.")
        print("=" * 70)

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed! Transaction rolled back: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()
