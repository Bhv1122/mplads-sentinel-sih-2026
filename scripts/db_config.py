"""
db_config.py
=============================================================================
Centralized Database Configuration & Connection Management for MPLADS Project.
=============================================================================

Securely loads PostgreSQL connection credentials from environment variables
(.env file or system environment) using python-dotenv.
Never hardcodes passwords or sensitive credentials in source code.

Environment Variables:
  - DB_HOST (default: localhost)
  - DB_PORT (default: 5432)
  - DB_NAME (default: mplads_db)
  - DB_USER (default: current system user)
  - DB_PASSWORD (default: empty string)
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extensions import connection as PgConnection
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from dotenv import load_dotenv

# Locate and load .env file from project root
SCRIPTS_DIR = Path(__file__).resolve().parent
if SCRIPTS_DIR.parent.name == "data":
    PROJECT_ROOT = SCRIPTS_DIR.parent.parent
else:
    PROJECT_ROOT = SCRIPTS_DIR.parent
ENV_PATH = PROJECT_ROOT / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()  # Fallback to standard environment search


def get_db_config(override_dbname: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns a dictionary of connection parameters derived strictly from environment variables.
    """
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    dbname = override_dbname or os.getenv("DB_NAME", "mplads_db")
    user = os.getenv("DB_USER", os.getenv("USER", "postgres"))
    password = os.getenv("DB_PASSWORD", "")

    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password
    }


def get_connection_url(override_dbname: Optional[str] = None) -> str:
    """
    Constructs or returns a SQLAlchemy connection URL without exposing secrets in logs.
    Prioritizes DATABASE_URL environment variable if present.
    """
    db_url = os.getenv("DATABASE_URL")
    if db_url and not override_dbname:
        if db_url.startswith("postgres://"):
            return db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
            return db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return db_url

    cfg = get_db_config(override_dbname=override_dbname)
    auth = cfg["user"]
    if cfg["password"]:
        auth += f":{cfg['password']}"
    return f"postgresql+psycopg2://{auth}@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"


def get_db_connection(override_dbname: Optional[str] = None, autocommit: bool = False) -> PgConnection:
    """
    Creates and returns a raw psycopg2 database connection.
    """
    cfg = get_db_config(override_dbname=override_dbname)
    conn = psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"]
    )
    conn.autocommit = autocommit
    return conn


def get_db_engine(override_dbname: Optional[str] = None) -> Engine:
    """
    Creates and returns a SQLAlchemy engine for Pandas integration.
    """
    url = get_connection_url(override_dbname=override_dbname)
    return create_engine(url)


def test_connection(override_dbname: Optional[str] = None) -> bool:
    """
    Tests database connectivity and reports server details.
    """
    cfg = get_db_config(override_dbname=override_dbname)
    masked_pw = "***" if cfg["password"] else "<none>"
    print(f"Testing connection to PostgreSQL at {cfg['host']}:{cfg['port']} as user '{cfg['user']}' (db: '{cfg['dbname']}', password: {masked_pw})...")
    
    try:
        conn = get_db_connection(override_dbname=override_dbname)
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version_str = cur.fetchone()[0]
            cur.execute("SELECT current_database(), current_user, inet_server_port();")
            db_info = cur.fetchone()
            print("  Connection SUCCESSFUL!")
            print(f"  PostgreSQL Version: {version_str.split(',')[0]}")
            print(f"  Connected DB: {db_info[0]} | Current Role: {db_info[1]} | Port: {db_info[2]}")
        conn.close()
        return True
    except Exception as e:
        print(f"  Connection FAILED: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Testing PostgreSQL Connection (dbname from config)...")
    test_connection()
    print("=" * 70)
