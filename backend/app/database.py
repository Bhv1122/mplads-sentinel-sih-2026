"""
backend/app/database.py
=============================================================================
Database Connection, Session Management & Dependency Injection for FastAPI.
=============================================================================

Connects FastAPI to the existing PostgreSQL database from Phase 3 using SQLAlchemy.
Reads connection credentials strictly from the DATABASE_URL environment variable
(or individual DB_* environment variables as fallback).
Never hardcodes credentials or secrets.
Does not overwrite, drop, or recreate existing database tables.
"""

import os
import logging
from pathlib import Path
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Configure module logger
logger = logging.getLogger("backend.database")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Locate .env file: check backend/ directory first, then project root
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

BACKEND_ENV = BACKEND_DIR / ".env"
ROOT_ENV = PROJECT_ROOT / ".env"

if BACKEND_ENV.exists():
    load_dotenv(dotenv_path=BACKEND_ENV)
elif ROOT_ENV.exists():
    load_dotenv(dotenv_path=ROOT_ENV)
else:
    load_dotenv()


try:
    from app.config import settings
except ImportError:
    from backend.app.config import settings


def get_database_url() -> str:
    """
    Resolves the database connection URL using Pydantic Settings.
    Prioritizes DATABASE_URL if present; otherwise constructs it from DB_* components.
    Ensures compatibility with psycopg2 driver.
    """
    try:
        return settings.resolved_database_url
    except Exception:
        raw_url = os.getenv("DATABASE_URL")
        if raw_url and raw_url.strip():
            url = raw_url.strip()
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return url

        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "mplads_db")
        db_user = os.getenv("DB_USER", os.getenv("USER", "postgres"))
        db_password = os.getenv("DB_PASSWORD", "")

        if db_password:
            return f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        return f"postgresql+psycopg2://{db_user}@{db_host}:{db_port}/{db_name}"



# Resolved database URL
DATABASE_URL = get_database_url()

# SQLAlchemy Engine with connection pool & pre-ping health validation
# Does NOT execute CREATE TABLE or drop any existing schema
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Automatically tests connectivity before giving out connections
        pool_size=10,             # Persistent pool connections
        max_overflow=20,          # Transient burst capacity
        pool_recycle=1800,        # Recycle idle connections after 30 minutes
        echo=os.getenv("SQL_ECHO", "False").lower() in ("true", "1")
    )
except Exception as exc:
    logger.critical(f"Failed to initialize SQLAlchemy database engine: {exc}")
    raise

# SessionLocal factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Declarative Base class
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields an independent database session per request,
    wraps operations with error handling, and guarantees session closure.
    """
    db = SessionLocal()
    try:
        yield db
    except OperationalError as exc:
        logger.error(f"PostgreSQL OperationalError during request: {exc}")
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        logger.error(f"SQLAlchemyError during request: {exc}")
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    """
    Verifies that the database engine can successfully connect and execute a query.
    Logs connection failures clearly without leaking sensitive passwords.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return True
    except OperationalError as exc:
        logger.warning(f"Database connection check failed (OperationalError): {exc}")
        return False
    except Exception as exc:
        logger.warning(f"Database connection check failed: {exc}")
        return False
