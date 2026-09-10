"""
backend/app/services/risk/risk_engine.py
=============================================================================
Re-export of Central Risk Aggregation Engine in the risk services namespace.
=============================================================================
"""

from app.services.risk_engine import (
    RiskEngine,
    SEVERITY_TO_IMPACT,
    DETECTOR_KEY_TO_FACTOR_CATEGORY,
    _score_to_impact,
)

__all__ = [
    "RiskEngine",
    "SEVERITY_TO_IMPACT",
    "DETECTOR_KEY_TO_FACTOR_CATEGORY",
    "_score_to_impact",
]
