"""
backend/app/config.py
=============================================================================
Application Configuration & Environment Settings using Pydantic Settings.
=============================================================================
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from pydantic_settings import BaseSettings, SettingsConfigDict

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

ENV_FILES = [
    str(BACKEND_DIR / ".env"),
    str(PROJECT_ROOT / ".env"),
    ".env"
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database Configuration
    DATABASE_URL: Optional[str] = None
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "mplads_db"
    DB_USER: str = os.getenv("USER", "postgres")
    DB_PASSWORD: str = ""

    # Application Server Configuration
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "MPLADS Governance & Analytics Platform API"

    # CORS Configuration
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://localhost:8080,"
        "http://localhost:4173,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:8080"
    )

    # =========================================================================
    # Centralized Risk Engine Configuration (Six Risk Engines)
    # =========================================================================
    
    # 1. Engine Weights (Default active 5 engines x 20% = 100%)
    ENGINE_WEIGHT_COST_ANOMALY: float = 0.20
    ENGINE_WEIGHT_DUPLICATE_DETECTION: float = 0.20
    ENGINE_WEIGHT_DELAY_DETECTION: float = 0.20
    ENGINE_WEIGHT_PROGRESS_MISMATCH: float = 0.20
    ENGINE_WEIGHT_AGENCY_PATTERN: float = 0.20
    ENGINE_WEIGHT_FUND_UTILIZATION: float = 0.00

    RISK_ENGINE_VERSION: str = "risk_engine_v2.0"
    MISSING_ENGINE_STRATEGY: str = "RENORMALIZE"

    # 2. Risk Level Thresholds (0-29: LOW, 30-59: MEDIUM, 60-79: HIGH, 80-100: CRITICAL)
    RISK_THRESHOLD_LOW_UPPER: float = 30.0
    RISK_THRESHOLD_MEDIUM_UPPER: float = 60.0
    RISK_THRESHOLD_HIGH_UPPER: float = 80.0
    RISK_THRESHOLD_CRITICAL_UPPER: float = 100.1

    # 3. Confidence Thresholds
    CONFIDENCE_THRESHOLD_MINIMUM: float = 0.30
    CONFIDENCE_THRESHOLD_MODERATE: float = 0.60
    CONFIDENCE_THRESHOLD_HIGH: float = 0.85
    CONFIDENCE_DEFAULT_FALLBACK: float = 0.50

    # 4. Engine-Specific Thresholds
    # Cost Anomaly Engine
    COST_ANOMALY_MIN_PEERS: int = 2
    COST_ANOMALY_IQR_MULTIPLIER: float = 1.5
    COST_ANOMALY_EXTREME_IQR_MULTIPLIER: float = 3.0
    COST_ANOMALY_RATIO_MODERATE: float = 1.5
    COST_ANOMALY_RATIO_HIGH: float = 2.0

    # Duplicate Detection Engine
    DUPLICATE_SIMILARITY_LOW: float = 0.60
    DUPLICATE_SIMILARITY_MEDIUM: float = 0.75
    DUPLICATE_SIMILARITY_HIGH: float = 0.88
    DUPLICATE_SIMILARITY_CRITICAL: float = 0.95

    # Delay Detection Engine
    DELAY_DAYS_LOW: int = 30
    DELAY_DAYS_MEDIUM: int = 90
    DELAY_DAYS_HIGH: int = 180
    DELAY_DAYS_CRITICAL: int = 365

    # Progress Mismatch Engine
    PROGRESS_MISMATCH_GAP_LOW: float = 10.0
    PROGRESS_MISMATCH_GAP_MEDIUM: float = 20.0
    PROGRESS_MISMATCH_GAP_HIGH: float = 35.0
    PROGRESS_MISMATCH_GAP_CRITICAL: float = 50.0

    # Agency Pattern Engine
    AGENCY_DEFAULT_COUNT_THRESHOLD: int = 2
    AGENCY_DELAY_RATE_THRESHOLD: float = 0.50
    AGENCY_OVERLOAD_ACTIVE_PROJECTS: int = 10
    AGENCY_COST_OVERRUN_RATE_THRESHOLD: float = 0.30

    # Fund Utilization Engine
    FUND_UTILIZATION_LOW_ABSORPTION_PCT: float = 20.0
    FUND_UTILIZATION_HEALTHY_MIN_PCT: float = 70.0
    FUND_UTILIZATION_HEALTHY_MAX_PCT: float = 100.0
    FUND_UTILIZATION_OVERRUN_PCT: float = 105.0

    @property
    def engine_weights(self) -> Dict[str, float]:
        """Returns canonical mapping of all six risk engines to their configured weights."""
        return {
            "cost_anomaly": self.ENGINE_WEIGHT_COST_ANOMALY,
            "duplicate_detection": self.ENGINE_WEIGHT_DUPLICATE_DETECTION,
            "delay_detection": self.ENGINE_WEIGHT_DELAY_DETECTION,
            "progress_mismatch": self.ENGINE_WEIGHT_PROGRESS_MISMATCH,
            "agency_pattern": self.ENGINE_WEIGHT_AGENCY_PATTERN,
            "fund_utilization": self.ENGINE_WEIGHT_FUND_UTILIZATION,
        }

    @property
    def risk_weights(self) -> Dict[str, float]:
        """
        Active risk weights for Phase 6/7 evaluation (5 active detectors = 20% each).
        """
        return {
            "cost_anomaly": self.ENGINE_WEIGHT_COST_ANOMALY,
            "duplicate_detection": self.ENGINE_WEIGHT_DUPLICATE_DETECTION,
            "delay": self.ENGINE_WEIGHT_DELAY_DETECTION,
            "progress_mismatch": self.ENGINE_WEIGHT_PROGRESS_MISMATCH,
            "agency_pattern": self.ENGINE_WEIGHT_AGENCY_PATTERN,
        }

    @property
    def risk_thresholds(self) -> List[Tuple[float, str]]:
        """
        Returns ordered list of (upper_bound_exclusive, risk_level) tuples:
        0-29: LOW, 30-59: MEDIUM, 60-79: HIGH, 80-100: CRITICAL
        """
        return [
            (self.RISK_THRESHOLD_LOW_UPPER, "LOW"),
            (self.RISK_THRESHOLD_MEDIUM_UPPER, "MEDIUM"),
            (self.RISK_THRESHOLD_HIGH_UPPER, "HIGH"),
            (self.RISK_THRESHOLD_CRITICAL_UPPER, "CRITICAL"),
        ]

    def score_to_risk_level(self, score: float) -> str:
        """
        Categorizes a numerical risk score (0-100) into standard risk levels:
        0–29 = LOW, 30–59 = MEDIUM, 60–79 = HIGH, 80–100 = CRITICAL
        """
        s = float(score)
        if s < self.RISK_THRESHOLD_LOW_UPPER:
            return "LOW"
        elif s < self.RISK_THRESHOLD_MEDIUM_UPPER:
            return "MEDIUM"
        elif s < self.RISK_THRESHOLD_HIGH_UPPER:
            return "HIGH"
        return "CRITICAL"

    def confidence_to_level(self, confidence: float) -> str:
        """Categorizes a 0.0-1.0 confidence score into discrete tiers."""
        c = float(confidence)
        if c >= self.CONFIDENCE_THRESHOLD_HIGH:
            return "HIGH"
        elif c >= self.CONFIDENCE_THRESHOLD_MODERATE:
            return "MEDIUM"
        elif c >= self.CONFIDENCE_THRESHOLD_MINIMUM:
            return "LOW"
        return "VERY_LOW"

    @property
    def engine_thresholds(self) -> Dict[str, Dict[str, Any]]:
        """Dictionary of engine-specific parameters and thresholds."""
        return {
            "cost_anomaly": {
                "min_peers": self.COST_ANOMALY_MIN_PEERS,
                "iqr_multiplier": self.COST_ANOMALY_IQR_MULTIPLIER,
                "extreme_iqr_multiplier": self.COST_ANOMALY_EXTREME_IQR_MULTIPLIER,
                "ratio_moderate": self.COST_ANOMALY_RATIO_MODERATE,
                "ratio_high": self.COST_ANOMALY_RATIO_HIGH,
            },
            "duplicate_detection": {
                "low": self.DUPLICATE_SIMILARITY_LOW,
                "medium": self.DUPLICATE_SIMILARITY_MEDIUM,
                "high": self.DUPLICATE_SIMILARITY_HIGH,
                "critical": self.DUPLICATE_SIMILARITY_CRITICAL,
            },
            "delay_detection": {
                "low_days": self.DELAY_DAYS_LOW,
                "medium_days": self.DELAY_DAYS_MEDIUM,
                "high_days": self.DELAY_DAYS_HIGH,
                "critical_days": self.DELAY_DAYS_CRITICAL,
            },
            "progress_mismatch": {
                "low_gap": self.PROGRESS_MISMATCH_GAP_LOW,
                "medium_gap": self.PROGRESS_MISMATCH_GAP_MEDIUM,
                "high_gap": self.PROGRESS_MISMATCH_GAP_HIGH,
                "critical_gap": self.PROGRESS_MISMATCH_GAP_CRITICAL,
            },
            "agency_pattern": {
                "default_count_threshold": self.AGENCY_DEFAULT_COUNT_THRESHOLD,
                "delay_rate_threshold": self.AGENCY_DELAY_RATE_THRESHOLD,
                "overload_active_projects": self.AGENCY_OVERLOAD_ACTIVE_PROJECTS,
                "cost_overrun_rate_threshold": self.AGENCY_COST_OVERRUN_RATE_THRESHOLD,
            },
            "fund_utilization": {
                "low_absorption_pct": self.FUND_UTILIZATION_LOW_ABSORPTION_PCT,
                "healthy_min_pct": self.FUND_UTILIZATION_HEALTHY_MIN_PCT,
                "healthy_max_pct": self.FUND_UTILIZATION_HEALTHY_MAX_PCT,
                "overrun_pct": self.FUND_UTILIZATION_OVERRUN_PCT,
            },
        }

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return ["*"]
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return origins if origins else ["*"]

    @property
    def resolved_database_url(self) -> str:
        """
        Resolves the PostgreSQL database connection URL.
        Prioritizes DATABASE_URL if set, else builds from individual DB_* settings.
        Ensures postgresql+psycopg2 dialect.
        """
        raw_url = self.DATABASE_URL
        if raw_url and raw_url.strip():
            url = raw_url.strip()
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return url

        # Construct from components
        password_part = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
        auth_part = f"{self.DB_USER}{password_part}@" if self.DB_USER else ""
        return f"postgresql+psycopg2://{auth_part}{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
