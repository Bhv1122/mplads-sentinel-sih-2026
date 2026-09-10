"""
backend/app/services/risk/__init__.py
=============================================================================
Package initialization for Phase 6 independent risk detection modules
and Phase 7 risk engine aggregation.
=============================================================================
"""

from app.services.risk.base import (
    BaseRiskDetector,
    RiskDetectorResult,
    score_to_severity,
)
from app.services.risk.cost_anomaly import CostAnomalyDetector
from app.services.risk.cost_anomaly_engine import CostAnomalyEngine
from app.services.risk.delay_detector import DelayDetector
from app.services.risk.delay_detection_engine import DelayDetectionEngine
from app.services.risk.fund_utilization import FundUtilizationDetector
from app.services.risk.progress_mismatch import ProgressMismatchDetector
from app.services.risk.progress_mismatch_engine import ProgressMismatchEngine
from app.services.risk.duplicate_detection import DuplicateDetector
from app.services.risk.duplicate_detection_engine import DuplicateDetectionEngine
from app.services.risk.agency_pattern_engine import AgencyPatternEngine
from app.services.risk.explained_risk_engine import ExplainedRiskEngine
from app.services.risk.risk_runner import RiskRunner
from app.services.risk.engine_base import (
    BaseRiskEngine,
    SIX_RISK_ENGINES,
)
from app.schemas.risk_engine import (
    RiskLevel,
    EngineResult,
    RiskFactorExplanation,
    ExplainedRiskResult,
)


def __getattr__(name: str):
    if name == "RiskEngine":
        try:
            from app.services.risk_engine import RiskEngine
        except ImportError:
            from backend.app.services.risk_engine import RiskEngine
        return RiskEngine
    if name in ("BatchRiskService", "BatchRiskSummary", "batch_risk_service"):
        try:
            from app.services.risk.batch_risk_service import (
                BatchRiskService,
                BatchRiskSummary,
                batch_risk_service,
            )
        except ImportError:
            from backend.app.services.risk.batch_risk_service import (
                BatchRiskService,
                BatchRiskSummary,
                batch_risk_service,
            )
        return locals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "BaseRiskDetector",
    "RiskDetectorResult",
    "score_to_severity",
    "CostAnomalyDetector",
    "CostAnomalyEngine",
    "DelayDetector",
    "DelayDetectionEngine",
    "FundUtilizationDetector",
    "ProgressMismatchDetector",
    "ProgressMismatchEngine",
    "DuplicateDetector",
    "DuplicateDetectionEngine",
    "AgencyPatternEngine",
    "ExplainedRiskEngine",
    "RiskRunner",
    "RiskEngine",
    "BaseRiskEngine",
    "SIX_RISK_ENGINES",
    "RiskLevel",
    "EngineResult",
    "RiskFactorExplanation",
    "ExplainedRiskResult",
    "BatchRiskService",
    "BatchRiskSummary",
    "batch_risk_service",
]


